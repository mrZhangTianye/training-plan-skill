# -*- coding: utf-8 -*-
"""单课时长模型：时长由剂量算出来，人工不再维护 duration_minutes。

口径（力量教练给出的公式，收敛为唯一实现）：
    单动作 = 组数×单组工作秒 + (组数−1)×组间休息秒
单组工作按优先级取：
    1. 目标 RPE ≥ 7 的计次动作：次数×5 秒（重负荷每次耗时更长）
    2. 资产表/备注已给出整组工作秒（`work_seconds_per_set`，如「3 次呼吸约 9 秒/次」）：直接用
    3. 有时长字段：时长
    4. 技术/低强度计次：次数×4 秒
    5. 计距：距离÷1.3 米/秒
`per_side` 的动作用时翻倍。起跑、收尾、准备段本来就是整课时间的一部分，不额外叠加。
"""
METRES_PER_SECOND = 1.3
REP_SECONDS_HARD = 5.0
REP_SECONDS_TECH = 4.0


def target_rpe(item):
    value = (item['dose'].get('load') or {}).get('target_rpe')
    return None if value is None else float(value)


def per_set_seconds(item):
    from work_timing import whole_set_seconds

    dose = item['dose']
    sides = 2 if dose.get('per_side') else 1
    rpe = target_rpe(item)
    if dose.get('reps') is not None and rpe is not None and rpe >= 7:
        return dose['reps'] * REP_SECONDS_HARD * sides
    known = whole_set_seconds(item)
    if known is not None:
        return known
    if dose.get('duration_minutes') is not None:
        return dose['duration_minutes'] * 60 * sides
    if dose.get('reps') is not None:
        return dose['reps'] * REP_SECONDS_TECH * sides
    if dose.get('distance_m') is not None:
        return dose['distance_m'] / METRES_PER_SECOND * sides
    return 0.0


def item_seconds(item):
    dose = item['dose']
    sets = dose.get('sets') or 1
    rest = dose.get('rest_seconds') or 0
    return sets * per_set_seconds(item) + max(sets - 1, 0) * rest


def session_minutes(session):
    return round(sum(item_seconds(x) for m in session['modules'] for x in m['items']) / 60.0, 2)


def apply(plan, kinds=('strength',)):
    """把算出来的时长写回 items→modules→session，三层和保持相等。"""
    changed = []
    for s in plan['sessions']:
        if s['kind'] not in kinds:
            continue
        before = s.get('duration_minutes')
        for m in s['modules']:
            for x in m['items']:
                x['duration_minutes'] = round(item_seconds(x) / 60.0, 2)
            m['duration_minutes'] = round(sum(x['duration_minutes'] for x in m['items']), 2)
        s['duration_minutes'] = round(sum(m['duration_minutes'] for m in s['modules']), 2)
        if before != s['duration_minutes']:
            changed.append((s['id'], before, s['duration_minutes']))
    return changed
