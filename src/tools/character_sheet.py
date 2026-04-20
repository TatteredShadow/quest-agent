from __future__ import annotations

from langchain_core.tools import StructuredTool

from src.models.character import Character, Item


def update_character_stat(character: Character, stat: str, delta: int) -> str:
    """Modify a character stat by delta."""
    if hasattr(character.stats, stat):
        old = getattr(character.stats, stat)
        setattr(character.stats, stat, old + delta)
        return f"{stat}: {old} → {old + delta}"
    return f"未知属性: {stat}"


def add_item_to_inventory(
    character: Character,
    name: str,
    description: str = "",
    item_type: str = "misc",
    power: int = 0,
) -> str:
    item = Item(name=name, description=description, item_type=item_type, power=power)
    character.inventory.append(item)
    return f"获得物品：{name}"


def create_stat_update_tool(character: Character) -> StructuredTool:
    def handler(stat: str, delta: int) -> str:
        """修改角色属性值（strength/intelligence/wisdom/charisma/endurance）"""
        return update_character_stat(character, stat, delta)

    return StructuredTool.from_function(
        func=handler,
        name="update_character",
        description="修改角色属性值",
    )


def create_add_item_tool(character: Character) -> StructuredTool:
    def handler(
        name: str,
        description: str = "",
        item_type: str = "misc",
        power: int = 0,
    ) -> str:
        """向角色背包添加物品"""
        return add_item_to_inventory(character, name, description, item_type, power)

    return StructuredTool.from_function(
        func=handler,
        name="add_item",
        description="向角色背包添加物品",
    )
