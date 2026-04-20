from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.llm import prompts
from src.memory.context import ContextAssembler
from src.models.story import Chapter, OutcomeType, PlotPoint
from src.tools.dice import create_dice_tool

logger = logging.getLogger(__name__)


class StoryTellerAgent(BaseAgent):
    """Generates narrative chapters based on task progress and world state."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(system_prompt=prompts.SYSTEM_STORYTELLER, **kwargs)
        self.context_assembler = ContextAssembler(self.db)
        self.register_tool(create_dice_tool())

    async def run(self, session_id: str, **kwargs: Any) -> Chapter:
        outcome_type: str = kwargs.get("outcome_type", "advance")
        completion_pct: int = kwargs.get("completion_pct", 80)
        evaluation_comment: str = kwargs.get("evaluation_comment", "")

        ctx = await self.context_assembler.build_story_context(session_id)
        chapter_num = await self.db.get_latest_chapter_number(session_id) + 1

        result = await self.think_json(
            prompts.PROMPT_GENERATE_CHAPTER,
            **ctx,
            completion_pct=completion_pct,
            outcome_type=outcome_type,
            evaluation_comment=evaluation_comment,
        )

        chapter = Chapter(
            chapter_number=chapter_num,
            title=result.get("title", f"第{chapter_num}章"),
            content=result.get("content", ""),
            summary=result.get("summary", ""),
            outcome_type=OutcomeType(outcome_type),
            plot_points=[
                PlotPoint(description=p) for p in result.get("plot_points", [])
            ],
        )

        await self.db.save_chapter(session_id, chapter)

        for pp in result.get("resolved_plots", []):
            await self.db.save_key_fact(session_id, "resolved_plot", pp, chapter_num)

        for pp in result.get("plot_points", []):
            await self.db.save_key_fact(session_id, "plot_point", pp, chapter_num)

        return chapter

    async def generate_opening(
        self, session_id: str, character_info: str, goal: str, world_info: str
    ) -> Chapter:
        """Generate the first chapter of the adventure."""
        result = await self.think_json(
            prompts.PROMPT_GENERATE_OPENING,
            character_info=character_info,
            goal=goal,
            world_info=world_info,
        )

        chapter = Chapter(
            chapter_number=1,
            title=result.get("title", "序章：觉醒"),
            content=result.get("content", ""),
            summary=result.get("summary", ""),
            outcome_type=OutcomeType.ADVANCE,
            plot_points=[
                PlotPoint(description=p) for p in result.get("plot_points", [])
            ],
        )

        await self.db.save_chapter(session_id, chapter)
        for pp in result.get("plot_points", []):
            await self.db.save_key_fact(session_id, "plot_point", pp, 1)

        return chapter
