from __future__ import annotations

import logging
from typing import Any, List

from src.agents.base import BaseAgent
from src.llm import prompts
from src.models.quest import Quest, Difficulty, QuestType, Goal
from src.tools.calendar import calculate_phase

logger = logging.getLogger(__name__)


class TaskPlannerAgent(BaseAgent):
    """Decomposes real-world goals into daily fantasy quests via LCEL chains."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(system_prompt=prompts.SYSTEM_TASK_PLANNER, **kwargs)

    async def run(self, session_id: str, **kwargs: Any) -> List[Quest]:
        goal: Goal = kwargs["goal"]
        day_count: int = kwargs.get("day_count", 1)

        history = await self.db.get_completion_history(session_id)
        avg_completion = int(sum(history) / len(history)) if history else 75

        phase = calculate_phase(day_count, goal.duration_days)

        result = await self.think_json(
            prompts.PROMPT_PLAN_TASKS,
            goal=goal.description,
            goal_type=goal.goal_type,
            day_count=day_count,
            total_days=goal.duration_days,
            avg_completion=avg_completion,
            current_phase=phase["current_phase"],
            total_phases=phase["total_phases"],
        )

        tasks_data = result.get("tasks", [])
        quests: List[Quest] = []

        for t in tasks_data:
            difficulty = Difficulty(t.get("difficulty", "medium"))
            quest = Quest(
                title=t.get("title", "未命名任务"),
                real_task=t.get("real_task", ""),
                quest_type=QuestType.DAILY,
                difficulty=difficulty,
                xp_reward=t.get("xp_reward", difficulty.base_xp),
            )
            await self.db.save_quest(session_id, quest)
            quests.append(quest)

        return quests

    async def create_main_quest(self, session_id: str, goal: Goal) -> Quest:
        """Create the main quest line from the user's goal."""
        result = await self.think_json(
            prompts.PROMPT_CREATE_MAIN_QUEST,
            goal_description=goal.description,
            goal_type=goal.goal_type,
            duration_days=goal.duration_days,
        )
        quest = Quest(
            title=result.get("title", "伟大的冒险"),
            real_task=result.get("real_task", goal.description),
            quest_type=QuestType.MAIN,
            difficulty=Difficulty.HARD,
            xp_reward=1000,
        )
        await self.db.save_quest(session_id, quest)
        return quest
