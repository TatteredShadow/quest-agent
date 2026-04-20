from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class NPC(BaseModel):
    id: str = ""
    name: str
    role: str = ""              # 商人、导师、敌人、盟友 ...
    description: str = ""
    relationship: int = 50      # 0-100 好感度
    location: str = ""
    is_alive: bool = True


class Location(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    discovered: bool = False
    connected_to: List[str] = Field(default_factory=list)  # location ids
    npcs: List[str] = Field(default_factory=list)           # npc ids


class Faction(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    reputation: int = 50   # 0-100


class Threat(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    danger_level: int = 1  # 1-10
    resolved: bool = False


class WorldState(BaseModel):
    current_location: str = ""
    discovered_locations: List[Location] = Field(default_factory=list)
    npcs: List[NPC] = Field(default_factory=list)
    factions: List[Faction] = Field(default_factory=list)
    active_threats: List[Threat] = Field(default_factory=list)
    resolved_threats: List[Threat] = Field(default_factory=list)
    day_count: int = 1
    world_seed: str = ""

    def get_location(self, name: str) -> Optional[Location]:
        for loc in self.discovered_locations:
            if loc.name == name:
                return loc
        return None

    def get_npc(self, name: str) -> Optional[NPC]:
        for npc in self.npcs:
            if npc.name == name:
                return npc
        return None
