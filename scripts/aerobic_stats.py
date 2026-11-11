"""Count only explicitly classified active work; never infer real exercise intensity."""
from work_timing import whole_set_seconds


def active_minutes(item):
    dose = item['dose']
    seconds = whole_set_seconds(item)
    return None if seconds is None else seconds * (dose['sets'] or 1) / 60


def calculate(p, assets):
    errors, missing = [], []
    planned = (p.get('design_context') or {}).get('aerobic_plan')
    by_week = (planned or {}).get('target_by_week', {})
    for key in by_week:
        try:
            number = int(key)
            if str(number) != key or not 1 <= number <= p['duration_weeks']:
                raise ValueError()
        except (TypeError, ValueError):
            errors.append('aerobic_plan: target_by_week requires a plan week number')
    rows = []
    for week in range(1, p['duration_weeks'] + 1):
        row = {'week': week, 'light_minutes': 0, 'moderate_minutes': 0, 'vigorous_minutes': 0,
               'net_minutes': 0, 'equivalent_minutes': 0, 'unclassified_items': [],
               'unclassified_work_minutes': 0, 'target_minutes': None, 'goal_status': 'not_set'}
        for session in p['sessions']:
            if session['week_number'] != week:
                continue
            for mi, module in enumerate(session['modules']):
                for xi, item in enumerate(module['items']):
                    amount = item.get('aerobic_minutes')
                    intensity = item.get('aerobic_intensity')
                    category = assets.get(item['unit_id'], {}).get('category')
                    if amount is None and intensity is None and category not in ('run', 'swim'):
                        continue
                    work = active_minutes(item)
                    address = session['id'] + '/' + str(mi) + '/' + str(xi) + '/' + item['unit_id']
                    if amount is not None and work is not None and amount > work + 0.01:
                        errors.append(address + ': aerobic minutes exceed active work; rest and total session time cannot be counted')
                    if amount is None or intensity is None or work is None:
                        row['unclassified_items'].append(address)
                        row['unclassified_work_minutes'] += work or 0
                        continue
                    # Both the net work allocation and intensity are explicit design assumptions.
                    row[intensity + '_minutes'] += amount
                    row['net_minutes'] += amount
                    row['equivalent_minutes'] += amount * (2 if intensity == 'vigorous' else 1 if intensity == 'moderate' else 0)
        row['annotations_complete'] = not row['unclassified_items']
        _wk = next((x for x in p.get('weeks', []) if x['number'] == week), None)
        if planned and _wk is not None and _wk.get('detail_status') == 'summary':
            # 尚未展开的周不做当量缺口判定：无课表不等于剂量不足
            row['goal_status'] = 'build_up'
            rows.append(row)
            continue
        if planned:
            target = by_week.get(str(week))
            if week == p['duration_weeks']:
                target = max(target or 0, planned['target_weekly_equivalent_minutes'])
            if target is not None:
                row['target_minutes'] = target
                if row['unclassified_items']:
                    row['goal_status'] = 'unverified'
                    missing.append('aerobic_goal:week ' + str(week) + ': 目标周存在未核定的净运动量或强度，不能据类型/RPE推断当量')
                elif row['equivalent_minutes'] + 0.01 < target:
                    row['goal_status'] = 'gap'
                    gap = target - row['equivalent_minutes']
                    missing.append('aerobic_goal:week ' + str(week) + ': 已标注中等当量距预定目标差' + f'{gap:g}' + '分钟；需修订剂量或目标，说明不能代替实际缺口')
                else:
                    row['goal_status'] = 'planned_meets'
            else:
                row['goal_status'] = 'build_up' if row['annotations_complete'] else 'unverified'
        elif row['unclassified_items']:
            row['goal_status'] = 'unverified'
        rows.append(row)
    targets = [row for row in rows if row['target_minutes'] is not None]
    summary = {'weeks': rows, 'assumptions_only': True,
               'annotations_complete': all(row['annotations_complete'] for row in rows),
               'goal_pass': None if not planned else bool(targets) and all(row['goal_status'] == 'planned_meets' for row in targets)}
    return summary, errors, missing
