"""
Simulate a 10-day adventure with varying daily completion levels.
Outputs a structured markdown report.
"""
import asyncio
import sys
from datetime import datetime

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.agents.game_master import GameMasterAgent
from src.llm.client import create_llm
from src.memory.database import Database
from src.models.quest import QuestStatus
from src.utils.config import load_config

DAILY_SCENARIOS = [
    {"day": 1,  "label": "首日热情",   "completions": [100, 100, 100]},
    {"day": 2,  "label": "稳步推进",   "completions": [100, 80, 100]},
    {"day": 3,  "label": "略有松懈",   "completions": [100, 50, 0]},
    {"day": 4,  "label": "状态回升",   "completions": [100, 100, 80]},
    {"day": 5,  "label": "遭遇低谷",   "completions": [30, 0, 0]},
    {"day": 6,  "label": "触底反弹",   "completions": [100, 100, 100]},
    {"day": 7,  "label": "稳中有进",   "completions": [100, 70, 100]},
    {"day": 8,  "label": "再次懈怠",   "completions": [50, 40, 0]},
    {"day": 9,  "label": "奋起直追",   "completions": [100, 100, 100]},
    {"day": 10, "label": "最终冲刺",   "completions": [100, 100, 100]},
]


def pct_to_status(pct):
    if pct >= 80:
        return QuestStatus.COMPLETED
    elif pct > 0:
        return QuestStatus.COMPLETED
    else:
        return QuestStatus.SKIPPED


async def main():
    config = load_config()
    llm = create_llm(config.llm)
    db = Database(config)
    gm = GameMasterAgent(llm=llm, db=db, config=config)

    report = []
    report.append("# Quest Agent 10 天冒险记录\n")
    report.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # ── Day 0: New Game ──
    print("=== Creating new game ===")
    result = await gm.start_new_game(
        goal_description="每天坚持跑步5公里，10天内养成运动习惯",
        goal_type="fitness",
        duration_days=10,
        character_name="凯尔",
    )
    session_id = result.session_id
    print(f"Session: {session_id}")

    report.append("## 冒险设定\n")
    report.append("- **目标**：每天坚持跑步5公里，10天内养成运动习惯")
    report.append(f"- **角色**：{result.character.name}（{result.character.character_class.display_name}）")
    report.append(f"- **起始位置**：{result.world.current_location}")
    npc_list = ", ".join(f"{n.name}({n.role})" for n in result.world.npcs)
    report.append(f"- **NPC**：{npc_list}")
    threat_list = ", ".join(t.name for t in result.world.active_threats)
    report.append(f"- **当前威胁**：{threat_list}")
    report.append("")

    report.append("---\n")
    report.append(f"## 第1章：{result.opening_chapter.title}\n")
    report.append(result.opening_chapter.content)
    report.append("")

    report.append("### 首日任务\n")
    report.append("| # | 任务名称 | 实际内容 | 难度 | XP |")
    report.append("|---|----------|----------|------|----|")
    for i, q in enumerate(result.daily_quests, 1):
        report.append(f"| {i} | {q.title} | {q.real_task} | {q.difficulty.display_name} | {q.xp_reward} |")
    report.append("")

    # ── Day 1-10: Daily Check-ins ──
    for scenario in DAILY_SCENARIOS:
        day = scenario["day"]
        label = scenario["label"]
        completions = scenario["completions"]

        print(f"\n=== Day {day}: {label} ===")

        quests = await gm.generate_new_daily_quests(session_id)
        print(f"  Generated {len(quests)} quests")

        for i, q in enumerate(quests):
            pct = completions[i] if i < len(completions) else completions[-1]
            q.completion_pct = pct
            q.status = pct_to_status(pct)

        try:
            ci = await gm.daily_check_in(session_id, quests=quests)
        except Exception as e:
            print(f"  ERROR: {e}")
            report.append(f"\n### 第{day}天：{label} (错误)\n")
            report.append(f"签到过程出错：{e}\n")
            continue

        ev = ci.evaluation
        ch = ci.chapter
        char = ci.character

        print(f"  Completion: {ev.completion_pct}% | Outcome: {ev.outcome_type.value} | XP: {ev.xp_earned}")
        print(f"  Chapter: {ch.title}")
        print(f"  Level: {char.level} | XP: {char.xp}/{char.xp_to_next} | Streak: {char.streak_days}")

        report.append("\n---\n")
        report.append(f"## 第{day}天：{label}\n")

        report.append("### 任务完成情况\n")
        report.append("| # | 任务 | 实际内容 | 完成度 | 状态 |")
        report.append("|---|------|----------|--------|------|")
        for i, q in enumerate(quests, 1):
            status_icon = {"completed": "完成", "skipped": "跳过", "failed": "失败"}.get(q.status.value, "?")
            report.append(f"| {i} | {q.title} | {q.real_task} | {q.completion_pct}% | {status_icon} |")
        report.append("")

        report.append("### 评估结果\n")
        report.append(f"- **完成度**：{ev.completion_pct}%")
        report.append(f"- **结果**：{ev.outcome_type.display_name}")
        report.append(f"- **获得经验**：+{ev.xp_earned} XP")
        report.append(f"- **评语**：{ev.comment}")
        if ci.leveled_up:
            report.append("- **等级提升！**")
        report.append("")

        report.append("### 角色状态\n")
        report.append(f"- 等级：{char.level} | 经验：{char.xp}/{char.xp_to_next} | 生命：{char.hp}/{char.max_hp}")
        report.append(f"- 连续打卡：{char.streak_days} 天 | 总天数：{char.total_days} 天")
        report.append("")

        report.append(f"### 第{ch.chapter_number}章：{ch.title}\n")
        report.append(ch.content)
        report.append("")

    # ── Summary ──
    final_char = await db.load_character(session_id)
    all_chapters = await db.load_chapters(session_id)

    report.append("\n---\n")
    report.append("## 冒险总结\n")
    report.append(f"- **最终等级**：{final_char.level}")
    report.append(f"- **总经验**：{final_char.xp}/{final_char.xp_to_next}")
    report.append(f"- **最终生命**：{final_char.hp}/{final_char.max_hp}")
    report.append("- **最长连续打卡**：统计见下")
    report.append(f"- **总天数**：{final_char.total_days} 天")
    report.append(f"- **总章节数**：{len(all_chapters)}")
    report.append("")

    report.append("### 章节目录\n")
    report.append("| 章节 | 标题 | 结果 |")
    report.append("|------|------|------|")
    for ch in all_chapters:
        report.append(f"| 第{ch.chapter_number}章 | {ch.title} | {ch.outcome_type.display_name} |")
    report.append("")

    report.append("### 每日完成度趋势\n")
    report.append("```")
    for s in DAILY_SCENARIOS:
        avg = sum(s["completions"]) / len(s["completions"])
        bar_len = int(avg / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        report.append(f"Day {s['day']:>2} {s['label']}  {bar} {avg:.0f}%")
    report.append("```\n")

    md_path = "d:\\agent\\adventure_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n=== Report saved to {md_path} ===")


if __name__ == "__main__":
    asyncio.run(main())
