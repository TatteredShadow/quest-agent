import pytest
from src.models.character import Character, CharacterClass, Stats, Item
from src.models.quest import Quest, Goal, Difficulty, QuestStatus, QuestType
from src.models.world import WorldState, Location, NPC
from src.models.story import Chapter, StoryArc, OutcomeType, PlotPoint
from src.tools.dice import roll_dice
from src.tools.calendar import calculate_phase


class TestCharacter:
    def test_create_character(self):
        c = Character(name="Aldric", character_class=CharacterClass.MAGE)
        assert c.name == "Aldric"
        assert c.level == 1
        assert c.hp == 100

    def test_add_xp_level_up(self):
        c = Character(name="Test", character_class=CharacterClass.WARRIOR, xp_to_next=100)
        leveled = c.add_xp(150)
        assert leveled is True
        assert c.level == 2
        assert c.xp == 50

    def test_class_from_goal(self):
        assert CharacterClass.from_goal_type("fitness") == CharacterClass.WARRIOR
        assert CharacterClass.from_goal_type("learning") == CharacterClass.MAGE
        assert CharacterClass.from_goal_type("work") == CharacterClass.RANGER
        assert CharacterClass.from_goal_type("creative") == CharacterClass.ROGUE
        assert CharacterClass.from_goal_type("unknown") == CharacterClass.WARRIOR

    def test_stats_class_bonus(self):
        stats = Stats()
        stats.apply_class_bonus(CharacterClass.MAGE)
        assert stats.intelligence == 13
        assert stats.wisdom == 12

    def test_damage_and_heal(self):
        c = Character(name="Test", character_class=CharacterClass.WARRIOR)
        c.take_damage(30)
        assert c.hp == 70
        c.heal(20)
        assert c.hp == 90
        c.heal(999)
        assert c.hp == 100


class TestQuest:
    def test_create_quest(self):
        q = Quest(title="Dragon Slayer", real_task="Run 5km")
        assert q.status == QuestStatus.ACTIVE
        assert not q.is_done

    def test_quest_done(self):
        q = Quest(title="Test", real_task="Test", status=QuestStatus.COMPLETED)
        assert q.is_done


class TestStoryArc:
    def test_add_chapter(self):
        arc = StoryArc()
        ch = Chapter(
            chapter_number=1, title="Begin", content="Story...",
            plot_points=[PlotPoint(description="Mystery clue")],
        )
        arc.add_chapter(ch)
        assert arc.current_chapter == 1
        assert len(arc.unresolved_plots) == 1

    def test_resolve_plot(self):
        arc = StoryArc()
        arc.unresolved_plots = [PlotPoint(description="X"), PlotPoint(description="Y")]
        arc.resolve_plot("X")
        assert len(arc.unresolved_plots) == 1
        assert arc.unresolved_plots[0].description == "Y"


class TestTools:
    def test_roll_dice(self):
        result = roll_dice(sides=6, modifier=2, count=3)
        assert len(result["rolls"]) == 3
        assert all(1 <= r <= 6 for r in result["rolls"])
        assert result["total"] == sum(result["rolls"]) + 2

    def test_calculate_phase(self):
        p = calculate_phase(1, 90)
        assert p["current_phase"] == 1
        assert p["phase_name"] == "启程"

        p = calculate_phase(45, 90)
        assert p["current_phase"] == 3
        assert p["phase_name"] == "深渊"


class TestWorldState:
    def test_get_npc(self):
        w = WorldState()
        w.npcs = [NPC(name="Gandalf", role="导师")]
        assert w.get_npc("Gandalf") is not None
        assert w.get_npc("Nobody") is None

    def test_get_location(self):
        w = WorldState()
        w.discovered_locations = [Location(name="Town")]
        assert w.get_location("Town") is not None
        assert w.get_location("Missing") is None
