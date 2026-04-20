from __future__ import annotations

import asyncio
from datetime import date

import click
from rich.console import Console
from rich.prompt import Prompt, IntPrompt

from src.agents.game_master import GameMasterAgent
from src.cli.display import (
    show_title,
    show_chapter,
    show_character_sheet,
    show_quests,
    show_world_status,
    show_evaluation,
)
from src.llm.client import create_llm
from src.memory.database import Database
from src.models.quest import QuestStatus
from src.utils.config import load_config

console = Console()


def _create_game_master() -> GameMasterAgent:
    config = load_config()
    llm = create_llm(config.llm)
    db = Database(config)
    return GameMasterAgent(llm=llm, db=db, config=config)


@click.group()
def cli():
    """Quest Agent - 故事驱动的目标追踪系统"""
    pass


@cli.command()
def new():
    """开启一段新的冒险"""
    show_title()
    console.print("\n[bold]欢迎，冒险者！[/bold]")
    console.print("在开始你的奇幻冒险之前，告诉我你在现实中想要达成什么目标。\n")

    goal_desc = Prompt.ask("[bold cyan]你的目标是什么[/bold cyan]")

    console.print("\n选择目标类型：")
    console.print("  [1] 健身运动 (对应职业：战士)")
    console.print("  [2] 学习成长 (对应职业：法师)")
    console.print("  [3] 工作事业 (对应职业：游侠)")
    console.print("  [4] 创意创作 (对应职业：盗贼)")
    console.print("  [5] 其他 (默认：战士)")

    type_choice = IntPrompt.ask("选择", default=5)
    goal_type_map = {1: "fitness", 2: "learning", 3: "work", 4: "creative", 5: "general"}
    goal_type = goal_type_map.get(type_choice, "general")

    duration = IntPrompt.ask("目标持续天数", default=90)
    char_name = Prompt.ask("给你的角色取个名字", default="无名英雄")

    console.print("\n[dim]正在创建你的冒险世界...[/dim]\n")

    gm = _create_game_master()

    with console.status("[bold green]世界构建中..."):
        result = asyncio.run(
            gm.start_new_game(
                goal_description=goal_desc,
                goal_type=goal_type,
                duration_days=duration,
                character_name=char_name,
            )
        )

    console.print(
        f"\n[bold green]冒险开始！[/bold green] 存档 ID: [cyan]{result.session_id}[/cyan]\n"
    )

    show_character_sheet(result.character)
    show_world_status(result.world)
    show_chapter(result.opening_chapter)
    show_quests(result.daily_quests)

    console.print("\n[dim]使用 [bold]quest check-in[/bold] 来汇报今日进度[/dim]")


@cli.command(name="check-in")
def check_in():
    """每日进度签到"""
    gm = _create_game_master()
    db = gm.db

    session_id = asyncio.run(db.get_active_session())
    if not session_id:
        console.print("[red]没有进行中的冒险。请先运行 quest new 开始新冒险。[/red]")
        return

    today_str = date.today().isoformat()
    quests = asyncio.run(db.load_daily_quests_today(session_id, today_str))

    if not quests:
        console.print("[dim]今天还没有任务，正在生成...[/dim]")
        with console.status("[bold green]生成今日任务..."):
            quests = asyncio.run(gm.generate_new_daily_quests(session_id))

    show_quests(quests)
    console.print("\n[bold]汇报你的任务完成情况：[/bold]\n")

    for i, q in enumerate(quests):
        console.print(f"  [{i+1}] {q.title}（{q.real_task}）")
        console.print("      [1] 完成  [2] 部分完成  [3] 跳过")
        choice = IntPrompt.ask(f"      任务 {i+1} 状态", default=1)
        if choice == 1:
            q.status = QuestStatus.COMPLETED
            q.completion_pct = 100
        elif choice == 2:
            pct = IntPrompt.ask("      完成百分比", default=50)
            q.status = QuestStatus.COMPLETED
            q.completion_pct = min(99, max(1, pct))
        else:
            q.status = QuestStatus.SKIPPED
            q.completion_pct = 0

    console.print("\n[dim]评估中...[/dim]")

    with console.status("[bold green]生成新的故事章节..."):
        result = asyncio.run(gm.daily_check_in(session_id, quests=quests))

    show_evaluation(
        result.evaluation.completion_pct,
        result.evaluation.outcome_type.value,
        result.evaluation.comment,
        result.evaluation.xp_earned,
        result.character.streak_days,
        result.leveled_up,
    )
    show_chapter(result.chapter)
    show_character_sheet(result.character)


@cli.command()
def story():
    """查看最新故事章节"""
    db = Database(load_config())
    session_id = asyncio.run(db.get_active_session())
    if not session_id:
        console.print("[red]没有进行中的冒险。[/red]")
        return

    chapters = asyncio.run(db.load_chapters(session_id))
    if not chapters:
        console.print("[dim]还没有故事章节。[/dim]")
        return

    for ch in chapters:
        show_chapter(ch)


@cli.command()
def status():
    """查看角色状态和世界信息"""
    db = Database(load_config())
    session_id = asyncio.run(db.get_active_session())
    if not session_id:
        console.print("[red]没有进行中的冒险。[/red]")
        return

    character = asyncio.run(db.load_character(session_id))
    world = asyncio.run(db.load_world_state(session_id))
    quests = asyncio.run(db.load_active_quests(session_id))

    if character:
        show_character_sheet(character)
    if world:
        show_world_status(world)
    if quests:
        show_quests(quests, title="进行中的任务")


@cli.command()
def history():
    """浏览所有历史章节"""
    db = Database(load_config())
    session_id = asyncio.run(db.get_active_session())
    if not session_id:
        console.print("[red]没有进行中的冒险。[/red]")
        return

    chapters = asyncio.run(db.load_chapters(session_id))
    if not chapters:
        console.print("[dim]还没有故事章节。[/dim]")
        return

    console.print(f"\n[bold]共 {len(chapters)} 个章节[/bold]\n")
    for ch in chapters:
        console.print(
            f"  第{ch.chapter_number}章：{ch.title} [{ch.outcome_type.display_name}]"
        )

    console.print()
    num = IntPrompt.ask("输入章节号查看详情（0 查看全部）", default=0)
    if num == 0:
        for ch in chapters:
            show_chapter(ch)
    else:
        target = [ch for ch in chapters if ch.chapter_number == num]
        if target:
            show_chapter(target[0])
        else:
            console.print(f"[red]章节 {num} 不存在[/red]")


@cli.command()
def config():
    """查看和修改配置"""
    cfg = load_config()
    Panel_config(cfg)


def Panel_config(cfg) -> str:
    from rich.panel import Panel

    text = (
        f"LLM 提供商: {cfg.llm.provider}\n"
        f"模型: {cfg.llm.model}\n"
        f"备用模型: {cfg.llm.fallback_model}\n"
        f"API Key 环境变量: {cfg.llm.api_key_env}\n"
        f"Temperature: {cfg.llm.temperature}\n"
        f"\n"
        f"游戏难度: {cfg.game.difficulty}\n"
        f"故事风格: {cfg.game.story_style}\n"
        f"语言: {cfg.game.language}\n"
    )
    console.print(Panel(text, title="当前配置", border_style="cyan"))
    console.print("[dim]编辑 config.yaml 文件修改配置[/dim]")
    return ""
