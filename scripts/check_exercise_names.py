#!/usr/bin/env python3
"""核对 references/exercise-names.md 与动作库的一致性。

为什么需要它：对照表的「现用中文名」一列按约定就是动作库 name 的原值，写课表时按名匹配。
行里没有库 id、或名字和库里不一致时，表面上仍是一张整齐的表，实际已经和库脱钩——
写课表的人照着表写，脚本按库匹配，两边对不上。这类错误肉眼扫一遍看不出来。

用法：
    python scripts/check_exercise_names.py
    python scripts/check_exercise_names.py --doc references/exercise-names.md

退出码：0 = 可核项全部一致且无疑似自造名；1 = 有未知 id／名称不符／无 id 的自造名。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_plan import library  # noqa: E402

SEP = re.compile(r"^:?-{2,}:?$")
ID = re.compile(r"`([A-Za-z0-9_.-]+)`")
NOT_IN_LIB = "not_in_library"  # 书里有、库内确认无此动作的显式声明
HEADER = {"书译名", "英文", "skill id", "包内 id", "现用中文名", "书页", "原书动作", "说明"}


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def clean(cell: str) -> str:
    return cell.replace("**", "").replace("`", "").strip()


def is_blank(cell: str) -> bool:
    c = clean(cell)
    if c in ("", "-", "未收录", "待核"):
        return True
    return c[0] in "—–"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=str(ROOT / "references" / "exercise-names.md"))
    args = ap.parse_args()

    doc = Path(args.doc)
    if not doc.exists():
        print(f"找不到对照表：{doc}")
        return 1

    lib = library()
    by_name: dict[str, list[str]] = {}
    for uid, unit in lib.items():
        by_name.setdefault(unit.get("name", ""), []).append(uid)

    unknown: list[str] = []
    mismatch: list[str] = []
    missing_name: list[str] = []
    orphan: list[str] = []
    resolvable: list[str] = []
    declared: list[str] = []
    checked = 0

    for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) < 3 or all(SEP.match(c.strip()) for c in cells if c.strip()):
            continue

        if HEADER & {clean(c) for c in cells}:
            continue  # 表头行不是数据行
        if any(clean(c) == NOT_IN_LIB for c in cells):
            declared.append(f"  第 {lineno} 行「{clean(cells[0])}」已声明库内无（not_in_library）")
            continue

        id_idx = next((i for i, c in enumerate(cells) if ID.search(c)), None)
        if id_idx is None:
            cand = clean(cells[-2]) if len(cells) >= 2 else ""
            if is_blank(cand):
                continue
            if cand in by_name:
                resolvable.append(f"  第 {lineno} 行「{cand}」库里存在，可补 id：{'/'.join(by_name[cand])}")
            else:
                orphan.append(f"  第 {lineno} 行「{cand}」无库 id，库里也没有同名条目")
            continue

        ids = ID.findall(cells[id_idx])
        name_cell = cells[id_idx + 1] if id_idx + 1 < len(cells) else ""
        for uid in ids:
            checked += 1
            if uid not in lib:
                unknown.append(f"  第 {lineno} 行 id `{uid}` 不在动作库")
                continue
            if is_blank(name_cell):
                missing_name.append(f"  第 {lineno} 行 `{uid}` 现用名一列为空（库名：{lib[uid].get('name')}）")
                continue
            if clean(name_cell) != lib[uid].get("name"):
                mismatch.append(
                    f"  第 {lineno} 行 `{uid}` 表里写「{clean(name_cell)}」，库里是「{lib[uid].get('name')}」"
                )

    print(f"对照表：{doc.name}｜库条目：{len(lib)}｜checked id：{checked}")
    for title, items in (
        ("未知 id（表里写了库里没有的动作）", unknown),
        ("名称与库不一致（写课表会发生匹配串台）", mismatch),
        ("有 id 但现用名留空", missing_name),
        ("无库 id 且库中无同名条目（疑似自造名）", orphan),
    ):
        if items:
            print(f"\n{title}：{len(items)}")
            print("\n".join(items))
    if declared:
        print(f"\n已显式声明库内无（不计为错误）：{len(declared)}")
        print("\n".join(declared))
    if resolvable:
        print(f"\n无 id 但库中已有同名条目（补 id 即可）：{len(resolvable)}")
        print("\n".join(resolvable))

    bad = len(unknown) + len(mismatch) + len(orphan)
    if bad:
        print(f"\n结果：{bad} 处必须改。表里的「现用中文名」只能填库 name 原值；无 id 的行不能自称现用名。")
        return 1
    if missing_name or resolvable:
        print("\n结果：名称一致，但有空名或可补 id 的行；声明「已在库与本表统一」前先补齐。")
        return 0
    print("\n结果：全部可核项一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
