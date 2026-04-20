from __future__ import annotations

import json
import random

from langchain_core.tools import StructuredTool


def roll_dice(sides: int = 20, modifier: int = 0, count: int = 1) -> dict:
    """Roll dice with D&D mechanics."""
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    is_crit = sides == 20 and any(r == 20 for r in rolls)
    is_fumble = sides == 20 and all(r == 1 for r in rolls)
    return {
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
        "is_critical": is_crit,
        "is_fumble": is_fumble,
    }


def create_dice_tool() -> StructuredTool:
    def _roll(sides: int = 20, modifier: int = 0, count: int = 1) -> str:
        """投掷骰子进行事件判定（D&D风格）"""
        return json.dumps(roll_dice(sides, modifier, count), ensure_ascii=False)

    return StructuredTool.from_function(
        func=_roll,
        name="roll_dice",
        description="投掷骰子进行事件判定（D&D风格）",
    )
