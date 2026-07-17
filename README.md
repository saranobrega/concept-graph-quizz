# Concept Graph Quizzer

Turn messy study notes into a Graphviz concept diagram and relationship-focused quiz.

> Screenshot placeholder

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add an Anthropic API key to `.env`:

```text
ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
streamlit run app.py
```

## How it works

1. Claude reads the notes and generates relationship-focused Graphviz DOT source.
2. Streamlit renders the DOT source as a native diagram.
3. Labeled DOT relationships become the source for relationship-only quiz questions.
4. Option answers are graded locally, while Claude grades free-text answers.

For public deployments, the sidebar supports bring-your-own-key access. The key remains
in the Streamlit session and is not stored by the app.
