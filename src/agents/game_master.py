from __future__ import annotations

import logging
from typing import Any, List
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel

from src.agents.base import BaseAgent
from src.agents.task_planner import TaskPlannerAgent
from src.agents.storyteller import StoryTellerAgent
from src.agents.evaluator import EvaluatorAgent, EvaluationResult
from src.agents.world_builder import WorldBuilderAgent
from src.llm import prompts
from src.memory.context import ContextAssembler
from src.memory.database import Database
from src.models.character import Character, CharacterClass, Stats
from src.models.quest import Quest, Goal
from src.models.story import Chapter
from src.models.world import WorldState
from src.tools.character_sheet import create_stat_update_tool, create_add_item_tool
from src.tools.calendar import create_calendar_tool
from src.utils.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class NewGameResult:
    session_id: str
    character: Character
    goal: Goal
    world: WorldState
    opening_chapter: Chapter
    daily_quests: List[Quest]


@dataclass
class CheckInResult:
    evaluation: EvaluationResult
    chapter: Chapter
    character: Character
    world: WorldState
    leveled_up: bool


class GameMasterAgent(BaseAgent):
    """Orchestrator agent that coordinates all sub-agents."""

    def __init__(self, llm: BaseChatModel, db: Database, config: AppConfig) -> None:
        super().__init__(
            llm=llm,
            db=db,
            config=config,
            system_prompt=prompts.SYSTEM_GAME_MASTER,
        )
        self.task_planner = TaskPlannerAgent(llm=llm, db=db, config=config)
        self.storyteller = StoryTellerAgent(llm=llm, db=db, config=config)
        self.evaluator = EvaluatorAgent(llm=llm, db=db, config=config)
        self.world_builder = WorldBuilderAgent(llm=llm, db=db, config=config)
        self.context_assembler = ContextAssembler(db)

    async def run(self, session_id: str, **kwargs: Any) -> Any:
        action = kwargs.get("action", "status")
        if action == "new_game":
            return await self.start_new_game(**kwargs)
        elif action == "check_in":
            return await self.daily_check_in(session_id, **kwargs)
        elif action == "status":
            return await self._get_status(session_id)
        return None

    async def start_new_game(self, **kwargs: Any) -> NewGameResult:
        """Full new game flow: create session, character, world, opening chapter, first quests."""
        goal_desc: str = kwargs["goal_description"]
        goal_type: str = kwargs.get("goal_type", "general")
        duration: int = kwargs.get("duration_days", 90)
        char_name: str = kwargs.get("character_name", "无名英雄")

        await self.db.initialize()
        session_id = await self.db.create_session()

        # 1. Create character
        char_class = CharacterClass.from_goal_type(goal_type)
        stats = Stats()
        stats.apply_class_bonus(char_class)
        character = Character(
            name=char_name,
            character_class=char_class,
            stats=stats,
        )
        await self.db.save_character(session_id, character)

        # Register character-bound tools
        self.register_tool(create_stat_update_tool(character))
        self.register_tool(create_add_item_tool(character))
        self.register_tool(create_calendar_tool(character))

        # 2. Create goal
        goal = Goal(
            description=goal_desc,
            goal_type=goal_type,
            duration_days=duration,
        )
        await self.db.save_goal(session_id, goal)

        # 3. Build world
        world = await self.world_builder.create_initial_world(
            session_id,
            goal_type=goal_type,
        )

        # 4. Create main quest
        main_quest = await self.task_planner.create_main_quest(session_id, goal)
        goal.main_quest = main_quest
        await self.db.save_goal(session_id, goal)

        # 5. Generate opening chapter
        char_info = self.context_assembler._format_character(character)
        world_info = self.context_assembler._format_world(world)
        opening = await self.storyteller.generate_opening(
            session_id,
            char_info,
            goal_desc,
            world_info,
        )

        # 6. Generate first day's quests
        daily_quests = await self.task_planner.run(
            session_id,
            goal=goal,
            day_count=1,
        )

        return NewGameResult(
            session_id=session_id,
            character=character,
            goal=goal,
            world=world,
            opening_chapter=opening,
            daily_quests=daily_quests,
        )

    async def daily_check_in(self, session_id: str, **kwargs: Any) -> CheckInResult:
        """Process daily check-in: evaluate, generate story, update world."""
        quests: List[Quest] = kwargs["quests"]
        character = await self.db.load_character(session_id)
        goal = await self.db.load_goal(session_id)
        world = await self.db.load_world_state(session_id)

        if not character or not goal or not world:
            raise RuntimeError("Game session data incomplete")

        # 1. Evaluate progress
        evaluation = await self.evaluator.run(
            session_id,
            quests=quests,
            streak_days=character.streak_days,
        )

        # 2. Update character
        leveled_up = character.add_xp(evaluation.xp_earned)
        hp_delta = evaluation.character_effects.get("hp_delta", 0)
        if hp_delta > 0:
            character.heal(hp_delta)
        elif hp_delta < 0:
            character.take_damage(abs(hp_delta))

        for stat, delta in evaluation.character_effects.get(
            "stat_changes", {}
        ).items():
            if hasattr(character.stats, stat):
                old = getattr(character.stats, stat)
                setattr(character.stats, stat, old + delta)

        if evaluation.completion_pct >= 50:
            character.streak_days += 1
        else:
            character.streak_days = 0
        character.total_days += 1

        await self.db.save_character(session_id, character)

        # 3. Save quest results
        for q in quests:
            await self.db.save_quest(session_id, q)

        # 4. Generate new chapter
        chapter = await self.storyteller.run(
            session_id,
            outcome_type=evaluation.outcome_type.value,
            completion_pct=evaluation.completion_pct,
            evaluation_comment=evaluation.comment,
        )

        # 5. Update world state
        world.day_count += 1
        await self.db.save_world_state(session_id, world)

        return CheckInResult(
            evaluation=evaluation,
            chapter=chapter,
            character=character,
            world=world,
            leveled_up=leveled_up,
        )

    async def generate_new_daily_quests(self, session_id: str) -> List[Quest]:
        """Generate a fresh set of daily quests."""
        goal = await self.db.load_goal(session_id)
        world = await self.db.load_world_state(session_id)
        if not goal or not world:
            raise RuntimeError("No active game session")
        return await self.task_planner.run(
            session_id,
            goal=goal,
            day_count=world.day_count,
        )

    async def _get_status(self, session_id: str) -> dict:
        character = await self.db.load_character(session_id)
        world = await self.db.load_world_state(session_id)
        goal = await self.db.load_goal(session_id)
        quests = await self.db.load_active_quests(session_id)
        chapters = await self.db.load_chapters(session_id, limit=1)
        return {
            "character": character,
            "world": world,
            "goal": goal,
            "active_quests": quests,
            "latest_chapter": chapters[0] if chapters else None,
        }
