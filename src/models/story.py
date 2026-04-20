from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OutcomeType(str, Enum):
    TRIUMPH = "triumph"       # 超额完成 100%+
    ADVANCE = "advance"       # 达标 80-99%
    SETBACK = "setback"       # 部分完成 50-79%
    CRISIS = "crisis"         # 未完成 <50%
    MILESTONE = "milestone"   # 阶段性成果
    BONUS = "bonus"           # 连续打卡奖励

    @property
    def display_name(self) -> str:
        return {
            "triumph": "大获成功",
            "advance": "稳步推进",
            "setback": "小遇挫折",
            "crisis": "危机降临",
            "milestone": "里程碑达成",
            "bonus": "额外奖励",
        }[self.value]


class PlotPoint(BaseModel):
    description: str
    resolved: bool = False
    chapter_introduced: int = 1


class Chapter(BaseModel):
    chapter_number: int
    title: str
    content: str
    summary: str = ""
    outcome_type: OutcomeType = OutcomeType.ADVANCE
    plot_points: List[PlotPoint] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class StoryArc(BaseModel):
    """Tracks the overall narrative arc for the adventure."""
    chapters: List[Chapter] = Field(default_factory=list)
    unresolved_plots: List[PlotPoint] = Field(default_factory=list)
    current_chapter: int = 0
    theme: str = ""

    @property
    def latest_chapter(self) -> Optional[Chapter]:
        return self.chapters[-1] if self.chapters else None

    def add_chapter(self, chapter: Chapter) -> None:
        self.chapters.append(chapter)
        self.current_chapter = chapter.chapter_number
        for pp in chapter.plot_points:
            if not pp.resolved:
                self.unresolved_plots.append(pp)

    def resolve_plot(self, description: str) -> None:
        for pp in self.unresolved_plots:
            if pp.description == description:
                pp.resolved = True
        self.unresolved_plots = [p for p in self.unresolved_plots if not p.resolved]
