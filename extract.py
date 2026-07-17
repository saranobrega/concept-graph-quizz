import re

from llm import call_claude
from prompts import DIAGRAM_SYSTEM, DIAGRAM_USER


EDGE_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[([^\]]*)\]"
)
NODE_RE = re.compile(
    r"(?:^|[;{\n])\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[([^\]]*)\]",
    flags=re.MULTILINE,
)
LABEL_RE = re.compile(r'\blabel\s*=\s*"((?:\\.|[^"\\])*)"')


def generate_dot(notes: str) -> str:
    """Generate and validate our Graphviz DOT diagram."""
    raw = call_claude(
        model="claude-sonnet-5",
        system=DIAGRAM_SYSTEM,
        user=DIAGRAM_USER(notes),
        max_tokens=1500,
    )
    dot = raw.strip()
    match = re.fullmatch(
        r"```(?:dot|graphviz)?\s*(.*?)\s*```",
        dot,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        dot = match.group(1).strip()
    if not dot.startswith("digraph"):
        raise ValueError(
            f"Claude returned invalid Graphviz DOT. Raw response: {raw[:200]!r}"
        )
    return dot


def _label(attrs: str) -> str | None:
    """Read our quoted label from a DOT attribute list."""
    match = LABEL_RE.search(attrs)
    if not match:
        return None
    return match.group(1).replace(r'\"', '"')


def dot_to_graph(dot: str) -> dict:
    """Derive our quiz concepts and relationships from generated DOT."""
    labels: dict[str, str] = {}
    for match in NODE_RE.finditer(dot):
        node_id, attrs = match.groups()
        label = _label(attrs)
        if node_id not in {"node", "edge", "graph"} and label:
            labels[node_id] = label

    edges: list[dict] = []
    for match in EDGE_RE.finditer(dot):
        source, target, attrs = match.groups()
        relation = _label(attrs)
        if not relation:
            raise ValueError("Every diagram edge needs a relationship label for the quiz.")
        labels.setdefault(source, source.replace("_", " "))
        labels.setdefault(target, target.replace("_", " "))
        edges.append({"source": source, "target": target, "relation": relation})

    if not edges:
        raise ValueError("The diagram has no labeled relationships to quiz.")
    concepts = [
        {"id": node_id, "label": label}
        for node_id, label in labels.items()
    ]
    return {"concepts": concepts, "edges": edges}
