# -*- coding: utf-8 -*-
"""Check structure and declared timing; never certify adaptation or safety."""
import argparse
import datetime as dt
import json
import re
import sys
from common import ROOT, read_json, schema_errors, library
from design_checks import check as design_check, item_capabilities
from aerobic_stats import calculate as calculate_aerobic
from group_schedule import sequence, schedule
from endurance_stats import calculate as calculate_endurance, check as check_endurance
from work_timing import whole_set_seconds, check as check_timing, summary as timing_summary
from asset_checks import check as check_asset
from session_summary import summary_drift, timing_audit
from duration_model import per_set_seconds
from ball_constraints import check as check_ball
from swim_contract import check as check_swim_contract


def work_seconds(item):
    """Whole-set estimate includes all sides; dose time is per side when declared."""
    return whole_set_seconds(item)


def week_scope(message, date_week, sessions):
    """缺口属于哪一周：能定位到具体周就只拦那一周，定位不到算计划层面。"""
    m = re.match(r'^W(\d{1,2})[-_]', message)
    if m:
        return int(m.group(1))
    m = re.search(r'week (\d+)', message)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', message)
    if m and m.group(1) in date_week:
        return date_week[m.group(1)]
    m = re.match(r'^([A-Za-z][A-Za-z0-9_-]*)/', message)
    if m and m.group(1) in sessions:
        return sessions[m.group(1)]['week_number']
    return None


def validate(p):
    errors = schema_errors(p, read_json(ROOT / 'schemas/plan.schema.json'))
    review, insufficient = [], []
    if errors:
        return {'errors': errors, 'review_items': review, 'insufficient_basis': [], 'review_requirements': [], 'ready_weeks': [], 'aerobic_summary': None, 'deterministic_pass': False, 'ready_to_render_executable': False}
    assets = library()
    swim_errors, swim_missing = check_swim_contract(p, assets)
    errors.extend(swim_errors)
    insufficient.extend(swim_missing)
    start, n = dt.date.fromisoformat(p['start_date']), p['duration_weeks']
    goals = {g['id'] for g in p['objectives']}
    blocks = {b['id']: b for b in p['blocks']}
    sessions = {s['id']: s for s in p['sessions']}
    weeks = {w['number']: w for w in p['weeks']}
    actual = p['intended_use'] == 'actual'
    # Explicit short-window coverage does not relax dose or readiness checks.
    scope_dates = None
    if p.get('scope') is not None:
        scope = p['scope']
        expected = {start.isoformat()} if scope['window'] == 'day' else {
            (start + dt.timedelta(days=i)).isoformat() for i in range(7)}
        dates = scope['dates']
        if n != 1:
            errors.append('scope: short window requires duration_weeks=1')
        elif len(dates) != len(set(dates)) or set(dates) != expected:
            errors.append('scope: dates must exactly match the declared day/week starting at start_date')
        else:
            scope_dates = expected
    for name, values in [('objective', [g['id'] for g in p['objectives']]), ('block', [b['id'] for b in p['blocks']]), ('session', [s['id'] for s in p['sessions']]), ('week', [w['number'] for w in p['weeks']]), ('evidence', [e['id'] for e in p['evidence']])]:
        if len(values) != len(set(values)):
            errors.append(f'duplicate {name} id')
    if set(weeks) != set(range(1, n + 1)):
        errors.append('weeks must cover the requested window exactly')
    cover = {i: [] for i in range(1, n + 1)}
    for b in p['blocks']:
        if b['first_week'] > b['last_week'] or b['last_week'] > n:
            errors.append(f'{b["id"]}: invalid block range')
        for i in range(b['first_week'], b['last_week'] + 1):
            if i in cover:
                cover[i].append(b['id'])
        if not set(b['goal_ids']) <= goals:
            errors.append(f'{b["id"]}: unknown goal')
    if any(len(v) != 1 for v in cover.values()):
        errors.append('block ranges must cover every week exactly once')
    # 阶段切分：周数是参数不是常量。标准长度各有一种（4 周两种）合法切法，其余长度只要求阶段覆盖完整。
    STANDARD_SPANS = {
        12: [[(1, 3), (4, 6), (7, 9), (10, 12)]],
        9: [[(1, 3), (4, 6), (7, 9)]],
        6: [[(1, 3), (4, 6)]],
        4: [[(1, 1), (2, 2), (3, 3), (4, 4)], [(1, 4)]],
        8: [[(1, 3), (4, 6), (7, 8)]],
        3: [[(1, 3)]],
    }
    spans = sorted((b['first_week'], b['last_week']) for b in p['blocks'])
    if n < 3:
        pass  # 单周／双周是最小单元，不构成阶段，不做切分校验
    elif n in STANDARD_SPANS:
        if spans not in STANDARD_SPANS[n]:
            allowed = ' 或 '.join('、'.join('第' + str(a) + '–' + str(b) + '周' for a, b in v) for v in STANDARD_SPANS[n])
            errors.append(str(n) + ' 周计划的阶段切分应为 ' + allowed + '；当前为 ' +
                          '、'.join('第' + str(a) + '–' + str(b) + '周' for a, b in spans))
    else:
        # 非标准长度：直接拒绝。回退在块内解决，不顺延总长
        errors.append(str(n) + ' 周不在支持的计划长度内（12／9／8／6／4／3）。阶段回退在块内做、总长不变；' +
                      '要改总长先重定阶段切分并重出计划，而不是把现有计划往后顺延')
    ball_check = check_ball(p)
    errors += ball_check["errors"]
    review += ball_check["reminders"]
    insufficient += ball_check["unverified"]
    assignments, minutes = [], {}
    for w in p['weeks']:
        if re.search(r'\d+\s*[×xX]\s*\d+|\d+\s*(?:分钟|公里|米|%)', w.get('variation', '')):
            errors.append('week ' + str(w['number']) + ': variation含手写数字处方；请由实际单次工作项生成周剂量摘要，避免两处声明冲突')
        if w['block_id'] not in blocks or w['block_id'] not in cover.get(w['number'], []):
            errors.append(f'week {w["number"]}: invalid block')
        assignments += w['session_ids']
        for sid in w['session_ids']:
            if sid not in sessions or sessions[sid]['week_number'] != w['number']:
                errors.append(f'week {w["number"]}: invalid session {sid}')
        days = set()
        for day in w['rest_days']:
            date = dt.date.fromisoformat(day)
            if not 7 * (w['number'] - 1) <= (date - start).days < 7 * w['number']:
                errors.append(f'week {w["number"]}: rest date out of range')
            if scope_dates is not None and day not in scope_dates:
                errors.append(f'week {w["number"]}: rest date outside declared scope')
            if day in days:
                errors.append(f'week {w["number"]}: duplicate rest date')
            days.add(day)
        active = {sessions[sid]['date'] for sid in w['session_ids'] if sid in sessions}
        ball_dates = {b['date'] for b in p.get('ball_days', []) if 7 * (w['number'] - 1) <= (dt.date.fromisoformat(b['date']) - start).days < 7 * w['number']}
        active |= ball_dates
        if active & days:
            errors.append(f'week {w["number"]}: training/rest date collision')
        if w['detail_status'] == 'scheduled':
            if scope_dates is not None and (active | days) != scope_dates:
                errors.append(f'week {w["number"]}: scheduled dates must cover declared scope exactly')
            elif scope_dates is None and len(active | days) != 7:
                errors.append(f'week {w["number"]}: scheduled week must account for seven dates')
        if w['detail_status'] == 'summary':
            review.append(f'week {w["number"]}: modules only; dates not fully prescribed')
    if sorted(assignments) != sorted(sessions):
        errors.append('week session references must assign each session exactly once')
    profile = p['profile']
    equipment = set(profile['equipment']) | {'bodyweight'}
    for s in p['sessions']:
        module_ids = [m['id'] for m in s['modules'] if m.get('id')]
        if len(module_ids) != len(set(module_ids)):
            errors.append(s['id'] + ': 重复模块ID会使跨周匹配歧义')
        date = dt.date.fromisoformat(s['date'])
        if scope_dates is not None and s['date'] not in scope_dates:
            errors.append(f'{s["id"]}: session date outside declared scope')
        delta = (date - start).days
        if not 0 <= delta < 7 * n or s['week_number'] != delta // 7 + 1:
            errors.append(f'{s["id"]}: date/week mismatch')
        if s['block_id'] != weeks.get(s['week_number'], {}).get('block_id'):
            errors.append(f'{s["id"]}: block mismatch')
        if not s['goal_ids'] or not set(s['goal_ids']) <= goals:
            errors.append(f'{s["id"]}: missing/unknown goals')
        if abs(sum(m['duration_minutes'] for m in s['modules']) - s['duration_minutes']) > 0.01:
            errors.append(f'{s["id"]}: module times do not match session time')
        group_labels = [m['group_label'] for m in s['modules'] if m.get('group_label')]
        if len(group_labels) != len(set(group_labels)):
            errors.append(f'{s["id"]}: duplicate group label would make the circuit order ambiguous')
        minutes[s['date']] = minutes.get(s['date'], 0) + s['duration_minutes']
        for m in s['modules']:
            items = m['items']
            item_ids = [x['id'] for x in items if x.get('id')]
            if len(item_ids) != len(set(item_ids)):
                errors.append(s['id'] + '/' + m['title'] + ': 重复工作项ID')
            grouped = bool(m.get('group_label'))
            if abs(sum(x['duration_minutes'] for x in items) - m['duration_minutes']) > 0.01:
                errors.append(f'{s["id"]}/{m["title"]}: item times do not match module time')
            group_sets = [x['dose']['sets'] for x in items]
            group_order_valid = True
            if m.get('set_sequence') is not None and not grouped:
                errors.append(f'{s["id"]}/{m["title"]}: set_sequence requires a grouped module')
            if grouped:
                try:
                    sequence(m)
                except ValueError as exc:
                    errors.append(f'{s["id"]}/{m["title"]}: {exc}')
                    group_order_valid = False
            active_per_round = []
            for x in items:
                uid, dose = x['unit_id'], x['dose']
                load_obj = dose.get('load') or {}
                if load_obj.get('target_rpe') is not None:
                    _kg = load_obj.get('reference_weight_kg')
                    _bs = load_obj.get('reference_weight_basis') or ''
                    _method = (load_obj.get('selection_method') or '').strip()
                    if _kg is None and not _method and not _bs.startswith('待补'):
                        errors.append(f'{s["id"]}/{uid}: 加载动作缺选重处方——写清组次＋目标RPE／RIR＋选重方法＋休息，或给出参考重量（TR）')
                    elif _kg is not None and not _bs.startswith('TR'):
                        errors.append(f'{s["id"]}/{uid}: 参考重量必须来自 TR（training PR）记录，写清组次与日期')
                asset = assets.get(uid)
                if not asset:
                    errors.append(f'{s["id"]}: unknown unit {uid}')
                    continue
                if asset.get('training_allowed') is False:
                    errors.append(f'{s["id"]}: {uid}仅用于目录，不能进入训练处方')
                errors.extend(s['id'] + '/' + uid + ': ' + message for message in check_timing(x))
                pool_length = s.get('pool_length_m', (profile.get('pool') or {}).get('length_m'))
                errors.extend(s['id'] + '/' + uid + ': ' + message for message in check_asset(x, asset, pool_length))
                if uid in profile['banned_units']:
                    errors.append(f'{s["id"]}: prohibited unit {uid}')
                if not any(set(combo) <= equipment for combo in asset['equipment_options']):
                    errors.append(f'{s["id"]}: equipment unavailable for {uid}')
                mastery = profile['mastery'].get(uid, 'unknown')
                if asset['requires_mastery'] and mastery != 'independent':
                    errors.append(f'{s["id"]}: independent skill not established for {uid}')
                elif (mastery != 'independent' and asset['category'] not in ('recovery', 'mobility')
                      and not (asset.get('swim_task_mode') == 'stationary'
                               and profile.get('swim_task_readiness', {}).get(uid, {}).get('status') == 'ready')):
                    message = f'{s["id"]}/{uid}: mastery {mastery}; confirm initial ability or select a familiar alternative'
                    if actual:
                        insufficient.append(message)
                    else:
                        review.append(message)
                if not any((dose['sets'], dose['duration_minutes'], dose['distance_m'])):
                    errors.append(f'{s["id"]}/{uid}: missing dose')
                if asset['category'] in ('strength', 'power') and (dose['sets'] is None or (dose['reps'] is None and not dose['duration_minutes'] and not dose['distance_m']) or not dose['load']['description']):
                    errors.append(f'{s["id"]}/{uid}: incomplete strength/power prescription')
                rpe = dose['load']['target_rpe']
                if rpe is not None and float(rpe).is_integer():
                    shown = dose['load'].get('execution_target') or dose['load'].get('description') or ''
                    for hit in re.findall(r'余(\d+)次', shown):
                        if int(hit) != 10 - int(rpe):
                            errors.append(s['id'] + '/' + uid + ': 努力锚点写「余' + hit + '次」与目标RPE'
                                          + str(int(rpe)) + '（约余' + str(10 - int(rpe)) + '次）不一致')
                if actual and asset['category'] in ('strength', 'power') and dose['load']['target_rpe'] is None and not dose['load'].get('execution_target'):
                    insufficient.append(s['id'] + '/' + uid + ': 缺少本组努力或质量的执行锚点，需execution_target或适用的目标RPE')
                if asset['category'] in ('run', 'swim') and not (dose['duration_minutes'] or dose['distance_m']):
                    errors.append(f'{s["id"]}/{uid}: endurance prescription needs positive time or distance')
                sets = dose['sets'] or 1
                whole_set = work_seconds(x)
                timed = dose['duration_minutes']
                if timed is not None and x.get('work_seconds_per_set') is not None:
                    expected = timed * 60 * (2 if dose['per_side'] else 1)
                    if abs(whole_set - expected) > 1:
                        errors.append(f'{s["id"]}/{uid}: whole-set work estimate contradicts prescribed timed work')
                if whole_set is None:
                    if actual or grouped:
                        insufficient.append(f'{s["id"]}/{uid}: need whole-set work_seconds_per_set for repetition/distance timing')
                elif whole_set <= 0:
                    errors.append(f'{s["id"]}/{uid}: active work must take positive time')
                recovery_type = dose.get('recovery_type', 'rest')
                if recovery_type != 'sendoff' and dose.get('sendoff_seconds') is not None:
                    errors.append(f'{s["id"]}/{uid}: sendoff_seconds requires sendoff recovery type')
                rest_floor = (sets - 1) * dose['rest_seconds'] / 60
                active_floor = per_set_seconds(x) * sets / 60
                if recovery_type == 'sendoff':
                    sendoff = dose.get('sendoff_seconds')
                    if not sendoff:
                        errors.append(f'{s["id"]}/{uid}: sendoff interval missing')
                    elif whole_set is not None:
                        if whole_set > sendoff:
                            errors.append(f'{s["id"]}/{uid}: swim work exceeds sendoff')
                        active_floor = ((sets - 1) * sendoff + whole_set) / 60
                    if dose['rest_seconds'] != 0:
                        errors.append(f'{s["id"]}/{uid}: sendoff must not also add rest_seconds')
                    if asset['category'] != 'swim':
                        errors.append(f'{s["id"]}/{uid}: sendoff is a swim departure interval')
                    if grouped:
                        errors.append(f'{s["id"]}/{uid}: sendoff cannot be mixed into a strength circuit')
                    rest_floor = 0
                if not grouped and rest_floor + active_floor > x['duration_minutes'] + 0.01:
                    errors.append(f'{s["id"]}/{uid}: prescribed work and rest exceed allocated time')
                if grouped:
                    if active_floor > x['duration_minutes'] + 0.01:
                        errors.append(f'{s["id"]}/{uid}: active work exceeds allocated item time')
                    active_per_round.append(whole_set)
            if grouped and group_order_valid and len(active_per_round) == len(items) and all(v is not None for v in active_per_round):
                minimum = schedule(m)[-1]['end'] / 60
                if minimum > m['duration_minutes'] + 0.01:
                    errors.append(f'{s["id"]}/{m["title"]}: combined active work and shared recovery exceed module time')
    for day, total in minutes.items():
        weekday = str(dt.date.fromisoformat(day).weekday())
        budget = profile['available_minutes'].get(weekday)
        if budget is None:
            if actual:
                insufficient.append(f'{day}: available daily time unknown')
            else:
                review.append(f'{day}: available daily time unknown')
        elif total > budget:
            errors.append(f'{day}: {total} minutes exceeds available {budget}')
    for e in p['evidence']:
        if e['session_id'] is not None and e['session_id'] not in sessions:
            errors.append(f'{e["id"]}: unknown session reference')
        if any(a['unit_id'] not in assets for a in e['actual_sets']):
            errors.append(f'{e["id"]}: unknown actual unit')
    KIND_LABEL = [('力量', 'strength'), ('轻松跑', 'run'), ('跑', 'run'), ('游泳', 'swim'), ('泳', 'swim')]
    for w in p['weeks']:
        if w.get('detail_status') != 'scheduled':
            continue                       # 未展开周没有单次可核对，只核对已展开周
        summary = w.get('module_summary') or ''
        counted = {}
        for s in p['sessions']:
            if s['week_number'] == w['number']:
                counted[s['kind']] = counted.get(s['kind'], 0) + 1
        seen = {}
        for label, kind in KIND_LABEL:
            for hit in re.findall(label + r'(\d+)次', summary):
                seen.setdefault(kind, set()).add(int(hit))
        if not seen:
            review.append('week ' + str(w['number']) + ': 周汇总未写明各课次数，无法与单次课表核对')
        for kind, values in seen.items():
            if len(values) != 1 or list(values)[0] != counted.get(kind, 0):
                errors.append('week ' + str(w['number']) + ': module_summary 与单次课数不一致（'
                              + str(kind) + '）')
    for g in p['objectives']:
        if g['mode'] != 'develop':
            continue
        for stage in g.get('progression_plan', []):
            declared = {int(n) for n in re.findall(r'\d+', stage.get('planned_dose') or '')}
            if not declared:
                continue
            for w in p['weeks']:
                if not (stage['first_week'] <= w['number'] <= stage['last_week']):
                    continue
                if w['detail_status'] != 'scheduled':
                    continue
                items = [x for s in p['sessions'] if s['week_number'] == w['number'] and g['id'] in s.get('goal_ids', [])
                         for m in s['modules'] for x in m.get('items', [])
                         if isinstance(x.get('dose'), dict) and x['dose'].get('reps')
                         and item_capabilities(x, assets) & set(g.get('capability_ids', []))]
                reps = {x['dose']['reps'] for x in items}
                if reps and not (reps & declared):
                    review.append(g['id'] + '/week ' + str(w['number'])
                                  + ': 阶段 planned_dose 与单次处方次数无交集，需确认两处剂量一致')
    topics = [x['topic'] for x in p['design_review']]
    required = {'goal_alignment', 'user_constraints', 'load_recovery', 'hierarchy', 'change_impact'}
    if len(topics) != len(set(topics)):
        errors.append('duplicate semantic review topic')
    semantic_ok = set(topics) == required and all(x['outcome'] in ('pass', 'tradeoff') for x in p['design_review'])
    entity_ids = goals | set(sessions) | set(blocks) | {p['id'], p['profile']['id']} | {b['id'] for b in p.get('ball_days', [])}
    for assessment in p['design_review']:
        if not set(assessment.get('checked_ids', [])) <= entity_ids:
            errors.append(assessment['topic'] + ': 审查引用未知目标、阶段或课程ID')
    if actual:
        for assessment in p['design_review']:
            if not assessment.get('checked_ids'):
                insufficient.append(assessment['topic'] + ': 设计审查需关联具体目标、阶段或课程ID')
    if not semantic_ok:
        review.append('semantic review is incomplete or unresolved')
    # 摘要必须由剂量生成：手写数字与处方两处并存时，改一处就会留下另一处
    pool_default = (p['profile'].get('pool') or {}).get('length_m')
    # 摘要写错不改训练结构，所以是 review；但必须报出来，否则手写数字会一直留在文件里
    for row in summary_drift(p, pool_default):
        if row['quantified']:
            review.append(row['id'] + ': mini_goal 与单次剂量不一致（应为「' + row['expected'] + '」）；摘要须由剂量生成，不手写')
        else:
            review.append(row['id'] + ': 单次摘要未写明剂量，建议由剂量生成')
    design_errors, design_review, missing, requirements = design_check(p, assets)
    aerobic_summary, aerobic_errors, aerobic_missing = calculate_aerobic(p, assets)
    endurance_summary = calculate_endurance(p, assets)
    endurance_errors, endurance_missing = check_endurance(p, assets)
    errors += design_errors
    errors += aerobic_errors
    errors += endurance_errors
    review += design_review
    insufficient = list(dict.fromkeys(insufficient + missing + aerobic_missing + endurance_missing))
    # 块末周不得自动减载：同一槽位（课型＋模块＋条目序号）组数低于本块前面周即提示换刺激
    for b in p['blocks']:
        weeks_in = [w['number'] for w in p['weeks'] if b['first_week'] <= w['number'] <= b['last_week']]
        per = {}
        for s in p['sessions']:
            if s['week_number'] not in weeks_in or s['kind'] != 'strength':
                continue
            for m in s['modules']:
                for i, x in enumerate(m.get('items', [])):
                    if x.get('dose', {}).get('sets'):
                        slot = (s['title'], m['title'], i)
                        per.setdefault(slot, {})[s['week_number']] = x['dose']['sets']
        last = max(weeks_in)
        seen = {}
        for slot, by_week in per.items():
            earlier = [v for k, v in by_week.items() if k < last]
            if earlier and by_week.get(last, 0) < max(earlier):
                key = slot[1] + '/' + str(slot[2])
                if key in seen or len(seen) > 5:
                    continue
                seen[key] = 1
                review.append('week ' + str(last) + ': ' + slot[1] + ' 第' + str(slot[2] + 1) + '项组数低于本块前面周，疑似自动减载；块末周应换刺激（负重/节奏/弹性比例）而不是固定减量')
    ready = not errors and not insufficient and semantic_ok and p['status'] == 'executable' and p['arrangement']['status'] in ('selected', 'confirmed') and actual
    if p['status'] == 'executable' and not ready and not insufficient:
        errors.append('executable status requires selected/confirmed arrangement, actual use, concrete prescriptions and resolved design information')
    # 设计前提缺失（能不能上还不确定）按周拦出表；执行反馈缺失（上没上还不知道）一律不拦：
    # 次晨反应、本周 RPE、实际完成量只有在课之后才存在，不做出表门槛。
    date_week = {s['date']: s['week_number'] for s in p['sessions']}

    blocked = {}
    global_gaps = []
    for message in insufficient:
        scope = week_scope(message, date_week, sessions)
        if scope is None:
            global_gaps.append(message)
        else:
            blocked.setdefault(scope, []).append(message)
    scheduled = [w['number'] for w in p['weeks'] if w.get('detail_status') == 'scheduled']
    ready_weeks = [] if errors else [w for w in scheduled if w not in blocked and not global_gaps]
    return {'errors': errors, 'review_items': review, 'insufficient_basis': insufficient, 'review_requirements': requirements, 'ball_check': ball_check,
            'ready_weeks': ready_weeks,
            'blocked_weeks': sorted(blocked), 'blocked_week_reasons': {w: v for w, v in sorted(blocked.items())},
            'global_gaps': global_gaps,
            'aerobic_summary': aerobic_summary, 'endurance_summary': endurance_summary,
            'timing_summary': timing_summary(p),
            'timing_audit': timing_audit(p),
            'check_coverage': {'structure': True, 'design_context': bool(p.get('design_context')),
                               'endurance_totals': True, 'pool_length': bool(p.get('profile', {}).get('pool')) or any(s.get('pool_length_m') for s in p['sessions']),
                               'library_numeric_interfaces': '按资产dose_domain中machine_check与plan_field映射核对；文字任务条件由设计者审查',
                               'semantic_review_is_designer_judgment': True, 'training_effect_machine_certified': False},
            'deterministic_pass': not errors, 'ready_to_render_executable': ready and not errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan')
    args = parser.parse_args()
    try:
        result = validate(read_json(args.plan))
    except (ValueError, OSError, KeyError) as e:
        result = {'errors': [str(e)], 'review_items': [], 'insufficient_basis': [], 'review_requirements': [], 'aerobic_summary': None, 'deterministic_pass': False, 'ready_to_render_executable': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['deterministic_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
