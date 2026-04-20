from __future__ import annotations

from typing import Dict, List

from src.memory.database import Database
from src.models.character import Character
from src.models.world import WorldState
from src.models.story import Chapter


class ContextAssembler:
    """Assembles context for story generation from multiple memory sources.

    When an embedding function is configured on the Database, the assembler
    uses **semantic similarity search** to retrieve the most relevant past
    chapters and key facts rather than simply fetching the most recent ones.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def build_story_context(self, session_id: str) -> Dict[str, str]:
        """Build context dict for StoryTeller with semantically relevant history."""
        character = await self.db.load_character(session_id)
        world = await self.db.load_world_state(session_id)

        char_info = self._format_character(character) if character else "无角色数据"
        world_info = self._format_world(world) if world else "无世界数据"

        search_query = f"{char_info}\n{world_info}"

        relevant_chapters = await self.db.search_similar_chapters(
            session_id, query=search_query, limit=3
        )
        if not relevant_chapters:
            relevant_chapters = await self.db.load_chapters(session_id, limit=2)

        relevant_facts = await self.db.search_relevant_facts(
            session_id, query=search_query, limit=5
        )
        if not relevant_facts:
            relevant_facts = await self.db.load_unresolved_facts(session_id)

        return {
            "character_info": char_info,
            "world_state": world_info,
            "previous_summary": self._format_chapters(relevant_chapters),
            "unresolved_plots": self._format_facts(relevant_facts),
        }

    def _format_character(self, c: Character) -> str:
        items = ", ".join(i.name for i in c.inventory) or "空"
        return (
            f"姓名：{c.name}  职业：{c.character_class.display_name}  称号：{c.title}\n"
            f"等级：{c.level}  经验：{c.xp}/{c.xp_to_next}  生命：{c.hp}/{c.max_hp}\n"
            f"属性：力量{c.stats.strength} 智力{c.stats.intelligence} "
            f"感知{c.stats.wisdom} 魅力{c.stats.charisma} 耐力{c.stats.endurance}\n"
            f"背包：{items}\n"
            f"连续打卡：{c.streak_days}天  总天数：{c.total_days}天"
        )

    def _format_world(self, w: WorldState) -> str:
        locs = ", ".join(loc.name for loc in w.discovered_locations) or "未知"
        npcs = (
            "; ".join(f"{n.name}({n.role}, 好感{n.relationship})" for n in w.npcs)
            or "无"
        )
        threats = ", ".join(t.name for t in w.active_threats) or "暂无威胁"
        return (
            f"当前位置：{w.current_location}\n"
            f"已探索：{locs}\n"
            f"NPC：{npcs}\n"
            f"当前威胁：{threats}\n"
            f"游戏日：第{w.day_count}天"
        )

    def _format_chapters(self, chapters: List[Chapter]) -> str:
        if not chapters:
            return "这是故事的开端。"
        parts = []
        for ch in chapters:
            summary = ch.summary or ch.content[:100] + "..."
            parts.append(f"第{ch.chapter_number}章「{ch.title}」：{summary}")
        return "\n".join(parts)

    def _format_facts(self, facts: List[Dict]) -> str:
        if not facts:
            return "无未解决线索。"
        return "\n".join(f"- [{f['type']}] {f['content']}" for f in facts)
