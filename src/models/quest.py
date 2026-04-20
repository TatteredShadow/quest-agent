from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    @property
    def display_name(self) -> str:
        return {"easy": "简单", "medium": "中等", "hard": "困难"}[self.value]

    @property
    def base_xp(self) -> int:
        return {"easy": 30, "medium": 50, "hard": 80}[self.value]


class QuestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QuestType(str, Enum):
    MAIN = "main"
    SIDE = "side"
    DAILY = "daily"


class Quest(BaseModel):
    id: str = ""
    title: str              # 奇幻名称
    real_task: str           # 实际任务描述
    quest_type: QuestType = QuestType.DAILY
    difficulty: Difficulty = Difficulty.MEDIUM
    xp_reward: int = 50
    status: QuestStatus = QuestStatus.ACTIVE
    completion_pct: int = 0  # 0-100
    deadline: Optional[date] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    parent_quest_id: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.status in (QuestStatus.COMPLETED, QuestStatus.FAILED, QuestStatus.SKIPPED)


class Goal(BaseModel):
    """The user's real-world goal that drives the entire adventure."""
    id: str = ""
    description: str
    goal_type: str = "general"  # fitness / learning / work / creative / general
    duration_days: int = 90
    created_at: datetime = Field(default_factory=datetime.now)
    main_quest: Optional[Quest] = None
    milestones: List[Quest] = Field(default_factory=list)
