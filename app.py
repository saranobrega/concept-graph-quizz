import streamlit as st

from extract import dot_to_graph, generate_dot
from quiz import generate_quiz, grade_answer


SAMPLE_NOTES = r"""retrieval augmented generation (RAG) - notes

basic idea: dont rely only on what the LLM memorized during training, give it
fresh/relevant docs at query time instead. helps a lot with hallucination since
model can ground its answer in actual retrieved text instead of guessing

pipeline is roughly: chunking -> embeddings -> vector store -> retriever ->
(optional reranker) -> augmented prompt -> generator LLM -> answer

chunking: splitting docs into smaller pieces before embedding. chunk size is a
tradeoff - too big and you retrieve irrelevant stuff mixed with relevant stuff,
too small and you lose context. overlap between chunks helps avoid cutting
important info at boundaries

embeddings: turn each chunk into a vector, meant to capture semantic meaning
not just keywords. similarity search later depends entirely on embedding
quality - bad embeddings = bad retrieval no matter how good the LLM is

vector store: where embeddings live (pinecone, weaviate, pgvector, faiss
locally). does similarity search - usually cosine similarity or dot product -
to find chunks close to the query embedding

retriever: takes the user query, embeds it, hits the vector store, returns top
k chunks. retriever quality is honestly the bottleneck of most RAG systems, not
the generator

reranker: optional second pass - takes the retriever's top k and re-scores them
with a more expensive/accurate model (cross-encoder usually) to push the truly
relevant ones to the top before they hit the prompt. retriever optimizes for
speed/recall, reranker optimizes for precision

augmented prompt: the reranked/retrieved chunks get stuffed into the prompt
alongside the user's question, this becomes the actual context the generator
sees

generator LLM: the model that reads the augmented prompt (query + retrieved
context) and writes the final answer. still limited by context window, so cant
just cram infinite chunks in

context window: hard limit on total prompt size, directly constrains how many
chunks the pipeline can pass to the generator

hallucination: generator making stuff up not grounded in the retrieved context
- RAG reduces this but doesn't eliminate it, especially if retrieval pulled
irrelevant chunks and the model tries to use them anyway"""


def save_key() -> None:
    """Store our optional API key only in the current session."""
    st.session_state["byok"] = st.session_state.get("key_input", "").strip()


def render_sidebar() -> None:
    """Render our API-key and model-cost information."""
    if "key_input" not in st.session_state:
        st.session_state.key_input = st.session_state.get("byok", "")
    st.sidebar.header("Settings")
    st.sidebar.text_input(
        "Anthropic API key (optional)",
        type="password",
        key="key_input",
        on_change=save_key,
    )
    st.sidebar.caption("The key is held only in this session and is never stored.")
    st.sidebar.caption(
        "Cost note: Sonnet generates the diagram and quiz; Haiku grades free-text "
        "answers. Option answers are graded locally."
    )


def clear_quiz() -> None:
    """Clear our quiz state when building a new diagram."""
    for key in ("questions", "quiz_idx", "score", "grade"):
        st.session_state.pop(key, None)


def start_quiz(dot: str) -> None:
    """Generate our relationship quiz from the diagram's DOT source."""
    try:
        graph = dot_to_graph(dot)
        with st.spinner("Creating relationship questions..."):
            questions = generate_quiz(graph)
    except (RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return
    st.session_state.questions = questions
    st.session_state.quiz_idx = 0
    st.session_state.score = 0.0
    st.session_state.pop("grade", None)
    st.rerun()


def submit_answer(question: dict, answer: str) -> bool:
    """Grade one answer and update our running score."""
    try:
        with st.spinner("Grading answer..."):
            result = grade_answer(question, answer)
    except (RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return False

    st.session_state.grade = result
    if result["verdict"] == "correct":
        st.session_state.score += 1
    elif result["verdict"] == "partial":
        st.session_state.score += 0.5
    return True


def show_result(result: dict) -> None:
    """Show our grading verdict with its matching status color."""
    message = f"{result['verdict'].title()}: {result['feedback']}"
    if result["verdict"] == "correct":
        st.success(message)
    elif result["verdict"] == "partial":
        st.warning(message)
    else:
        st.error(message)


def render_quiz() -> None:
    """Render one relationship question at a time."""
    questions = st.session_state.get("questions", [])
    idx = st.session_state.get("quiz_idx", 0)
    score = st.session_state.get("score", 0.0)

    if idx >= len(questions):
        st.subheader("Quiz complete")
        st.success(f"Final score: {score:g} / {len(questions)}")
        if st.button("Restart quiz"):
            clear_quiz()
            st.rerun()
        return

    question = questions[idx]
    st.divider()
    st.subheader(f"Question {idx + 1} of {len(questions)}")
    st.caption(f"Running score: {score:g} / {idx}")
    st.write(question["prompt"])

    result = st.session_state.get("grade")
    if result is None:
        with st.form(f"question_{idx}"):
            options = question.get("options")
            if isinstance(options, list):
                answer = st.radio(
                    "Answer",
                    options,
                    index=None,
                    key=f"answer_option_{idx}",
                )
            else:
                answer = st.text_input("Answer", key=f"answer_text_{idx}")
            submitted = st.form_submit_button("Submit")
        if submitted:
            if not isinstance(answer, str) or not answer.strip():
                st.warning("Enter or select an answer before submitting.")
            elif submit_answer(question, answer):
                st.rerun()
        return

    show_result(result)
    if st.button("Next"):
        st.session_state.quiz_idx = idx + 1
        st.session_state.pop("grade", None)
        st.rerun()


def main() -> None:
    """Run our notes-to-diagram and relationship-quiz workflow."""
    st.set_page_config(
        page_title="Concept Graph Quizzer",
        page_icon="🕸️",
        layout="wide",
    )
    render_sidebar()

    st.title("Concept Graph Quizzer")
    st.write("Turn study notes into a clean diagram of key concept relationships.")
    notes = st.text_area("Study notes", value=SAMPLE_NOTES, height=300)

    if st.button("Build diagram", type="primary"):
        if not notes.strip():
            st.warning("Add some study notes before building a diagram.")
        else:
            try:
                with st.spinner("Generating concept diagram..."):
                    dot = generate_dot(notes)
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))
            else:
                st.session_state.dot = dot
                clear_quiz()

    dot = st.session_state.get("dot")
    if isinstance(dot, str):
        st.subheader("Concept diagram")
        st.graphviz_chart(dot, use_container_width=True)
        if "questions" not in st.session_state:
            if st.button("Start quiz"):
                start_quiz(dot)
        else:
            render_quiz()


if __name__ == "__main__":
    main()
