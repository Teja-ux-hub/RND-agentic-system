"""Utility functions for agents."""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

LOGGER = logging.getLogger(__name__)


def get_gemini_llm(
    model_env_var: str = "GEMINI_MODEL",
    default_model: str = "gemini-2.0-flash",
    temperature: float = 0.2,
) -> ChatGoogleGenerativeAI | None:
    """Get a Gemini LLM instance if the API key is present."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        # Check primary model env var, then fall back to old names, then default
        model_name = os.getenv(model_env_var) or os.getenv("GEMINI_MODEL_FLASH") or os.getenv("GEMINI_MODEL_PRO") or default_model
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
        )
    except Exception as exc:
        LOGGER.error("Failed to initialize Gemini LLM: %s", exc)
        return None
