from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

from settings import LLM_API_URL, LLM_MODEL, LLM_API_TIMEOUT


load_dotenv()


def chat_with_model(message: str) -> str:
    """Send a prompt to the LLM API and return the assistant content.

    Raises a RuntimeError with details when the API fails or returns an unexpected payload.
    """
    api_key = os.getenv("OPENWEB_UI_API")
    if not api_key:
        raise RuntimeError("OPENWEB_UI_API is not set in environment.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": message}],
        "reasoning": {"effort": "low"},
        "temperature": 0.1,
        "top_p": 0.1,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=LLM_API_TIMEOUT) as client:
            resp = client.post(LLM_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"LLM API request failed: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected LLM API response structure.") from exc
