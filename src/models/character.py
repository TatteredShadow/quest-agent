from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class CharacterClass(str, Enum):
    WARRIOR = "warrior"
    MAGE = "mage"
    RANGER = "ranger"
    ROGUE = "rogue"

    @property
    def display_name(self) -> str:
        return {
            "warrior": "战士",
            "mage": "法师",
            "ranger": "游侠",
            "rogue": "盗贼",
        }[self.value]

    @classmethod
    def from_goal_type(cls, goal_type: str) -> CharacterClass:
        mapping = {
            "fitness": cls.WARRIOR,
            "learning": cls.MAGE,
            "work": cls.RANGER,
            "creative": cls.ROGUE,
        }
        return mapping.get(goal_type, cls.WARRIOR)


class Stats(BaseModel):
    strength: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    endurance: int = 10

    def apply_class_bonus(self, char_class: CharacterClass) -> None:
        bonuses = {
            CharacterClass.WARRIOR: {"strength": 3, "endurance": 2},
            CharacterClass.MAGE: {"intelligence": 3, "wisdom": 2},
            CharacterClass.RANGER: {"wisdom": 2, "endurance": 2, "strength": 1},
            CharacterClass.ROGUE: {"charisma": 3, "intelligence": 2},
        }
        for stat, bonus in bonuses.get(char_class, {}).items():
            setattr(self, stat, getattr(self, stat) + bonus)


class Item(BaseModel):
    name: str
    description: str = ""
    item_type: str = "misc"  # weapon / armor / potion / misc / quest_item
    power: int = 0


class Skill(BaseModel):
    name: str
    description: str = ""
    level_required: int = 1
    unlocked: bool = False


class Character(BaseModel):
    id: str = ""
    name: str
    character_class: CharacterClass
    level: int = 1
    xp: int = 0
    xp_to_next: int = 500
    hp: int = 100
    max_hp: int = 100
    stats: Stats = Field(default_factory=Stats)
    inventory: List[Item] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    streak_days: int = 0
    total_days: int = 0
    title: str = "冒险者"

    def add_xp(self, amount: int) -> bool:
        """Add XP and return True if leveled up."""
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = int(self.xp_to_next * 1.2)
            self.max_hp += 10
            self.hp = self.max_hp
            leveled = True
        return leveled

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)
