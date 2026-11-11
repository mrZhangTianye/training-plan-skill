"""Sum prescribed moving work separately from health intensity and session time."""
from aerobic_stats import active_minutes


def role(item, assets):
    explicit = item.get('endurance_role')
    if explicit:
        return explicit
    asset = assets.get(item['unit_id'], {})
    physical_role = asset.get('endurance_role')
    if physical_role:
        return physical_role
    category = asset.get('category')
    return category if category in ('run', 'swim') else None


def empty():
    return {'run_minutes': 0, 'run_time_complete': True,
            'run_distance_m': 0, 'run_distance_known_m': 0,
            'run_distance_status': 'exact', 'run_distance_complete': True,
            'swim_distance_m': 0, 'swim_distance_known_m': 0,
            'swim_distance_complete': True, 'easy_minutes': 0,
            'non_easy_minutes': 0,
            'non_easy_by_type': {'tempo': 0, 'interval': 0, 'fast': 0},
            'unclassified_run_minutes': 0, 'has_run': False, 'has_swim': False}


def calculate(p, assets):
    sessions = {}
    for session in p.get('sessions', []):
        row = empty()
        for module in session['modules']:
            for item in module['items']:
                mode = role(item, assets)
                if mode not in ('run', 'swim'):
                    continue
                dose = item['dose']
                if mode == 'swim' and assets.get(item['unit_id'], {}).get('swim_task_mode') == 'stationary':
                    row['has_swim'] = True
                    continue  # Non-displacing technique time is never invented distance.
                factor = (dose['sets'] or 1) * (dose.get('reps') or 1) * (2 if dose['per_side'] else 1)
                distance = dose.get('distance_m')
                if mode == 'run':
                    row['has_run'] = True
                    minutes = active_minutes(item)
                    if minutes is None:
                        row['run_time_complete'] = False
                    else:
                        row['run_minutes'] += minutes
                        intensity = item.get('run_intensity')
                        if intensity == 'easy':
                            row['easy_minutes'] += minutes
                        elif intensity in row['non_easy_by_type']:
                            row['non_easy_by_type'][intensity] += minutes
                            row['non_easy_minutes'] += minutes
                        else:
                            row['unclassified_run_minutes'] += minutes
                    if distance is None:
                        distance = dose.get('distance_estimate_m')
                        if distance is None:
                            row['run_distance_complete'] = False
                            row['run_distance_status'] = 'unknown'
                        elif row['run_distance_status'] != 'unknown':
                            row['run_distance_status'] = 'estimated'
                    if distance is not None:
                        row['run_distance_known_m'] += distance * factor
                else:
                    row['has_swim'] = True
                    if distance is None:
                        row['swim_distance_complete'] = False
                    else:
                        row['swim_distance_known_m'] += distance * factor
        row['run_distance_m'] = row['run_distance_known_m'] if row['run_distance_complete'] else None
        row['swim_distance_m'] = row['swim_distance_known_m'] if row['swim_distance_complete'] else None
        sessions[session['id']] = row
    weeks = []
    for number in range(1, p['duration_weeks'] + 1):
        row = empty()
        row['week'] = number
        for session in p.get('sessions', []):
            if session['week_number'] != number:
                continue
            part = sessions[session['id']]
            for key in ('run_minutes', 'run_distance_known_m', 'swim_distance_known_m',
                        'easy_minutes', 'non_easy_minutes', 'unclassified_run_minutes'):
                row[key] += part[key]
            for key in ('run_time_complete', 'run_distance_complete', 'swim_distance_complete'):
                row[key] = row[key] and part[key]
            for key in ('has_run', 'has_swim'):
                row[key] = row[key] or part[key]
            for key in row['non_easy_by_type']:
                row['non_easy_by_type'][key] += part['non_easy_by_type'][key]
            if part['run_distance_status'] == 'unknown':
                row['run_distance_status'] = 'unknown'
            elif part['run_distance_status'] == 'estimated' and row['run_distance_status'] == 'exact':
                row['run_distance_status'] = 'estimated'
        row['run_distance_m'] = row['run_distance_known_m'] if row['run_distance_complete'] else None
        row['swim_distance_m'] = row['swim_distance_known_m'] if row['swim_distance_complete'] else None
        row['easy_percent'] = 100 * row['easy_minutes'] / row['run_minutes'] if row['run_minutes'] and row['run_time_complete'] and not row['unclassified_run_minutes'] else None
        weeks.append(row)
    return {'sessions': sessions, 'weeks': weeks, 'assumptions_only': True}


def check(p, assets):
    errors, missing = [], []
    actual = p.get('intended_use') == 'actual'
    default_pool = (p.get('profile', {}).get('pool') or {}).get('length_m')
    for session in p.get('sessions', []):
        pool = session.get('pool_length_m', default_pool)
        for module in session['modules']:
            for item in module['items']:
                uid = item['unit_id']
                mode = role(item, assets)
                asset = assets.get(uid, {})
                expected_role = asset.get('endurance_role') or asset.get('category')
                address = session['id'] + '/' + uid
                if expected_role == 'mixed' and not item.get('endurance_role'):
                    missing.append(address + ': 混合训练单元需拆为实际跑、走或泳段，再分别标运动形式与强度；整段不能冒作跑量')
                if expected_role in ('run', 'swim', 'walk') and mode != expected_role:
                    errors.append(address + ': 实际跑泳工作不能改标成其他项目以隐藏总量')
                if item.get('run_intensity') and mode != 'run':
                    errors.append(address + ': 跑步强度分类只用于实际跑段')
                dose = item['dose']
                estimate = dose.get('distance_estimate_m')
                if estimate is not None:
                    if mode != 'run' or dose.get('distance_m') is not None:
                        errors.append(address + ': 预计跑距只用于没有确定距离的跑段')
                    if not dose.get('distance_estimate_basis'):
                        missing.append(address + ': 预计跑距需有个人配速等估算依据')
                if mode == 'run' and actual:
                    if not item.get('run_intensity'):
                        missing.append(address + ': 需注明轻松、节奏、间歇或短快段，不能用健康强度推断跑步分配')
                    if active_minutes(item) is None:
                        missing.append(address + ': 需给跑段工作时间以核算总跑动分钟')
                if mode == 'swim' and asset.get('swim_task_mode') == 'stationary':
                    if dose.get('distance_m') is not None:
                        errors.append(address + ': 原地技术练习不得虚构泳距')
                    continue
                if mode == 'swim':
                    distance = dose.get('distance_m')
                    if distance is None:
                        missing.append(address + ': 泳段需有确定组距，才能汇总整堂总距离')
                    if actual and not pool:
                        missing.append(session['id'] + ': 需明确本课泳池长度')
                    if distance is not None and pool and abs(distance / pool - round(distance / pool)) > 0.00001 and not item.get('partial_length'):
                        errors.append(address + ': 组距必须符合池长；局部短段需明确partial_length及安全完成方式')
                    if item.get('partial_length') and not item.get('execution_note'):
                        missing.append(address + ': 池中短段需说明起止位置及如何完成剩余池长')
                    if dose['per_side']:
                        errors.append(address + ': 泳距离不按左右侧重复计量')
    return errors, list(dict.fromkeys(missing))


def strength_summary(p, week_number):
    """The actual prescriptions are the sole source of a weekly dose summary."""
    rows = {}
    for session in p.get('sessions', []):
        if session['week_number'] != week_number:
            continue
        for module in session['modules']:
            for item in module['items']:
                wave = item.get('wave_role')
                if wave:
                    key = (item['unit_id'], wave)
                    rows.setdefault(key, []).append({'session_id': session['id'], 'dose': item['dose'], 'display_name': item.get('display_name')})
    return [{'unit_id': uid, 'wave_role': wave, 'prescriptions': doses} for (uid, wave), doses in rows.items()]
