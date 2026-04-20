from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from src.utils.config import LLMConfig

logger = logging.getLogger(__name__)


def create_llm(config: LLMConfig) -> BaseChatModel:
    """Create a ChatOpenAI instance with optional fallback model.

    Supports any OpenAI-compatible API by setting base_url in config.
    Works with OpenAI, Azure, Ollama, vLLM, LM Studio, etc.
    """
    api_key = config.api_key or "sk-placeholder"

    kwargs: Dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "api_key": api_key,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url

    llm = ChatOpenAI(**kwargs)

    if config.fallback_model:
        fallback_kwargs: Dict[str, Any] = {
            "model": config.fallback_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "api_key": api_key,
        }
        if config.base_url:
            fallback_kwargs["base_url"] = config.base_url

        fallback = ChatOpenAI(**fallback_kwargs)
        return llm.with_fallbacks([fallback])

    return llm
