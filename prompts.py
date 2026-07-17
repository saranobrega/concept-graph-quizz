DIAGRAM_SYSTEM = """\
Read the supplied study notes and produce Graphviz DOT code that diagrams relationships
between the key concepts. Output ONLY valid DOT source starting with "digraph". Do not
include prose or markdown fences.

Follow these rules:
- Use digraph G { ... }.
- Set rankdir=TB and node [shape=box, style=rounded, fontname="Helvetica"].
- Extract 5-12 concept nodes and give each a short, readable label.
- Declare every concept explicitly as SimpleId [label="Readable label"].
- Give every edge a short verb-phrase label that describes the relationship, for example:
  Chunking -> Embeddings [label="feeds into"].
- Make every edge directional and specific. Never use vague relations such as "related to".
- Assert only relationships grounded in the supplied notes. Do not invent facts.
- Keep node IDs simple and valid DOT identifiers. Quote labels that contain spaces.
"""


def DIAGRAM_USER(notes: str) -> str:
    """Build our diagram request from study notes."""
    return f"STUDY NOTES:\n{notes}"

QUIZ_SYSTEM = """\
Create quizzes exclusively about relationships represented by knowledge-graph edges.
Definition-style questions are forbidden. Never ask "what is X", what a concept means,
or for properties of an isolated concept.

Generate one question per edge provided, up to a maximum of 8. Rotate across these
question types so all three appear when at least three edges are available:

1. "relation_direction": Give concept_a and the edge relation, then ask which concept
   it points to. Include 3 or 4 distinct concept labels in options, including the correct
   target label. Set ground_truth to that target label.
2. "relation_identify": Give two concept labels and ask for their relationship in the
   learner's own words. Set options to null and ground_truth to the supported relation.
3. "true_false": State a relationship and ask whether it is true. Some statements should
   be true; make plausible false statements by swapping a target between supplied edges.
   Set options to ["True", "False"] and ground_truth to the correct option.

Every item must have exactly this shape:
{"id":"q1","type":"relation_direction|relation_identify|true_false",
 "prompt":"...","concept_a":"id","concept_b":"id or null",
 "options":["..."] or null,"ground_truth":"..."}

Use only concept IDs, labels, and relationships present in the supplied graph. Number IDs
sequentially from q1. The top-level JSON value MUST be the question array itself. Do not
wrap it in an object such as {"questions": [...]}. Output ONLY raw JSON, with no prose
and no markdown fences.
"""


def QUIZ_USER(graph_json: str) -> str:
    """Build our quiz request from a serialized graph."""
    return f"KNOWLEDGE GRAPH:\n{graph_json}"


GRADE_SYSTEM = """\
Grade a free-text answer about a relationship between concepts. Accept accurate
paraphrases and award partial credit when the core direction or mechanism is incomplete.
Return ONLY raw JSON, with no prose and no markdown fences, in exactly this shape:
{"verdict":"correct|partial|incorrect","feedback":"one sentence"}
"""


def GRADE_USER(question_json: str, user_answer: str) -> str:
    """Build our grading request with the expected relationship."""
    return (
        f"QUESTION OBJECT: {question_json}\n"
        f"GROUND TRUTH: included in the question object's ground_truth field\n"
        f"LEARNER ANSWER: {user_answer}"
    )
