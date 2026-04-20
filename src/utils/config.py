from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Union

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key_env: str = "OPENAI_API_KEY"
    api_key_direct: str = ""
    temperature: float = 0.8
    max_tokens: int = 2000
    fallback_model: str = "gpt-4o-mini"
    base_url: str = ""
    embedding_model: str = "text-embedding-3-small"

    @property
    def api_key(self) -> Optional[str]:
        if self.api_key_direct:
            return self.api_key_direct
        return os.environ.get(self.api_key_env)


@dataclass
class GameConfig:
    difficulty: str = "normal"
    story_style: str = "high_fantasy"
    language: str = "zh"
    xp_per_level: int = 500
    streak_bonus_threshold: int = 3


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    game: GameConfig = field(default_factory=GameConfig)


def load_config(path: Optional[Union[Path, str]] = None) -> AppConfig:
    path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        return AppConfig()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    llm_cfg = LLMConfig(**raw.get("llm", {}))
    game_cfg = GameConfig(**raw.get("game", {}))
    return AppConfig(llm=llm_cfg, game=game_cfg)
