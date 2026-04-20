from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.llm import prompts
from src.models.world import WorldState, Location, NPC, Faction, Threat

logger = logging.getLogger(__name__)


class WorldBuilderAgent(BaseAgent):
    """Creates and maintains the fantasy world state."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(system_prompt=prompts.SYSTEM_WORLD_BUILDER, **kwargs)

    async def run(self, session_id: str, **kwargs: Any) -> WorldState:
        """Update world based on story events."""
        world = await self.db.load_world_state(session_id)
        if not world:
            return await self.create_initial_world(session_id, **kwargs)

        changes: dict = kwargs.get("world_changes", {})
        if not changes:
            return world

        for npc_data in changes.get("new_npcs", []):
            if isinstance(npc_data, dict):
                world.npcs.append(NPC(**npc_data))

        for loc_data in changes.get("new_locations", []):
            if isinstance(loc_data, dict):
                world.discovered_locations.append(
                    Location(**loc_data, discovered=True)
                )

        for npc_name, delta in changes.get("npc_relationship_changes", {}).items():
            npc = world.get_npc(npc_name)
            if npc:
                npc.relationship = max(0, min(100, npc.relationship + delta))

        for threat_data in changes.get("new_threats", []):
            if isinstance(threat_data, dict):
                world.active_threats.append(Threat(**threat_data))

        for threat_name in changes.get("resolved_threats", []):
            for t in world.active_threats:
                if t.name == threat_name:
                    t.resolved = True
                    world.resolved_threats.append(t)
            world.active_threats = [t for t in world.active_threats if not t.resolved]

        world.day_count += 1
        await self.db.save_world_state(session_id, world)
        return world

    async def create_initial_world(
        self, session_id: str, **kwargs: Any
    ) -> WorldState:
        """Generate the initial world setting."""
        goal_type = kwargs.get("goal_type", "general")
        story_style = self.config.game.story_style

        result = await self.think_json(
            prompts.PROMPT_BUILD_WORLD,
            goal_type=goal_type,
            story_style=story_style,
            current_world="（空白世界，需要从零创建）",
        )

        start_loc_data = result.get("starting_location", {})
        start_loc = Location(
            name=start_loc_data.get("name", "起始之地"),
            description=start_loc_data.get("description", ""),
            discovered=True,
        )

        npcs = []
        for npc_data in result.get("initial_npcs", []):
            npcs.append(
                NPC(
                    name=npc_data.get("name", ""),
                    role=npc_data.get("role", ""),
                    description=npc_data.get("description", ""),
                    location=npc_data.get("location", start_loc.name),
                )
            )

        factions = []
        for f_data in result.get("factions", []):
            factions.append(
                Faction(
                    name=f_data.get("name", ""),
                    description=f_data.get("description", ""),
                )
            )

        threat_data = result.get("initial_threat", {})
        threats = []
        if threat_data:
            threats.append(
                Threat(
                    name=threat_data.get("name", ""),
                    description=threat_data.get("description", ""),
                    danger_level=threat_data.get("danger_level", 3),
                )
            )

        world = WorldState(
            current_location=start_loc.name,
            discovered_locations=[start_loc],
            npcs=npcs,
            factions=factions,
            active_threats=threats,
            day_count=1,
            world_seed=result.get("world_theme", ""),
        )

        await self.db.save_world_state(session_id, world)
        return world
