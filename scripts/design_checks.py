# -*- coding: utf-8 -*-
"""Check declared design consistency, not individual adaptation or medical safety."""
import datetime as dt
import json
import re
from common import ROOT, read_json, fingerprint


def minutes(time):
    h, m = map(int, time.split(':'))
    return h * 60 + m


def item_capabilities(item, assets):
    return set(item.get('capability_ids', assets.get(item['unit_id'], {}).get('capabilities', [])))


def substantive_text(value):
    """Ignore punctuation and layout, retain actual qualitative intensity wording."""
    return re.sub(r'[^\w]', '', value or '').lower()


def stable_parameters(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        return {k: stable_parameters(v) for k, v in value.items()}
    if isinstance(value, list):
        return [stable_parameters(v) for v in value]
    return value


def recovery_context(session):
    """Exclude labels, cues and prose reviews; bind meaningful training parameters."""
    modules = []
    for m in session['modules']:
        items = []
        for x in m['items']:
            d = x['dose']
            items.append({'unit_id': x['unit_id'], 'duration_minutes': x['duration_minutes'],
                          'work_seconds_per_set': x.get('work_seconds_per_set'),
                          'contacts_per_rep': x.get('contacts_per_rep'),
                          'tempo_seconds_per_rep': x.get('tempo_seconds_per_rep'),
                          'swim_pace_seconds_per_100m': x.get('swim_pace_seconds_per_100m'),
                          'endurance_role': x.get('endurance_role'), 'run_intensity': x.get('run_intensity'),
                          'aerobic_minutes': x.get('aerobic_minutes'), 'aerobic_intensity': x.get('aerobic_intensity'),
                          'dose': {k: d[k] for k in ('sets', 'reps', 'duration_minutes', 'distance_m', 'per_side', 'rest_seconds')},
                          'distance_estimate_m': d.get('distance_estimate_m'),
                          'execution_target': substantive_text(d['load'].get('execution_target')),
                          'recovery_type': d.get('recovery_type', 'rest'), 'sendoff_seconds': d.get('sendoff_seconds'),
                          'target_rpe': d['load']['target_rpe'], 'reference_weight_kg': d['load']['reference_weight_kg'],
                          'selection_method': substantive_text(d['load'].get('selection_method')),
                          'intensity': substantive_text(d['load']['description'])})
        modules.append({'duration_minutes': m['duration_minutes'], 'grouped': bool(m.get('group_label')), 'set_sequence': m.get('set_sequence'), 'items': items})
    return {'id': session['id'], 'date': session['date'], 'start_time': session.get('start_time'),
            'pool_length_m': session.get('pool_length_m'),
            'duration_minutes': session['duration_minutes'], 'recovery_cost': session['recovery_cost'],
            'fatigue_regions': sorted(set(session['fatigue_regions'])), 'modules': modules}


# 跑动剂量只算跑：走段与课首尾过渡不计入时长口径的分子与分母（整课时间不是跑量）
RUN_NON_RUN_UNITS = {'warmup', 'cooldown', 'brisk_walk', 'run_warmup', 'run_cooldown',
                     'mobility', 'foam_roll', 'static_stretch'}

# 阶段对照只看课表里真实写下的剂量，不看目标层的说法：一个专项若只是目标里写「发展」，
# 每次课的剂量没动，它在对照表里就是平的——这正是要暴露的东西。
LINE_SPORTS = ('strength', 'run', 'swim')
VOLUME_RISE = 1.10      # 量涨过 10% 算上抬（沿用包里泳量那条 10% 判定带，不是生理阈值）
INTENSITY_RISE = 0.2    # 目标 RPE 均值涨过 0.2 算上抬
REST_SHORTEN = 0.95     # 主项休息压到 95% 以下算上抬（压缩休息本身也是加量）

# 球类规则是条件分支：课表里没有球类课次，这些词就不该出现
BALL_RULE_MARKERS = ('球前', '球后', '球赛当天', '打球', '球类')


def _week_lines(p, week):
    """按专项汇总某一周课表里写下的量／强度／休息。"""
    agg = {sport: {'volume': 0.0, 'intensity': [], 'rest': []} for sport in LINE_SPORTS}
    for s in p['sessions']:
        if s['week_number'] != week or s['kind'] not in agg:
            continue
        bucket = agg[s['kind']]
        for m in s['modules']:
            for x in m['items']:
                d = x['dose']
                load = d.get('load') or {}
                rest = d.get('rest_seconds')
                if s['kind'] == 'strength':
                    if load.get('target_rpe') is None:
                        continue  # 准备与整理不算主力负荷
                    bucket['volume'] += (d.get('sets') or 0) * (d.get('reps') or 0)
                    bucket['intensity'].append(load['target_rpe'])
                    if rest:
                        bucket['rest'].append(rest)
                elif s['kind'] == 'run':
                    if x['unit_id'] in RUN_NON_RUN_UNITS:
                        continue
                    bucket['volume'] += d.get('duration_minutes') or 0
                    if load.get('target_rpe') is not None:
                        bucket['intensity'].append(load['target_rpe'])
                    if rest:
                        bucket['rest'].append(rest)
                elif s['kind'] == 'swim':
                    if d.get('sets') and d.get('distance_m'):
                        bucket['volume'] += d['sets'] * d['distance_m']
                    if load.get('target_rpe') is not None:
                        bucket['intensity'].append(load['target_rpe'])
                    if rest:
                        bucket['rest'].append(rest)
    for sport, bucket in agg.items():
        for key in ('intensity', 'rest'):
            values = bucket[key]
            bucket[key] = sum(values) / len(values) if values else None
    return agg


def _week_run_shape(p, week):
    """某一周跑动的次数、单次最长、整周量（不含走／跨步那类非跑单元）。"""
    count, longest, volume = 0, 0.0, 0.0
    for s in p['sessions']:
        if s['week_number'] != week or s['kind'] != 'run':
            continue
        count += 1
        for m in s['modules']:
            for x in m['items']:
                if x['unit_id'] in RUN_NON_RUN_UNITS:
                    continue
                minutes = x['dose'].get('duration_minutes') or 0
                volume += minutes
                longest = max(longest, minutes)
    return count, longest, volume


def baseline_entry_check(p):
    """基线→首周这一步，按频率判，不按百分比判。

    只比 W1 之后的相邻抬档点（ramp_interval）和阶段衔接（stage_handoff），基线到 W1 这一跳
    会整段漏掉，而那往往是全表最大的一步。判据沿用 Daniels 的顺序：跑次增加时单次不上抬，
    加频率本身不算加量；跑次不变而周量抬得超过 VOLUME_RISE 才报。
    """
    blocks = p.get('blocks') or []
    if not blocks:
        return []
    week = blocks[0]['first_week']
    count, longest, volume = _week_run_shape(p, week)
    rows = []
    for goal in p.get('objectives', []):
        basis = goal.get('baseline_basis') or {}
        base_sessions = basis.get('run_sessions_per_week')
        if base_sessions is None:
            if '跑' in (goal.get('baseline') or ''):
                rows.append({'id': goal['id'], 'kind': 'missing_basis',
                             'message': goal['id'] + ': 基线没写跑次与单次最长，W' + str(week)
                                        + ' 这一步无法按频率核，需补口径'})
            continue
        base_longest = basis.get('run_longest_minutes')
        base_weekly = basis.get('run_weekly_minutes')
        head = goal['id'] + ': 基线 ' + str(base_sessions) + ' 次/周、单次最长 ' + str(base_longest) + '′'
        if count > base_sessions:
            if base_longest is not None and longest > base_longest + 1e-9:
                rows.append({'id': goal['id'], 'kind': 'frequency_plus_longer',
                             'message': head + '→W' + str(week) + ' ' + str(count) + ' 次、单次最长 '
                                        + str(round(longest, 1)) + '′：加频率的同时延长了单次，等于两条线一起抬'})
        elif count == base_sessions:
            if base_weekly and volume > base_weekly * VOLUME_RISE:
                rows.append({'id': goal['id'], 'kind': 'volume_same_frequency',
                             'message': head + '→W' + str(week) + ' 跑次不变，周量 ' + str(round(base_weekly, 1))
                                        + '′→' + str(round(volume, 1)) + '′，超过 ' + str(int((VOLUME_RISE - 1) * 100))
                                        + '% 需说明'})
    return rows


def _strength_signature(p, week):
    """某周力量主项（写了目标 RPE 的条目）的 (动作, 组, 次, RPE) 清单，用来识别处方内入门周。"""
    out = {}
    for s in p['sessions']:
        if s['week_number'] != week or s['kind'] != 'strength':
            continue
        for m in s['modules']:
            for x in m['items']:
                load = x['dose'].get('load') or {}
                if load.get('target_rpe') is None:
                    continue
                slot = s['id'].split('-')[-1]
                out[(slot, x['unit_id'])] = (x['dose'].get('sets'), x['dose'].get('reps'), load['target_rpe'])
    return out


def _is_phase_intro(prev_sig, next_sig):
    """阶段首周 2 组、次周 3 组、次数与强度一致＝原表 Phase 1 的入门周，不是阶段内自主加量。

    Boyle 11.2 的 Phase 1 本来就把第 1 周排成 2 组、第 2–3 周 3 组；把它当成「阶段内涨量」
    会让合规示例每周都被要求进审查，所以这里单列识别，只认这一种形态。
    """
    if not prev_sig or prev_sig.keys() != next_sig.keys():
        return False
    changed = False
    for key, (sets_a, reps_a, rpe_a) in prev_sig.items():
        sets_b, reps_b, rpe_b = next_sig[key]
        if reps_a != reps_b or rpe_a != rpe_b:
            return False
        if sets_a == sets_b:
            continue  # 未变的动作不参与判定（F2 较重课本来就从 3 组起）
        if sets_a not in (1, 2) or sets_b != 3:
            return False
        changed = True
    return changed


def stage_load_lines(p):
    """每个阶段首末周的量／强度／休息对照，以及其中上抬的专项。

    handoff_rising 记录「上一阶段末周→本阶段首周」的跨阶段变化：只在阶段首末周之间比对，
    阶段内持平的涨量会被整段漏掉，所以衔接处必须单列一次。
    ``prescribed_intro`` 记录被排除的处方内入门周（Phase 1 第 1 周 2 组），
    该周的 2→3 组来自原表，不算阶段内自主加量。
    """
    rows = []

    def rose(a, b):
        if a['volume'] and b['volume'] > a['volume'] * VOLUME_RISE:
            return True
        if a['intensity'] is not None and b['intensity'] is not None and b['intensity'] > a['intensity'] + INTENSITY_RISE:
            return True
        if a['rest'] is not None and b['rest'] is not None and b['rest'] < a['rest'] * REST_SHORTEN:
            return True
        return False

    previous = None
    for block in p.get('blocks', []):
        first, last = _week_lines(p, block['first_week']), _week_lines(p, block['last_week'])
        entry = {'block_id': block['id'], 'first_week': block['first_week'],
                 'last_week': block['last_week'], 'lines': {}, 'rising': [],
                 'handoff': {}, 'handoff_rising': [], 'prescribed_intro': []}
        base = first
        intro = False
        if block['last_week'] > block['first_week']:
            second_week = block['first_week'] + 1
            if _is_phase_intro(_strength_signature(p, block['first_week']),
                               _strength_signature(p, second_week)):
                intro = True
                base = _week_lines(p, second_week)
                entry['prescribed_intro'].append('strength')
        for sport in LINE_SPORTS:
            a, b = base[sport], last[sport]
            entry['lines'][sport] = {key: [a[key], b[key]] for key in ('volume', 'intensity', 'rest')}
            if rose(a, b):
                entry['rising'].append(sport)
            if intro and sport == 'strength':
                entry['lines'][sport]['intro_week'] = [first[sport]['volume'], block['first_week']]
        if previous is not None:
            for sport in LINE_SPORTS:
                a, b = previous[sport], first[sport]
                entry['handoff'][sport] = {key: [a[key], b[key]] for key in ('volume', 'intensity', 'rest')}
                if rose(a, b):
                    entry['handoff_rising'].append(sport)
        rows.append(entry)
        previous = last
    return rows


def ball_rule_without_ball(p):
    """课表提到球前／球后规则，却没有安排任何球类课次。"""
    blob = json.dumps(p, ensure_ascii=False)
    markers = [m for m in BALL_RULE_MARKERS if m in blob]
    has_ball = any(s['kind'] not in LINE_SPORTS for s in p['sessions'])
    return markers, has_ball


MIN_STABLE_WEEKS = 3   # 抬档之间至少稳 3 周（Daniels 的 3–4 周抬一档，取保守端）


def line_rise_points(p, sport):
    """逐周量，以及"抬档点"：相邻周涨幅超过判定带的那一周。"""
    weeks = list(range(1, p['duration_weeks'] + 1))
    volume = {w: _week_lines(p, w)[sport]['volume'] for w in weeks}
    points = [w for w in weeks if w > 1 and volume[w - 1] and volume[w] > volume[w - 1] * VOLUME_RISE]
    return volume, points


def rising_streak(rows, sport):
    """同一条线连续多少个阶段都在抬，取最长的一段。"""
    best = cur = 0
    for entry in rows:
        cur = cur + 1 if sport in entry['rising'] else 0
        best = max(best, cur)
    return best


def check(p, assets):
    errors, review, missing, requirements = [], [], [], []
    caps = read_json(ROOT / 'references/training-library/capabilities.json')
    context = p.get('design_context')
    actual = p['intended_use'] == 'actual'
    supplied = set()
    for s in p['sessions']:
        for m in s['modules']:
            for item in m['items']:
                asset_caps = set(assets.get(item['unit_id'], {}).get('capabilities', []))
                declared = item_capabilities(item, assets)
                if not declared <= asset_caps:
                    errors.append(s['id'] + '/' + item['unit_id'] + ': capability override exceeds registered asset capabilities')
                supplied.update(declared)

    def require_review(review_id, message, context_value):
        requirements.append({'review_id': review_id, 'message': message,
                             'context_hash': fingerprint(stable_parameters(context_value)), 'resolution': None})

    if not context:
        if actual:
            missing.append('缺少design_context：能力安排、保守起点、恢复取舍与重入策略')
    else:
        waves = context.get('strength_waves', [])
        for wave in waves:
            uids = list(wave.get('unit_ids') or [wave['unit_id']])
            first, last = wave['first_week'], wave['last_week']
            if any(u not in assets for u in uids) or first > last or last > p['duration_weeks']:
                errors.append('invalid strength wave anchor/range: ' + '+'.join(uids))
                continue
            for week in p['weeks']:
                if not first <= week['number'] <= last or week['detail_status'] != 'scheduled':
                    continue
                matches = [(s, x) for s in p['sessions'] if s['week_number'] == week['number'] for m in s['modules'] for x in m['items'] if x['unit_id'] in uids and x.get('wave_role')]
                key = '+'.join(uids) + '/week ' + str(week['number'])
                ORDER = {'capacity': 0, 'moderate': 1, 'heavy': 2}
                roles = sorted({x['wave_role'] for _, x in matches}, key=lambda r: ORDER.get(r, 1))
                if len(roles) < 2:
                    missing.append(key + ': 声明日波动却缺少同动作容量或较重工作组')
                    continue
                by_role = {r: [(s, x) for s, x in matches if x['wave_role'] == r] for r in roles}
                date_sets = [frozenset(s['date'] for s, _ in by_role[r]) for r in roles]
                if sum(len(ds) for ds in date_sets) != len(frozenset().union(*date_sets)):
                    errors.append(key + ': daily wave roles must occur on separate training dates')
                for _, x in matches:
                    if x['dose']['reps'] is None or x['dose']['load']['target_rpe'] is None:
                        missing.append(key + ': 主力波动需明确次数与选重用力标准')
                light = [x['dose']['reps'] for _, x in by_role[roles[0]]]
                heavy = [x['dose']['reps'] for _, x in by_role[roles[-1]]]
                light_rpe = [x['dose']['load']['target_rpe'] for _, x in by_role[roles[0]]]
                heavy_rpe = [x['dose']['load']['target_rpe'] for _, x in by_role[roles[-1]]]
                if None not in light + heavy and max(heavy) >= min(light):
                    # 原表 Phase 2–4 两日主项同为 5 次，日的轻重由目标 RPE 承担；
                    # 只有连 RPE 也没拉开，才算「没有明确较轻/较重」。
                    rpe_split = (None not in light_rpe + heavy_rpe
                                 and min(heavy_rpe) > max(light_rpe))
                    if not rpe_split:
                        missing.append(key + ': 较重课与容量课未给出明确较低重复区间或更高的目标 RPE')
        declared_wave_ids = {u for x in waves for u in (x.get('unit_ids') or [x['unit_id']])}
        for s in p['sessions']:
            for m in s['modules']:
                for x in m['items']:
                    if x.get('wave_role') and (x['unit_id'] not in declared_wave_ids or not any(x['unit_id'] in (w.get('unit_ids') or [w['unit_id']]) and w['first_week'] <= s['week_number'] <= w['last_week'] for w in waves)):
                        errors.append(s['id'] + '/' + x['unit_id'] + ': wave role has no corresponding strength_waves declaration')
        covered = context['coverage']
        ids = [x['capability_id'] for x in covered]
        if len(ids) != len(set(ids)):
            errors.append('duplicate coverage capability')
        if set(ids) != set(caps):
            missing.append('能力覆盖须逐项说明11项能力状态，不要求全部训练')
        for c in covered:
            if c['mode'] in ('develop', 'maintain') and c['capability_id'] not in supplied:
                missing.append('缺少对应训练刺激：' + c['capability_id'])
        counts = {}
        for s in p['sessions']:
            for m in s['modules']:
                for item in m['items']:
                    contacts = item.get('contacts_per_rep')
                    if contacts is not None:
                        d = item['dose']
                        if d['sets'] is None or d['reps'] is None:
                            missing.append(s['id'] + ': 接触量需要组数与次数')
                        else:
                            counts[s['date']] = counts.get(s['date'], 0) + contacts * d['sets'] * d['reps'] * (2 if d['per_side'] else 1)
        for date, count in counts.items():
            budgets = context['contact_budget']
            if date not in budgets:
                missing.append(date + ': 接触量预算未提供')
            elif count > budgets[date]:
                relevant = [recovery_context(s) for s in p['sessions'] if s['date'] == date and any(x.get('contacts_per_rep') is not None for m in s['modules'] for x in m['items'])]
                require_review('contact_budget:' + date, date + ': 接触量超过计划预算，需具体处理本次取舍；不是伤病诊断',
                               {'date': date, 'contacts': count, 'budget': budgets[date], 'sessions': sorted(relevant, key=lambda x: x['id'])})
        if context['reentry']['state'] == 'returning' and context['reentry']['missed_days'] == 0:
            errors.append('returning requires a stated interruption')

    for row in baseline_entry_check(p):
        require_review('baseline_entry:' + row['id'], row['message'], row)
    for entry in stage_load_lines(p):
        if len(entry['rising']) > 1:
            names = {'strength': '力量', 'run': '跑动', 'swim': '泳'}
            require_review('stage_lines:' + entry['block_id'],
                           entry['block_id'] + '（W' + str(entry['first_week']) + '–W' + str(entry['last_week'])
                           + '）同阶段 ' + '、'.join(names.get(x, x) for x in entry['rising'])
                           + ' 同时上抬，需说明本阶段主次与其余项的冻结方式', entry)
        if entry['handoff_rising']:
            names = {'strength': '力量', 'run': '跑动', 'swim': '泳'}
            lines = '、'.join(names.get(x, x) + ' ' + str(round(entry['handoff'][x]['volume'][0], 1))
                             + '→' + str(round(entry['handoff'][x]['volume'][1], 1))
                             for x in entry['handoff_rising'])
            require_review('stage_handoff:' + entry['block_id'],
                           entry['block_id'] + ' 衔接处（上一阶段末周→W' + str(entry['first_week'])
                           + '）' + lines + ' 继续加量：阶段内持平不等于整轮受控，需说明这是抬档还是叠加', entry)

    for sport in ('run',):
        volume, points, = line_rise_points(p, sport)
        gaps = [(a, b) for a, b in zip(points, points[1:]) if b - a < MIN_STABLE_WEEKS]
        if gaps:
            a, b = gaps[0]
            name = {'run': '跑动', 'swim': '泳', 'strength': '力量'}.get(sport, sport)
            require_review('ramp_interval:' + sport + ':' + str(b),
                           name + '线 W' + str(a) + '→W' + str(b) + '（' + str(round(volume[a - 1], 1)) + '→'
                           + str(round(volume[b - 1], 1)) + ' 分钟）只隔 ' + str(b - a) + ' 周就再次抬档，'
                           + '抬档之间至少稳 ' + str(MIN_STABLE_WEEKS) + ' 周；本阶段是节拍安排还是转化依据需写明',
                           {'weeks': points, 'volume': {str(k): v for k, v in volume.items()}})

    for sport in LINE_SPORTS:
        streak = rising_streak(stage_load_lines(p), sport)
        if streak >= 2:
            name = {'run': '跑动', 'swim': '泳', 'strength': '力量'}.get(sport, sport)
            volume, _points = line_rise_points(p, sport)
            require_review('stage_lines_streak:' + sport,
                           name + '线连续 ' + str(streak) + ' 个阶段都在上抬；单阶段只抬一条线不等于可以让同一条线连涨整轮，'
                           + '需说明是分阶抬档（每档稳 ' + str(MIN_STABLE_WEEKS) + ' 周以上）还是持续递进',
                           {'streak': streak, 'volume': {str(k): v for k, v in volume.items()}})

    markers, has_ball = ball_rule_without_ball(p)
    if markers and not has_ball:
        require_review('ball_rules', '课表提到' + '、'.join(markers)
                       + '但没有任何球类课次，球前／球后约束为空转；有球时如何启用需明确',
                       {'markers': markers})

    for g in p['objectives']:
        if actual and not g.get('capability_ids'):
            missing.append(g['id'] + ': 未关联能力词表')
        basis = g.get('baseline_basis')
        if actual and not basis:
            missing.append(g['id'] + ': 缺少起点依据，可用用户自述或明确保守假设')
        if basis:
            if basis['date'] and basis['date'] > p['start_date']:
                errors.append(g['id'] + ': baseline after plan start')
            if (basis['adequacy'] != 'sufficient' or basis['type'] == 'unknown') and not (context and context['uncertainty_actions']):
                missing.append(g['id'] + ': 有限或未知起点需明确保守初始剂量；不要求额外测试或逐次日志')
        if context:
            modes = {c['capability_id']: c['mode'] for c in context['coverage']}
            for c in g.get('capability_ids', []):
                if modes.get(c) != g['mode']:
                    errors.append(g['id'] + ': objective/coverage mode mismatch ' + c)
        if actual and g['mode'] == 'develop':
            stages = g.get('progression_plan', [])
            if not stages:
                missing.append(g['id'] + ': 缺少预先安排的阶段剂量与递进')
            covered_weeks = []
            for stage in stages:
                first, last = stage['first_week'], stage['last_week']
                if first > last or last > p['duration_weeks']:
                    errors.append(g['id'] + ': invalid progression stage range')
                covered_weeks.extend(range(first, last + 1))
                for w in p['weeks']:
                    if first <= w['number'] <= last and w['detail_status'] == 'scheduled':
                        ss = [s for s in p['sessions'] if s['week_number'] == w['number'] and g['id'] in s['goal_ids']]
                        matching = [s for s in ss if any(item_capabilities(x, assets) & set(g.get('capability_ids', [])) for m in s['modules'] for x in m['items'])]
                        if len(matching) < stage['session_frequency']:
                            missing.append(g['id'] + '/week ' + str(w['number']) + ': 已展开刺激课数少于阶段预定频率')
            if stages and sorted(covered_weeks) != list(range(1, p['duration_weeks'] + 1)):
                errors.append(g['id'] + ': progression stages must cover each plan week exactly once')

    windows = p['profile'].get('windows', [])
    for w in windows:
        if minutes(w['start']) >= minutes(w['end']):
            errors.append('availability window must end after start')
    intervals, daily = {}, {}
    for s in p['sessions']:
        daily.setdefault(s['date'], []).append(s)
        if 'start_time' in s:
            start = minutes(s['start_time'])
            end = start + s['duration_minutes']
            if end > 1440:
                errors.append(s['id'] + ': session crosses midnight')
            intervals.setdefault(s['date'], []).append((start, end, s))
            weekday = dt.date.fromisoformat(s['date']).weekday()
            if windows and not any(w['weekday'] == weekday and minutes(w['start']) <= start and end <= minutes(w['end']) for w in windows):
                errors.append(s['id'] + ': outside availability window')
        elif actual and windows:
            missing.append(s['id'] + ': 已提供具体时间窗口，需给出开始时间以核实')
        for m in s['modules']:
            for item in m['items']:
                if actual and not item.get('dose_basis'):
                    missing.append(s['id'] + '/' + item['unit_id'] + ': 剂量依据未提供，可采用保守起点与预定递进')
                a = assets.get(item['unit_id'], {})
                requires_contacts = a.get('requires_contact_count') or a.get('id') in ('landing', 'low_jump')
                if requires_contacts:
                    if actual and item.get('contacts_per_rep') is None:
                        missing.append(s['id'] + ': 跳跃接触量未定义')
                    elif item.get('contacts_per_rep') is not None and item['contacts_per_rep'] <= 0:
                        errors.append(s['id'] + '/' + item['unit_id'] + ': landing contacts must be positive')
    for date, ss in daily.items():
        if len(ss) > 1 and any('start_time' not in s for s in ss):
            missing.append(date + ': 一日两练需明确各课开始时间')
        # 硬约束：大重量推与强泳不排同日（上肢叠加，泳姿技术会被推的力量疲劳改写）
        heavy_push = [x for x in ss if x['kind'] == 'strength' and x['recovery_cost'] == 'high']
        hard_swim = [x for x in ss if x['kind'] == 'swim' and x['recovery_cost'] == 'high']
        if heavy_push and hard_swim:
            errors.append(date + ': 大重量力量课与高强度泳课同日（' + heavy_push[0]['id'] + '/' + hard_swim[0]['id'] +
                          '）；推的力量疲劳会改写泳姿技术，必须拆到不同日')

    # 结构性限制：no_impact / no_load / no_overhead，按 assets 的 impact 与 category 扫全计划
    IMPACT_KINDS = {'jump', 'hop', 'bound', 'loaded_jump', 'loaded_receiving_foot_transition',
                    'running', 'step'}
    lims = (p.get('design_context') or {}).get('limitations') or []
    if lims:
        for lim in lims:
            if lim.get('scope'):
                review.append('限制需人工二审：' + (lim.get('region') or '部位') + '「' + lim.get('rule') +
                              '」的 scope 「' + lim.get('scope') + '」脚本只按 rule 全库扫，部位与细目由人核对')
    if lims:
        seen_until = set()
        for s_ in p['sessions']:
            wk_s = s_.get('week_number') or 0
            # 复评提醒按「周 × 限制」报一次，不按动作重复刷屏
            for lim in lims:
                rule_l = lim.get('rule')
                region_l = lim.get('region') or '限制部位'
                uw = lim.get('until_week') or 0
                if uw and wk_s >= uw and (wk_s, region_l, rule_l) not in seen_until:
                    seen_until.add((wk_s, region_l, rule_l))
                    review.append('限制复评到期（week ' + str(wk_s) + '）：' + region_l + '「' + rule_l +
                                  '」登记到第 ' + str(uw) + ' 周，复核核对后再继续；到顶不自动解除。解除条件：' +
                                  (lim.get('clear_when') or '未写，需人工确认'))
            for m in s_['modules']:
                for i in m['items']:
                    aid = i.get('unit_id') or ''
                    a = assets.get(aid) if isinstance(assets, dict) else None
                    if not a:
                        continue
                    for lim in lims:
                        rule = lim.get('rule')
                        region = lim.get('region') or '限制部位'
                        if rule == 'no_impact' and (a.get('impact') in IMPACT_KINDS):
                            errors.append('限制冲突：' + region + ' 登记 no_impact，但 ' + s_['id'] + '／' + m['title'] +
                                          ' 排了 ' + (a.get('name') or aid) + '（impact=' + str(a.get('impact')) + '）')
                        if rule == 'no_load' and a.get('category') == 'strength' and i['dose'].get('load'):
                            errors.append('限制冲突：' + region + ' 登记 no_load，但 ' + s_['id'] + '／' + m['title'] +
                                          ' 给 ' + (a.get('name') or aid) + ' 加了负荷')
                        if rule == 'no_overhead' and a.get('category') in ('strength', 'power'):
                            _task = (a.get('primary_task') or '') + (a.get('name') or '')
                            if any(k in _task for k in ('过顶', '推举', 'overhead', 'press')):
                                errors.append('限制冲突：' + region + ' 登记 no_overhead，但 ' + s_['id'] + '／' + m['title'] +
                                              ' 排了 ' + (a.get('name') or aid))

    # 硬约束：每周高强度课上限与单次长跑占比（此前只写在文档里，脚本不查）
    run_peak_by_block = {}   # block_id -> 该阶段已出现的单次最长跑（距离口径），供单跑周比对
    run_peak_minutes_by_block = {}   # 同上，纯时长处方用
    swim_prev = {}   # (block_id, 课型) -> (日期, 泳总量 m)，供涨幅核算
    by_week = {}
    for s in p['sessions']:
        by_week.setdefault(s['week_number'], []).append(s)
    for wk in sorted(by_week):
        ss_w = by_week[wk]
        high = [s for s in ss_w if s['recovery_cost'] == 'high' or (s.get('session_rpe') or 0) >= 8]
        # 只有阶段性限制占用恢复预算；长期结构性限制只改动作选择，不降额度（未标注按阶段性=保守）
        active_lims = [l for l in lims if (l.get('kind') or '阶段性') == '阶段性']
        hi_cap = 3 if active_lims else 4
        if len(high) > hi_cap:
            errors.append('week ' + str(wk) + ': 高强度课 ' + str(len(high)) + ' 次，超过每周 ' + str(hi_cap) + ' 次上限（' +
                          '、'.join(s['id'] for s in high) + '）')
        # 跑课量核算。原书第 4 章只管 L 长跑、按周里程：周量 <40 英里(≈64km) 时 ≤30%，≥40 英里取 min(25%, 150 分钟对应量)。
        # 下面按跑次分档的 30/40/55 与 >64km 收 0.25 都是**包内校准**，套在「本周最长一次跑课 ÷ 周跑动」上，
        # 与原文的课型、分母、单位都不同，报错文案里必须写「包内」，不得挂 Daniels 名下。I ≤8%、R ≤5% 才是原书口径。
        run_lines = []
        for s_ in ss_w:
            if s_['kind'] != 'run':
                continue
            total = 0
            i_m = r_m = 0
            mins = 0
            for m in s_['modules']:
                for i in m['items']:
                    _id = i.get('unit_id') or ''
                    d = i['dose']
                    sets = d.get('sets') or 1
                    if _id == 'aerobic_run_intervals':
                        i_m += (d.get('distance_m') or 0) * sets
                    elif _id in ('repetition_run', 'uphill_speed_repetitions'):
                        r_m += (d.get('distance_m') or 0) * sets
                    total += (d.get('distance_m') or 0) * sets
                    if _id not in RUN_NON_RUN_UNITS:
                        mins += (d.get('duration_minutes') or 0) * sets
            run_lines.append((s_['id'], total, i_m, r_m, mins))
        if run_lines:
            # 跑次＝全部跑课，不是「给了距离的课数」：按给了距离的课数算，三跑周只两课有距离就松成 2 跑档（55%），
            # 一课有距离还会掉进单跑周分支、比例完全不核算。
            rc = len(run_lines)
            blk = ss_w[0].get('block_id') if ss_w else None
            n_dist = len([x for x in run_lines if x[1]])
            n_time = len([x for x in run_lines if x[4]])
            if n_dist == rc:
                basis, idx, unit = 'dist', 1, 'm'
            elif n_time == rc:
                basis, idx, unit = 'time', 4, '分钟'
                if n_dist:
                    # 距离不全就不许拿部分距离当分母：分母少一半，比例必然偏大，报出来的错也不是那条真错；
                    # 但也不能因此不核算——全周统一按分钟算，跑次仍按真实跑次数
                    review.append('week ' + str(wk) + ': 跑量口径不统一（' + str(rc) + ' 次跑课里 ' + str(n_dist) +
                                  ' 次给了距离、' + str(rc) + ' 次都有时长），不拿部分距离当分母，全周统一按时长口径'
                                  '核算；距离口径占比未核定——不是已通过')
                else:
                    review.append('week ' + str(wk) + ': 跑课只给时长、没给距离（使用期询问项，非阻断）：'
                                  '有配速/距离就按距离口径复核，没有就按时长口径核算——距离口径的占比属未核定，不是已通过')
            else:
                basis = None
                review.append('week ' + str(wk) + ': 跑课里 ' + str(rc - n_time) + ' 次既没距离也没时长，跑量无法核算'
                              '——本周最长跑占比与 I/R 比例未核定，不是已通过')
            week_total = sum(x[idx] for x in run_lines) if basis else 0
            if basis:
                longest = max(run_lines, key=lambda x: x[idx])
                peak = run_peak_by_block if basis == 'dist' else run_peak_minutes_by_block
                if rc >= 2:
                    cap = {4: 0.30, 3: 0.40, 2: 0.55}.get(rc, 0.30)
                    if basis == 'dist' and week_total >= 64000:
                        cap = min(cap, 0.25)
                    if longest[idx] > week_total * cap:
                        errors.append('week ' + str(wk) + ': 单次最长跑 ' + str(int(longest[idx])) + ' ' + unit +
                                      ('（时长口径）' if basis == 'time' else '') +
                                      ' 占本周跑量 ' + str(int(week_total)) + ' ' + unit + ' 的 ' +
                                      str(round(100.0 * longest[idx] / week_total)) +
                                      '%，超过 ' + str(int(cap * 100)) + '% 包内上限（' + longest[0] +
                                      '，本周跑 ' + str(rc) + ' 次；分档是包内校准，原书只对 L 长跑按周里程限量）')
                    peak[blk] = max(peak.get(blk) or 0, longest[idx])
                else:
                    # 单跑周比例不适用，但不等于可以把原周量塞进一次：单次时长受本阶段已出现的单次最长值约束
                    seed = peak.get(blk)
                    if not seed:
                        review.append('week ' + str(wk) + ': 单跑周且本阶段没有可比的单次值，单次时长未核定——'
                                      '按本阶段已有的单次最长值定，不要当已通过')
                    elif longest[idx] > seed:
                        review.append('week ' + str(wk) + ': 单跑周单次 ' + str(int(longest[idx])) + ' ' + unit +
                                      ' 超过本阶段已出现的单次最长 ' + str(int(seed)) + ' ' + unit +
                                      '，须说明这不是把原周量塞进一次（' + longest[0] + '）')
                    peak[blk] = max(seed or 0, longest[idx])
            for _id, _tot, _i, _r, _min in (run_lines if basis == 'dist' else []):
                if _i and week_total and _i > week_total * 0.08:
                    errors.append('week ' + str(wk) + ': ' + _id + ' 单次 I 跑动 ' + str(int(_i)) +
                                  ' m 占周量 ' + str(int(week_total)) + ' m 的 ' + str(round(100.0 * _i / week_total)) +
                                  '%，超过 8% 上限（原书 I 课按周里程 ≤8%）')
                if _r and week_total and _r > week_total * 0.05:
                    errors.append('week ' + str(wk) + ': ' + _id + ' 单次 R 跑动 ' + str(int(_r)) +
                                  ' m 占周量 ' + str(int(week_total)) + ' m 的 ' + str(round(100.0 * _r / week_total)) +
                                  '%，超过 5% 上限（原书 R 课按周里程 ≤5%）')
        # 泳量涨幅：同一阶段内相邻两次同课型的泳总量涨幅 >10% 报 review。10% 是包内上限带，不是通用生理阈值；
        # 只对给了泳距的剂量生效，纯分钟档标未核定。
        for s_ in sorted([x for x in ss_w if x['kind'] == 'swim'], key=lambda x: x['date']):
            swim_total = 0
            for m in s_['modules']:
                for i in m['items']:
                    d = i['dose']
                    swim_total += (d.get('distance_m') or 0) * (d.get('sets') or 1)
            key = (s_.get('block_id'), s_.get('course_id') or '泳')
            prev = swim_prev.get(key)
            if not swim_total:
                review.append('week ' + str(wk) + ': ' + s_['id'] + ' 没给泳距，泳量涨幅未核定——不是已通过')
                continue
            if prev and swim_total > prev[1] * 1.10:
                review.append('week ' + str(wk) + ': ' + s_['id'] + ' 泳总量 ' + str(int(prev[1])) + ' → ' +
                              str(int(swim_total)) + ' m（+' + str(round(100.0 * (swim_total - prev[1]) / prev[1])) +
                              '%），超过同一阶段内相邻两次 ≤10% 的涨幅带（10% 是包内上限，不是通用生理阈值）')
            swim_prev[key] = (s_['date'], swim_total)
    for date, iv in intervals.items():
        iv.sort(key=lambda x: x[0])
        for (_, end, a), (next_start, _, b) in zip(iv, iv[1:]):
            if next_start < end:
                errors.append(date + ': overlapping sessions ' + a['id'] + '/' + b['id'])
            elif a['recovery_cost'] != 'low' and b['recovery_cost'] != 'low':
                key = ':'.join(sorted([a['id'], b['id']]))
                require_review('same_day:' + key, date + ': 两次非低成本训练，间隔' + str(next_start - end) + '分钟；需说明重点、局部重叠及恢复取舍',
                               sorted([recovery_context(a), recovery_context(b)], key=lambda x: x['id']))
    ss = p['sessions']
    for i, a in enumerate(ss):
        for b in ss[i + 1:]:
            days = abs((dt.date.fromisoformat(a['date']) - dt.date.fromisoformat(b['date'])).days)
            if days == 1 and a['recovery_cost'] == b['recovery_cost'] == 'high' and set(a['fatigue_regions']) & set(b['fatigue_regions']):
                key = ':'.join(sorted([a['id'], b['id']]))
                require_review('overlap:' + key, a['id'] + '/' + b['id'] + ': 相邻高成本课局部重叠，需明确恢复取舍',
                               sorted([recovery_context(a), recovery_context(b)], key=lambda x: x['id']))
    resolutions = (context or {}).get('review_resolutions', [])
    resolution_ids = [r['review_id'] for r in resolutions]
    if len(resolution_ids) != len(set(resolution_ids)):
        errors.append('duplicate review resolution id')
    known = {r['review_id']: r for r in resolutions}
    required_ids = {r['review_id'] for r in requirements}
    for r in resolutions:
        if r['review_id'] not in required_ids:
            review.append(r['review_id'] + ': 历史处理记录，当前安排未再触发该提醒')
    for requirement in requirements:
        resolution = known.get(requirement['review_id'])
        current = resolution and resolution.get('context_hash') == requirement['context_hash']
        requirement['resolution'] = resolution if current else None
        if current:
            review.append(requirement['review_id'] + ': 已明确处理 — ' + resolution['rationale'])
        else:
            message = '旧处理与当前实质训练参数不一致，需重新复审；' if resolution else ''
            review.append(requirement['review_id'] + ': ' + message + requirement['message'])
            if actual:
                missing.append(requirement['review_id'] + ': 需在review_resolutions记录当前context_hash、本项决定与具体理由')
    return errors, review, list(dict.fromkeys(missing)), requirements
