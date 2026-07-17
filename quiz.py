import json
import re

from llm import call_claude, parse_json
from prompts import GRADE_SYSTEM, GRADE_USER, QUIZ_SYSTEM, QUIZ_USER


TYPES = {"relation_direction", "relation_identify", "true_false"}
VERDICTS = {"correct", "partial", "incorrect"}
QUESTION_KEYS = {
    "id",
    "type",
    "prompt",
    "concept_a",
    "concept_b",
    "options",
    "ground_truth",
}


def _is_definition(prompt: str, labels: set[object]) -> bool:
    """Detect forbidden definition-style prompts about our concept labels."""
    text = " ".join(prompt.casefold().split())
    for label in labels:
        if not isinstance(label, str):
            continue
        name = re.escape(label.casefold())
        if re.match(rf"^(what is|define)\s+{name}\s*[?.!]*$", text):
            return True
        if re.match(rf"^what does\s+{name}\s+mean\s*[?.!]*$", text):
            return True
    return False


def _fix_direction_options(question: dict, graph: dict, idx: int) -> None:
    """Build our direction choices from known concept labels."""
    concepts = graph.get("concepts", graph.get("nodes", []))
    label_by_id = {
        concept["id"]: concept["label"]
        for concept in concepts
        if isinstance(concept, dict)
        and isinstance(concept.get("id"), str)
        and isinstance(concept.get("label"), str)
    }
    labels = list(dict.fromkeys(label_by_id.values()))
    if len(labels) < 3:
        raise ValueError("The diagram needs at least 3 distinct concepts for quiz options.")

    raw_truth = str(question.get("ground_truth", "")).strip()
    truth = next(
        (label for label in labels if label.casefold() == raw_truth.casefold()),
        None,
    )
    if truth is None:
        truth = label_by_id.get(raw_truth) or label_by_id.get(question.get("concept_b"))
    if truth is None:
        targets = [
            edge.get("target")
            for edge in graph.get("edges", [])
            if isinstance(edge, dict) and edge.get("source") == question.get("concept_a")
        ]
        if len(targets) == 1:
            truth = label_by_id.get(targets[0])
    if truth is None:
        raise ValueError("A relation-direction question has an unknown correct concept.")

    others = [label for label in labels if label != truth]
    offset = (idx - 1) % len(others)
    others = others[offset:] + others[:offset]
    size = min(4, len(labels))
    options = others[: size - 1]
    options.insert((idx - 1) % size, truth)
    question["ground_truth"] = truth
    question["options"] = options


def _validate_questions(data: object, graph: dict) -> list[dict]:
    """Validate our generated relationship questions."""
    if not isinstance(data, list):
        raise ValueError("Claude must return quiz questions as a JSON list.")
    questions = data
    expected = min(len(graph["edges"]), 8)
    if len(questions) != expected:
        raise ValueError(
            f"Expected {expected} quiz questions (one per edge, capped at 8), "
            f"got {len(questions)}"
        )

    concepts = graph.get("concepts", graph.get("nodes", []))
    ids = {
        concept.get("id")
        for concept in concepts
        if isinstance(concept, dict) and isinstance(concept.get("id"), str)
    }
    labels = {
        concept.get("label")
        for concept in concepts
        if isinstance(concept, dict) and isinstance(concept.get("label"), str)
    }
    seen_types: set[str] = set()
    for idx, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError("Every quiz question must be a JSON object.")
        if set(question) != QUESTION_KEYS:
            raise ValueError("A quiz question does not match the required JSON shape.")
        if question.get("id") != f"q{idx}":
            raise ValueError("Quiz question IDs must be sequential from q1.")

        kind = question.get("type")
        if kind not in TYPES:
            raise ValueError("A quiz question has an unsupported type.")
        seen_types.add(kind)
        if not isinstance(question.get("prompt"), str) or not question["prompt"].strip():
            raise ValueError("A quiz question is missing its prompt.")
        if _is_definition(question["prompt"], labels):
            raise ValueError("Definition-style quiz questions are not allowed.")
        if question.get("concept_a") not in ids:
            raise ValueError("A quiz question references an unknown concept_a.")
        if question.get("concept_b") is not None and question["concept_b"] not in ids:
            raise ValueError("A quiz question references an unknown concept_b.")
        if not isinstance(question.get("ground_truth"), str) or not question[
            "ground_truth"
        ].strip():
            raise ValueError("A quiz question is missing its ground truth.")

        if kind == "relation_direction":
            _fix_direction_options(question, graph, idx)
        options = question.get("options")
        if kind == "relation_identify" and options is not None:
            raise ValueError("Relation-identify questions must use free text.")
        if kind == "relation_direction":
            if (
                not isinstance(options, list)
                or not 3 <= len(options) <= 4
                or not all(isinstance(option, str) and option.strip() for option in options)
                or len(set(options)) != len(options)
                or not set(options).issubset(labels)
                or question["ground_truth"] not in options
            ):
                raise ValueError("Relation-direction questions need 3-4 valid options.")
        if kind == "true_false" and (
            options != ["True", "False"] or question["ground_truth"] not in options
        ):
            raise ValueError("True/false questions must use True and False options.")

    if expected >= 3 and seen_types != TYPES:
        raise ValueError("The quiz must vary across all three relationship question types.")
    return questions


def _unwrap_questions(data: object) -> object:
    """Unwrap our question array when Claude adds an unnecessary object wrapper."""
    if not isinstance(data, dict):
        return data
    for key in ("questions", "quiz"):
        questions = data.get(key)
        if isinstance(questions, list):
            return questions
    if len(data) == 1:
        questions = next(iter(data.values()))
        if isinstance(questions, list):
            return questions
    return data


def generate_quiz(graph: dict) -> list[dict]:
    """Generate one relationship question per edge, capped at eight."""
    rels = graph.get("edges", graph.get("relationships"))
    concepts = graph.get("concepts", graph.get("nodes"))
    if not isinstance(rels, list) or not rels:
        raise ValueError("The graph has no relationships to quiz.")
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("The graph has no concepts for quiz options.")

    limited = {"concepts": concepts, "edges": rels[:8]}
    graph_json = json.dumps(limited, ensure_ascii=False)
    raw = call_claude(
        "claude-sonnet-5",
        QUIZ_SYSTEM,
        QUIZ_USER(graph_json),
        2500,
    )
    data = _unwrap_questions(parse_json(raw))
    return _validate_questions(data, limited)


def grade_answer(question: dict, user_answer: str) -> dict:
    """Grade our option answers locally and free-text answers with Claude."""
    options = question.get("options")
    truth = question.get("ground_truth")
    if not isinstance(truth, str) or not truth.strip():
        raise ValueError("The question has no valid ground truth.")

    if isinstance(options, list):
        correct = user_answer.strip().casefold() == truth.strip().casefold()
        if correct:
            return {"verdict": "correct", "feedback": "Correct relationship."}
        return {
            "verdict": "incorrect",
            "feedback": f"The correct answer is {truth}.",
        }

    raw = call_claude(
        "claude-haiku-4-5",
        GRADE_SYSTEM,
        GRADE_USER(json.dumps(question, ensure_ascii=False), user_answer),
        300,
    )
    data = parse_json(raw)
    if (
        not isinstance(data, dict)
        or data.get("verdict") not in VERDICTS
        or not isinstance(data.get("feedback"), str)
        or not data["feedback"].strip()
    ):
        raise ValueError("Claude returned an invalid grading response.")
    return data
