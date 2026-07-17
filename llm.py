import json
import os
import re

import anthropic
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


def get_api_key() -> str:
    """Return our sidebar key first, then our environment key."""
    byok = st.session_state.get("byok", "")
    if isinstance(byok, str) and byok.strip():
        return byok.strip()

    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    raise RuntimeError(
        "Add ANTHROPIC_API_KEY to .env or paste an Anthropic API key in the sidebar."
    )


def call_claude(model: str, system: str, user: str, max_tokens: int) -> str:
    """Call Claude and return our concatenated text response."""
    try:
        client = anthropic.Anthropic(api_key=get_api_key())
        response = client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        detail = str(exc).strip() or "unknown Anthropic API error"
        raise RuntimeError(f"Claude request failed: {detail}") from exc


def parse_json(raw: str) -> dict:
    """Parse our JSON response after removing optional markdown fences."""
    text = raw.strip()
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        preview = raw[:200]
        raise ValueError(f"Claude returned invalid JSON. Raw response: {preview!r}") from exc
