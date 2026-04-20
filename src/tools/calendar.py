from __future__ import annotations

import json
from datetime import date
from typing import Optional

from langchain_core.tools import StructuredTool

from src.models.character import Character


def get_streak_info(character: Character) -> dict:
    return {
        "streak_days": character.streak_days,
        "total_days": character.total_days,
        "is_streak_bonus": character.streak_days > 0 and character.streak_days % 3 == 0,
    }


def get_date_info(start_date: Optional[str] = None) -> dict:
    today = date.today()
    info = {
        "today": today.isoformat(),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()],
    }
    if start_date:
        start = date.fromisoformat(start_date)
        info["elapsed_days"] = (today - start).days
    return info


def calculate_phase(day_count: int, total_days: int, num_phases: int = 4) -> dict:
    """Determine which story phase the user is in."""
    phase_length = total_days // num_phases
    current_phase = (
        min(day_count // phase_length + 1, num_phases) if phase_length > 0 else 1
    )
    phase_names = ["启程", "试炼", "深渊", "归来"]
    return {
        "current_phase": current_phase,
        "total_phases": num_phases,
        "phase_name": (
            phase_names[current_phase - 1]
            if current_phase <= len(phase_names)
            else "尾声"
        ),
        "phase_progress_pct": (
            int((day_count % phase_length) / phase_length * 100)
            if phase_length > 0
            else 100
        ),
    }


def create_calendar_tool(character: Character) -> StructuredTool:
    def handler(action: str = "streak") -> str:
        """查看打卡连续天数、当前日期等日历信息（action: streak 或 date）"""
        if action == "streak":
            return json.dumps(get_streak_info(character), ensure_ascii=False)
        elif action == "date":
            return json.dumps(get_date_info(), ensure_ascii=False)
        return "未知操作"

    return StructuredTool.from_function(
        func=handler,
        name="get_calendar",
        description="查看打卡连续天数、当前日期等日历信息",
    )
