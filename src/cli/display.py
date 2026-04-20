from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.columns import Columns
from rich.text import Text
from rich import box

from src.models.character import Character
from src.models.quest import Quest
from src.models.story import Chapter, OutcomeType
from src.models.world import WorldState

console = Console()


def show_title() -> None:
    title = Text()
    title.append("\n  Quest Agent  \n", style="bold white on dark_red")
    title.append("  故事驱动的目标追踪系统  ", style="italic dim")
    console.print(Panel(title, box=box.DOUBLE, border_style="red"))


def show_chapter(chapter: Chapter) -> None:
    outcome_colors = {
        OutcomeType.TRIUMPH: "bold green",
        OutcomeType.ADVANCE: "blue",
        OutcomeType.SETBACK: "yellow",
        OutcomeType.CRISIS: "bold red",
        OutcomeType.MILESTONE: "bold magenta",
        OutcomeType.BONUS: "bold cyan",
    }
    color = outcome_colors.get(chapter.outcome_type, "white")
    header = f"第{chapter.chapter_number}章：{chapter.title}"
    console.print()
    console.print(Panel(
        Markdown(chapter.content),
        title=f"[{color}]{header}[/{color}]",
        subtitle=f"[dim]{chapter.outcome_type.display_name}[/dim]",
        border_style=color.replace("bold ", ""),
        box=box.ROUNDED,
        padding=(1, 2),
    ))


def show_character_sheet(character: Character) -> None:
    table = Table(title=f"{character.name} - {character.character_class.display_name}",
                  box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("属性", style="bold")
    table.add_column("值", justify="right")

    table.add_row("称号", character.title)
    table.add_row("等级", str(character.level))
    table.add_row("经验", f"{character.xp}/{character.xp_to_next}")

    hp_ratio = character.hp / character.max_hp if character.max_hp else 0
    hp_color = "green" if hp_ratio > 0.6 else "yellow" if hp_ratio > 0.3 else "red"
    table.add_row("生命", f"[{hp_color}]{character.hp}/{character.max_hp}[/{hp_color}]")
    table.add_row("", "")
    table.add_row("[bold]力量[/bold]", str(character.stats.strength))
    table.add_row("[bold]智力[/bold]", str(character.stats.intelligence))
    table.add_row("[bold]感知[/bold]", str(character.stats.wisdom))
    table.add_row("[bold]魅力[/bold]", str(character.stats.charisma))
    table.add_row("[bold]耐力[/bold]", str(character.stats.endurance))
    table.add_row("", "")
    table.add_row("连续打卡", f"{character.streak_days} 天")
    table.add_row("总天数", f"{character.total_days} 天")

    if character.inventory:
        items_str = ", ".join(i.name for i in character.inventory)
        table.add_row("", "")
        table.add_row("[bold]背包[/bold]", items_str)

    console.print(table)


def show_quests(quests: List[Quest], title: str = "今日任务") -> None:
    table = Table(title=title, box=box.ROUNDED, border_style="yellow")
    table.add_column("#", style="dim", width=3)
    table.add_column("任务", style="bold")
    table.add_column("实际内容", style="dim")
    table.add_column("难度", justify="center")
    table.add_column("XP", justify="right", style="green")
    table.add_column("状态", justify="center")

    diff_colors = {"简单": "green", "中等": "yellow", "困难": "red"}

    for i, q in enumerate(quests, 1):
        diff_name = q.difficulty.display_name
        status_icon = {
            "active": "[ ]",
            "completed": "[green][x][/green]",
            "failed": "[red][!][/red]",
            "skipped": "[dim][-][/dim]",
        }.get(q.status.value, "?")

        table.add_row(
            str(i),
            q.title,
            q.real_task,
            f"[{diff_colors.get(diff_name, 'white')}]{diff_name}[/{diff_colors.get(diff_name, 'white')}]",
            str(q.xp_reward),
            status_icon,
        )
    console.print(table)


def show_world_status(world: WorldState) -> None:
    panel_content = Text()
    panel_content.append(f"当前位置：{world.current_location}\n", style="bold cyan")
    panel_content.append(f"游戏日：第 {world.day_count} 天\n\n")

    if world.discovered_locations:
        panel_content.append("已探索地点：", style="bold")
        panel_content.append(", ".join(l.name for l in world.discovered_locations) + "\n")

    if world.npcs:
        panel_content.append("\nNPC：\n", style="bold")
        for npc in world.npcs:
            rel_color = "green" if npc.relationship >= 70 else "yellow" if npc.relationship >= 40 else "red"
            panel_content.append(f"  {npc.name} ({npc.role}) ")
            panel_content.append(f"好感度 {npc.relationship}\n", style=rel_color)

    if world.active_threats:
        panel_content.append("\n当前威胁：\n", style="bold red")
        for t in world.active_threats:
            panel_content.append(f"  {t.name} - 危险等级 {t.danger_level}\n", style="red")

    console.print(Panel(panel_content, title="世界状态", border_style="magenta", box=box.ROUNDED))


def show_evaluation(completion_pct: int, outcome: str, comment: str,
                    xp: int, streak: int, leveled_up: bool) -> None:
    outcome_display = {
        "triumph": ("[bold green]", "大获成功"),
        "advance": ("[blue]", "稳步推进"),
        "setback": ("[yellow]", "小遇挫折"),
        "crisis": ("[bold red]", "危机降临"),
    }
    style, label = outcome_display.get(outcome, ("[white]", outcome))

    console.print()
    console.print(f"  完成度：{style}{completion_pct}%[/]  |  结果：{style}{label}[/]")
    console.print(f"  获得经验：[green]+{xp} XP[/green]  |  连续打卡：[cyan]{streak} 天[/cyan]")
    if comment:
        console.print(f"  评语：[italic]{comment}[/italic]")
    if leveled_up:
        console.print("  [bold magenta]*** 等级提升！ ***[/bold magenta]")
    console.print()
