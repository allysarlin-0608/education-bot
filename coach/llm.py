"""Groq calls shared by the lesson page and the book tracker."""
import json
import re

import streamlit as st

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

MODEL_NAME = "openai/gpt-oss-120b"
NO_KEY = "還沒有設定 Groq API key，請先在側邊欄設定。"


def get_client():
    key = st.session_state.get("api_key", "")
    if not key or not GROQ_AVAILABLE:
        return None
    return groq.Groq(api_key=key)


def _stream(client, system_prompt, messages):
    stream = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=2048,
        messages=[{"role": "system", "content": system_prompt}] + messages,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_reply(system_prompt, messages):
    """Stream a reply into an assistant chat bubble and return its text,
    or None if the call couldn't be made."""
    client = get_client()
    with st.chat_message("assistant"):
        if client is None:
            st.warning(NO_KEY)
            return None
        try:
            return st.write_stream(_stream(client, system_prompt, messages))
        except Exception as e:
            st.error(f"呼叫 Groq 時出了點問題：{e}")
            return None


def parse_json(text: str):
    """The first JSON object in a model reply, or None."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ask_json(system_prompt, messages):
    """Ask for a JSON object (non-streaming). Returns (data, error)."""
    client = get_client()
    if client is None:
        return None, NO_KEY
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=4096,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        return None, f"呼叫 Groq 時出了點問題：{e}"
    data = parse_json(resp.choices[0].message.content)
    if data is None:
        return None, "教練這次的回覆格式跑掉了，再送出一次就好。"
    return data, None
