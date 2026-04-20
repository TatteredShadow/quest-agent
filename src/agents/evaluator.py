from __future__ import annotations

import logging
from typing import Any, List
from dataclasses import dataclass

from src.agents.base import BaseAgent
from src.llm import prompts
from src.models.quest import Quest, QuestStatus
from src.models.story import OutcomeType

logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@dataclass
class EvaluationResult:
    completion_pct: int
    outcome_type: OutcomeType
    comment: str
    xp_earned: int
    streak_bonus: bool
    character_effects: dict


class EvaluatorAgent(BaseAgent):
    """Evaluates daily task completion and maps results to story outcomes."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(system_prompt=prompts.SYSTEM_EVALUATOR, **kwargs)

    async def run(self, session_id: str, **kwargs: Any) -> EvaluationResult:
        quests: List[Quest] = kwargs["quests"]
        streak_days: int = kwargs.get("streak_days", 0)

        tasks_status = self._format_tasks(quests)
        streak_threshold = self.config.game.streak_bonus_threshold

        result = await self.think_json(
            prompts.PROMPT_EVALUATE,
            tasks_status=tasks_status,
            streak_days=streak_days,
            streak_threshold=streak_threshold,
        )

        completion = _safe_int(
            result.get("completion_pct"), self._calc_completion(quests)
        )
        outcome_str = result.get("outcome_type", self._determine_outcome(completion))

        raw_effects = result.get("character_effects", {})
        effects: dict = {}
        if isinstance(raw_effects, dict):
            effects["hp_delta"] = _safe_int(raw_effects.get("hp_delta"), 0)
            raw_stats = raw_effects.get("stat_changes", {})
            if isinstance(raw_stats, dict):
                effects["stat_changes"] = {
                    k: _safe_int(v, 0) for k, v in raw_stats.items()
                }
            else:
                effects["stat_changes"] = {}

        return EvaluationResult(
            completion_pct=completion,
            outcome_type=OutcomeType(outcome_str),
            comment=str(result.get("comment", "")),
            xp_earned=_safe_int(result.get("xp_earned"), self._calc_xp(quests)),
            streak_bonus=bool(result.get("streak_bonus", False)),
            character_effects=effects,
        )

    def _format_tasks(self, quests: List[Quest]) -> str:
        lines = []
        for q in quests:
            status_icon = {
                QuestStatus.COMPLETED: "[完成]",
                QuestStatus.FAILED: "[失败]",
                QuestStatus.SKIPPED: "[跳过]",
                QuestStatus.ACTIVE: "[未完成]",
            }.get(q.status, "[?]")
            lines.append(
                f"{status_icon} {q.title}（{q.real_task}）- "
                f"{q.difficulty.display_name} {q.xp_reward}XP - 完成度{q.completion_pct}%"
            )
        return "\n".join(lines)

    def _calc_completion(self, quests: List[Quest]) -> int:
        if not quests:
            return 0
        return int(sum(q.completion_pct for q in quests) / len(quests))

    def _determine_outcome(self, pct: int) -> str:
        if pct >= 100:
            return "triumph"
        if pct >= 80:
            return "advance"
        if pct >= 50:
            return "setback"
        return "crisis"

    def _calc_xp(self, quests: List[Quest]) -> int:
        total = 0
        for q in quests:
            if q.status == QuestStatus.COMPLETED:
                total += q.xp_reward
            elif q.completion_pct > 0:
                total += int(q.xp_reward * q.completion_pct / 100)
        return total
