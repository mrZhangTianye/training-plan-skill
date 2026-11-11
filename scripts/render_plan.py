# -*- coding: utf-8 -*-
"""Render concise executable blocks and source-free planning summaries."""
import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from string import Template
from common import ROOT, read_json, library
from validate_plan import validate
from group_schedule import sequence, schedule
from endurance_stats import calculate as calculate_endurance, strength_summary


def text(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\\', '\\\\').replace('|', '\\|').replace('`', '\\`').replace('\n', '<br>')


def table(headers, rows):
    return '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n' + ''.join('| ' + ' | '.join(text(c) for c in row) + ' |\n' for row in rows)


def number(value):
    return f'{value:g}'


def minute_text(minutes):
    total = round(minutes * 60)
    whole, seconds = divmod(total, 60)
    return str(whole) + '分' + (str(seconds) + '秒' if seconds else '')


def time_dose(minutes):
    return number(minutes * 60) + '秒' if minutes < 1 else number(minutes) + '分钟'


def dose_string(d):
    parts = []
    if d['reps'] is not None:
        value = str(d['reps'])
    elif d['duration_minutes'] is not None:
        value = time_dose(d['duration_minutes'])
    elif d['distance_m'] is not None:
        value = number(d['distance_m']) + '米'
    else:
        value = '待明确'
    if d['sets'] is not None and d['reps'] is not None and d['distance_m'] is not None:
        value = str(d['sets']) + '轮×' + str(d['reps']) + '×' + number(d['distance_m']) + '米'
    elif d['sets'] is not None:
        value = str(d['sets']) + '×' + value
    if d['per_side']:
        value += '/侧'
    parts.append(value)
    # Multiple dose dimensions are retained when the plan explicitly specifies them.
    if d['reps'] is not None and d['duration_minutes'] is not None:
        parts.append(time_dose(d['duration_minutes']) + '/组' + ('/侧' if d['per_side'] else ''))
    if (d['reps'] is not None or d['duration_minutes'] is not None) and d['distance_m'] is not None and not (d['sets'] is not None and d['reps'] is not None):
        parts.append(number(d['distance_m']) + '米/组' + ('/侧' if d['per_side'] else ''))
    return '，'.join(parts)


def intensity_string(load):
    parts = []
    description = (load.get('execution_target') or load['description']).strip().rstrip('。.')
    if load['target_rpe'] is not None:
        value = 'RPE' + number(load['target_rpe'])
        if 6 <= load['target_rpe'] <= 10:
            value += '，约余' + number(10 - load['target_rpe']) + '次'
        # 有 RPE 时不再显示负荷描述：RPE 与目标余次数已经是强度本身
        parts.append(value)
    elif description:
        parts.append(description)
    if load['reference_weight_kg'] is not None:
        suffix = {'per_hand': '/手', 'added': '（额外负重）', 'total': ''}.get(load.get('reference_weight_unit')) or ''
        parts.append(number(load['reference_weight_kg']) + 'kg' + suffix + '（参考）')
    elif (load.get('selection_method') or '').strip():
        parts.append('按' + load['selection_method'].strip().rstrip('。.'))
    elif (load.get('reference_weight_basis') or '').startswith('待补'):
        parts.append('参考重量待补')
    return '；'.join(parts) or '—'


def recovery_string(dose):
    if dose.get('recovery_type') == 'sendoff':
        return '每' + number(dose['sendoff_seconds']) + '秒出发'
    if dose['rest_seconds'] == 0:
        return '—'
    return number(dose['rest_seconds']) + '秒' + ('主动恢复' if dose.get('recovery_type') == 'active_recovery' else '')


def execution_note(item, asset):
    # Necessary instructions are explicit presentation data; background notes stay backstage.
    return item.get('execution_note', '').strip().rstrip('。.')


# 环节编号与侧重标签来自数据文件 references/frames.json（改数据不改脚本）。
_FRAMES = read_json(ROOT / 'references' / 'frames.json')
FRAME_ORDER = [f['title'] for f in _FRAMES['frames']]
FRAME_NO = {f['title']: f['no'] for f in _FRAMES['frames']}
FOCUS_LABELS = _FRAMES['focus_labels']


def module_label(module, letter, counter):
    """力量课环节照 Table 11.10 固定编号（速度段阶段1不排，号留空）；泳课按本课顺序编号。"""
    if letter:
        return str(FRAME_NO['力量']) + '-' + letter
    for name, no in FRAME_NO.items():
        if module['title'].startswith(name):
            return str(no)
    counter[0] += 1
    return str(counter[0])


def group_heading(module, letter):
    label = '配对' if len(module['items']) == 2 else '三联组'
    counts = [x['dose']['sets'] for x in module['items']]
    dose = str(counts[0]) + '轮' if len(set(counts)) == 1 else '／'.join(map(str, counts)) + '组'
    # 标题里已经写明结构（前置组合/力量配对/后续三联）时，不再重复追加配对或三联组
    named = any(word in module['title'] for word in ('组合', '配对', '三联'))
    return letter + '组 · ' + module['title'] + ('' if named else '（' + label + '）') + ' · ' + dose


def group_order_note(module, letter):
    try:
        timeline = schedule(module)
    except ValueError:
        order = '→'.join(letter + str(index) for index in sequence(module))
        return '组序：' + order + '；完整组工作时间待补，恢复与整课时间尚不能核定。\n\n'
    counts = [x['dose']['sets'] for x in module['items']]
    if len(set(counts)) == 1 and 'set_sequence' not in module:
        size = len(module['items'])
        gaps = [row['wait'] for row in timeline[size:]]
        # A short round instruction is valid only when all wait falls at round starts.
        if not any(row['wait'] for i, row in enumerate(timeline) if i % size):
            order = '→'.join(letter + str(i + 1) for i in range(size))
            note = '顺序：' + order + '，共' + str(counts[0]) + '轮'
            if gaps and max(gaps) > 0:
                note += '；轮间至少' + minute_text(math.ceil(max(gaps)) / 60)
            return note + '。\n\n'
    steps = []
    for row in timeline:
        if row['wait']:
            steps.append('休息' + number(math.ceil(row['wait'])) + '秒')
        steps.append(letter + str(row['item']))
    return '组序：' + '→'.join(steps) + '。\n\n'


def distance_text(meters):
    return number(meters / 1000) + '公里' if meters >= 1000 else number(meters) + '米'


def run_volume(row):
    if row.get('run_time_complete', True):
        body = '总跑动' + number(row['run_minutes']) + '分钟'
    else:
        body = '总跑动时间未核定'
    if row['run_distance_m'] is None or row['run_distance_status'] == 'unknown':
        body += '；距离未估算'
    else:
        body += '；' + ('预计' if row['run_distance_status'] == 'estimated' else '') + '总跑量' + distance_text(row['run_distance_m'])
    return body


def swim_volume(row):
    if row['swim_distance_m'] is None or not row.get('swim_distance_complete', True):
        return '总泳距未核定'
    return '总泳距' + number(row['swim_distance_m']) + '米'


def session_volume(row, kind=None):
    parts = []
    if kind == 'run' or row['run_minutes'] or (row['run_distance_m'] or 0) or not row.get('run_time_complete', True):
        parts.append(run_volume(row))
    if kind == 'swim' or (row['swim_distance_m'] or 0) or not row.get('swim_distance_complete', True):
        parts.append(swim_volume(row))
    return '；'.join(parts)


def week_endurance_body(row):
    volume = session_volume(row)
    if not volume:
        return ''
    body = '计划周总量：' + volume + '。\n'
    total = row['run_minutes']
    if total or not row.get('run_time_complete', True):
        complete = row.get('run_time_complete', True)
        def share(amount):
            if not complete or not total or row['unclassified_run_minutes']:
                return '占比未核定'
            percent = f'{amount / total * 100:.1f}'.rstrip('0').rstrip('.')
            return percent + '%'
        body += '计划跑步时间分配：轻松' + number(row['easy_minutes']) + '分钟（' + share(row['easy_minutes']) + '），非轻松' + number(row['non_easy_minutes']) + '分钟（' + share(row['non_easy_minutes']) + '）'
        labels = {'tempo': '节奏', 'interval': '间歇', 'fast': '短快段'}
        body += '；' + '、'.join(label + number(row['non_easy_by_type'].get(key, 0)) + '分钟' for key, label in labels.items())
        if row['unclassified_run_minutes']:
            body += '；未分类' + number(row['unclassified_run_minutes']) + '分钟（' + share(row['unclassified_run_minutes']) + '）'
        body += '。\n'
    return body


def strength_week_body(p, week, assets):
    summaries = strength_summary(p, week)
    if not summaries:
        return ''
    rows = []
    labels = FOCUS_LABELS
    for summary in summaries:
        for prescription in summary['prescriptions']:
            name = prescription.get('display_name') or assets[summary['unit_id']]['name']
            rows.append([name, prescription['session_id'], labels[summary['wave_role']], dose_string(prescription['dose']), intensity_string(prescription['dose']['load'])])
    return '本周主力波动：\n\n' + table(['主力动作', '课程编号', '侧重', '剂量', '强度'], rows) + '\n'


def session_body(s, assets, restrictions=None, include_exception=True, endurance=None, skip=None):
    body = '日期：' + s['date'] + ' ｜ 约' + number(s['duration_minutes']) + '分钟（参考）\n\n'
    if endurance is None:
        endurance = calculate_endurance({'sessions': [s], 'duration_weeks': s['week_number']}, assets)['sessions'][s['id']]
    volume = session_volume(endurance, s['kind'])
    if volume:
        body += volume + '\n\n'
    body += '本次小目标：' + text(s['mini_goal']) + '\n\n'
    if s.get('swim_focus'):
        focus = s['swim_focus']
        body += '今天只关注：' + text(focus['goal']) + '\n\n'
        body += '观察：' + text(focus['observation']) + '\n\n'
    if s.get('start_time'):
        body += '开始时间：' + text(s['start_time']) + '\n\n'
    body += modules_body([m for m in s['modules'] if not (skip and m['title'] in skip)], assets)
    return body


def modules_body(modules, assets):
    body = ''
    group_count = 0
    counter = [0]
    for module in modules:
        letter = None
        if module.get('group_label'):
            letter = chr(ord('A') + group_count)
            group_count += 1
        number_label = module_label(module, letter, counter)
        # 去掉 group_heading 自带的"A组 · "：编号 10-A 已经说明这是哪个组合
        heading = (number_label + ' ' + group_heading(module, letter)[len(letter) + 4:]) if letter else (number_label + '. ' + module['title'])
        body += '### ' + text(heading) + '\n\n'
        if letter:
            body += group_order_note(module, letter)
        strength = module.get('group_label') is not None
        rows, notes = [], False
        for index, item in enumerate(module['items'], 1):
            asset, dose = assets[item['unit_id']], item['dose']
            note = execution_note(item, asset)
            notes = notes or bool(note)
            name = item.get('display_name', asset['name'])
            if letter:
                name = letter + str(index) + ' ' + name
            dosed = dose_string(dose)
            if not strength:
                rest = recovery_string(dose)
                if rest != '—':
                    dosed += '（休' + rest + '）'
            rows.append([name, dosed, intensity_string(dose['load']), recovery_string(dose), note or '—'])
        if strength:
            headers = ['动作', '剂量', '强度', '同动作恢复']
            if notes:
                headers.append('必要提示')
                body += table(headers, rows) + '\n'
            else:
                body += table(headers, [row[:4] for row in rows]) + '\n'
        elif notes:
            body += table(['动作', '剂量', '必要提示'], [row[:2] + [row[4]] for row in rows]) + '\n'
        else:
            body += table(['动作', '剂量'], [row[:2] for row in rows]) + '\n'
    return body


def common_prep(sessions):
    """本周所有力量课完全相同的环节（同标题同内容）只写一次，各天只列当天变的部分。"""
    strength = [x for x in sessions if x['kind'] == 'strength']
    if len(strength) < 2:
        return []
    def signature(module):
        # item 的 id 带课次后缀，比较时要去掉，否则同一段准备永远判为不同
        items = [{k: v for k, v in item.items() if k != 'id'} for item in module['items']]
        return module['title'], json.dumps(items, sort_keys=True, ensure_ascii=False)

    keys = [signature(m) for m in strength[0]['modules']]
    shared = []
    for index, key in enumerate(keys):
        for other in strength[1:]:
            if index >= len(other['modules']):
                break
            if signature(other['modules'][index]) != key:
                break
        else:
            shared.append(key[0])
    return shared


def aerobic_body(row):
    body = '计划有氧净运动：' + minute_text(row['net_minutes']) + '；计划中等当量：' + minute_text(row['equivalent_minutes']) + '（中等＋2×较强）。'
    if row['unclassified_items']:
        body += '尚有' + str(len(row['unclassified_items'])) + '个工作项未核定强度或净时间，不计入当量。'
    if row['target_minutes'] is not None:
        body += '本周安排目标：' + minute_text(row['target_minutes']) + '当量；'
        if row['goal_status'] == 'planned_meets':
            body += '按标注预计达到。'
        elif row['goal_status'] == 'gap':
            body += '仍差' + minute_text(row['target_minutes'] - row['equivalent_minutes']) + '，需调整安排。'
        else:
            body += '未核定，不能称达标。'
    return body + '\n'


def identity(value, field, fallback):
    return ('id', value[field]) if value.get(field) else ('semantic',) + fallback


def semantic_groups(records, field, fallback, context):
    """Group (parent, week, local token, value) records without positional week matching."""
    keyed, counts = [], {}
    for parent, week, token, value in records:
        key = identity(value, field, fallback(value))
        counts[parent, key] = counts.get((parent, key), 0) + 1
        keyed.append((key, parent, week, token, value))
    ambiguous = {key for (_, key), count in counts.items() if count > 1}
    explicit = [key[1] for key in ambiguous if key[0] == 'id']
    if explicit:
        raise ValueError(context + '的稳定编号重复：' + '、'.join(map(str, sorted(explicit))))
    groups = {}
    for key, parent, week, token, value in keyed:
        # The local token only separates an ambiguous record. It never matches weeks.
        if key in ambiguous:
            key = ('unmatched', parent, token)
        groups.setdefault(key, []).append((parent, week, token, value))
    return groups, bool(ambiguous)


def stage_matrix(p, block, assets):
    week_numbers = list(range(block['first_week'], block['last_week'] + 1))
    sessions = sorted((s for s in p['sessions'] if s['week_number'] in week_numbers), key=lambda s: (s['week_number'], s['date'], s.get('start_time', ''), s['id']))
    records = [(s['week_number'], s['week_number'], s['id'], s) for s in sessions]
    courses, ambiguous = semantic_groups(records, 'course_id', lambda s: (s['kind'], s['title']), '课程')
    if not courses:
        return '该阶段尚未展开单次剂量。\n'
    notices = ['同周存在重名课程，已按日期分别展示，未跨周合并；请区分这些课程的名称或稳定编号。'] if ambiguous else []
    body, omitted_preparation, stage_notes = '', False, {}
    for course_key, course_records in courses.items():
        first_session = course_records[0][3]
        title = first_session['title']
        if course_key[0] == 'unmatched':
            title += ' · ' + first_session['date']
        module_records = [(session['id'], week, index, module) for _, week, _, session in course_records for index, module in enumerate(session['modules'])]
        modules, ambiguous = semantic_groups(module_records, 'id', lambda m: ('group', m['group_label']) if m.get('group_label') else ('title', m['title']), title + '模块')
        if ambiguous:
            notices.append(title + '：模块名称重复，未跨周合并；请区分这些模块的名称或稳定编号。')
        course_body = ''
        for module_records in modules.values():
            first_module = module_records[0][3]
            heading = first_module['title']
            group_sizes = {len(module['items']) if module.get('group_label') else 0 for _, _, _, module in module_records}
            is_strength = group_sizes != {0}
            item_records = [(parent, week, index, entry) for parent, week, _, module in module_records for index, entry in enumerate(module['items'])]
            # 行动作的身份用单元编号，不能用课次内唯一的 item id，否则跨周无法合并
            item_groups, ambiguous = semantic_groups(item_records, 'id', lambda entry: (entry['unit_id'], entry.get('display_name', assets[entry['unit_id']]['name'])), title + '/' + heading + '动作')
            if ambiguous:
                notices.append(title + '/' + heading + '含重名动作，未跨周合并；请区分这些动作的名称或稳定编号。')
            rows = []
            for entries in item_groups.values():
                name = entries[0][3].get('display_name', assets[entries[0][3]['unit_id']]['name'])
                row = {'name': name, 'values': {}, 'parameters': {}, 'explicit_notes': {}}
                for _, week, _, entry in entries:
                    entry_name = entry.get('display_name', assets[entry['unit_id']]['name'])
                    intensity, recovery = intensity_string(entry['dose']['load']), recovery_string(entry['dose'])
                    value = dose_string(entry['dose'])
                    if entry_name != name:
                        value = entry_name + ' · ' + value
                    if intensity != '—' and is_strength:
                        value += ' · ' + intensity
                    if recovery != '—':
                        value += ' · 恢复' + recovery
                    row['values'][week] = value
                    note = execution_note(entry, assets[entry['unit_id']])
                    row['explicit_notes'][week] = note
                    row['parameters'][week] = (dose_string(entry['dose']), intensity, recovery, note, entry_name, entry['unit_id'])
                rows.append(row)
            preparation = group_sizes == {0} and any(word in heading for word in ('滚压', '呼吸', '准备', '热身', '冷身', '整理', '放松游', '软组织', '拉伸', '纠正', '激活', '原地', '行进技能', '动作技能'))
            fixed = all(set(row['parameters']) == set(week_numbers) and len(set(row['parameters'].values())) == 1 for row in rows)
            fixed = fixed and len({module['title'] for _, _, _, module in module_records}) == 1
            if preparation and fixed:
                omitted_preparation = True
                continue
            for row in rows:
                if len(set(row['explicit_notes'].get(week, '') for week in week_numbers)) > 1:
                    for week, note in row['explicit_notes'].items():
                        if note:
                            stage_notes.setdefault(note, set()).add(week)
            if group_sizes != {0}:
                label = '配对' if group_sizes == {2} else '三联组' if group_sizes == {3} else '组合'
                if label not in heading:
                    heading += '（' + label + '）'
            for _, week, _, module in module_records:
                if module['title'] != first_module['title']:
                    stage_notes.setdefault('模块：' + module['title'], set()).add(week)
            course_body += '#### ' + text(heading) + '\n\n'
            # 阶段视图按周列剂量，不做"四周恒定"折叠：跨周对齐必须一眼可见
            course_body += table(['动作／单元'] + ['W' + str(week) for week in week_numbers], [[row['name']] + [row['values'].get(week, '—') for week in week_numbers] for row in rows]) + '\n'
        if course_body:
            body += '### ' + text(title) + '\n\n' + course_body
            for _, week, _, session in course_records:
                if session['title'] != first_session['title']:
                    stage_notes.setdefault('课程：' + session['title'], set()).add(week)
    if omitted_preparation:
        body = '固定准备与整理见当周单课；下表逐周展示主工作与变化剂量，组合实际执行顺序见当周单课。\n\n' + body
    if notices:
        body = '\n'.join(text(notice) for notice in dict.fromkeys(notices)) + '\n\n' + body
    if stage_notes:
        body += '\n## 逐周提示\n\n' + '\n'.join('- W' + '/W'.join(str(week) for week in sorted(weeks)) + '：' + text(note) + '。' for note, weeks in stage_notes.items()) + '\n'
    return body or '该阶段仅有固定准备与整理，见当周单课。\n'


def selection_error(label, requested, available):
    provided = '未提供' if requested is None else str(requested)
    return ValueError(label + '编号“' + provided + '”不存在；可用编号：' + '、'.join(map(str, available)))


def execution_gaps(p, result):
    if p['intended_use'] != 'actual' or result['ready_to_render_executable']:
        return ''
    problems = list(result.get('insufficient_basis', []))
    if p['arrangement']['status'] not in ('selected', 'confirmed'):
        problems.append('整体训练安排尚未选定，需先确定本次采用的结构。')
    required = {'goal_alignment', 'user_constraints', 'load_recovery', 'hierarchy', 'change_impact'}
    if {review['topic'] for review in p['design_review']} != required or any(review['outcome'] not in ('pass', 'tradeoff') for review in p['design_review']):
        problems.append('目标、执行条件、恢复或层级一致性的设计判断尚未完成。')
    if not problems:
        return ''
    return '执行前需补齐：\n\n' + '\n'.join('- ' + text(problem) for problem in dict.fromkeys(problems)) + '\n\n'


def render(p, view, week=None, block=None, session=None, allow_gaps=False):
    assets = library(); result = validate(p)
    if result['errors']:
        raise ValueError('; '.join(result['errors']))
    if p['intended_use'] == 'actual' and p['status'] == 'executable' and not allow_gaps:
        gaps = list(result.get('global_gaps') or [])
        blocked = list(result.get('blocked_weeks') or [])
        if gaps or blocked:
            raise ValueError('设计前提还没定，不能输出正式文档：' + '；'.join(
                gaps[:3] or ['W' + '/W'.join(str(w) for w in blocked[:5]) + ' 存在未定的动作或条件']))
    endurance = calculate_endurance(p, assets)
    status = '展示样稿，虚构用户，非正式处方' if p['intended_use'] == 'demo' else '执行版' if p['status'] == 'executable' and result['ready_to_render_executable'] else '草案，整体安排或训练细节待明确'
    summary_weeks = [str(w['number']) for w in p['weeks'] if w['detail_status'] == 'summary']
    if summary_weeks and view in ('overall', 'block'):
        status += '；W' + '/W'.join(summary_weeks) + '仅有概要，尚未展开执行课表'
    single_day = p.get('scope', {}).get('window') == 'day'
    end = dt.date.fromisoformat(p['start_date']) + dt.timedelta(days=p['duration_weeks'] * 7 - 1)
    fields = {'title': text(p['title']), 'status': status, 'version': str(p['version']), 'window': f'{p["start_date"]}至{end.isoformat()}，共{p["duration_weeks"]}周', 'body': ''}
    if single_day:
        fields['window'] = p['start_date'] + '，共1天（单日安排，非阶段周期）'
    if view == 'overall':
        fields['body'] = table(['目标', '安排', '预期变化'], [[g['capability'], {'develop': '发展', 'maintain': '维持', 'defer': '暂缓'}[g['mode']], g['desired_change']] for g in p['objectives']])
        fields['body'] += '\n' + text(p['arrangement']['rationale']) + '\n\n' + '\n'.join('- ' + text(x) for x in p['arrangement']['weekly_template']) + '\n\n'
        for b in p['blocks']:
            fields['body'] += ('## 当日安排 ' if single_day else '## W' + str(b['first_week']) + '–W' + str(b['last_week']) + ' ') + text(b['focus']) + '\n\n' + ('' if single_day else stage_matrix(p, b, assets) + '\n')
        rows = result['aerobic_summary']['weeks']
        if any(row['net_minutes'] or row['unclassified_items'] or row['target_minutes'] is not None for row in rows):
            fields['body'] += '\n## 有氧安排\n\n' + table(['周', '计划净运动', '计划中等当量', '本周目标', '状态'], [[row['week'], minute_text(row['net_minutes']), minute_text(row['equivalent_minutes']), '—' if row['target_minutes'] is None else minute_text(row['target_minutes']), {'planned_meets': '按标注预计达到', 'gap': '有缺口', 'unverified': '未核定', 'build_up': '渐进阶段', 'not_set': '未设当量目标'}[row['goal_status']]] for row in rows])
    elif view == 'block':
        b = next((x for x in p['blocks'] if x['id'] == block), None)
        if not b:
            raise selection_error('阶段', block, [x['id'] for x in p['blocks']])
        fields['title'] = text(b['focus'])
        fields['body'] = ('范围：' + p['start_date'] + '（单日，非阶段周期）' if single_day else '范围：W' + str(b['first_week']) + '–W' + str(b['last_week']) + '\n\n' + stage_matrix(p, b, assets))
    elif view == 'week':
        w = next((x for x in p['weeks'] if x['number'] == week), None)
        if not w:
            raise selection_error('周', week, [x['number'] for x in p['weeks']])
        fields['title'] = p['start_date'] + ' 单日课表' if single_day else f'第{week}周课表'
        ss = {s['id']: s for s in p['sessions']}
        if w['detail_status'] == 'summary':
            fields['body'] += '本周尚未展开完整日期课表。' + text(w['module_summary']) + '\n\n'
        rows = [[ss[sid]['date'] + (' ' + ss[sid]['start_time'] if ss[sid].get('start_time') else ''), ss[sid]['title'], session_volume(endurance['sessions'][sid], ss[sid]['kind']) or '—', number(ss[sid]['duration_minutes']) + '分钟'] for sid in w['session_ids']]
        rows += [[day, '休息', '—', '—'] for day in w['rest_days']]
        fields['body'] += table(['日期', '训练', '跑泳单次总量', '用时'], sorted(rows, key=lambda row: row[0])) + '\n'
        fields['body'] += strength_week_body(p, week, assets)
        fields['body'] += '\n' + week_endurance_body(next(r for r in endurance['weeks'] if r['week'] == week))
        fields['body'] += aerobic_body(next(r for r in result['aerobic_summary']['weeks'] if r['week'] == week))
        shared = common_prep([ss[sid] for sid in w['session_ids']])
        if shared:
            _has = lambda kw: any(any(str(m.get('title','')).startswith(kw) for m in ss[sid]['modules'])
                                  for sid in w['session_ids'] if ss[sid]['kind'] == 'strength')
            _spd = '' if _has('速度') else '（本阶段不排）'
            _ply = '' if _has('增强式') else '（本阶段不排）'
            _extra = {'速度': _spd, '增强式': _ply}
            _legend = '　'.join(str(f['no']) + f['title'] + _extra.get(f['title'], '') for f in _FRAMES['frames'])
            fields['body'] += ('\n力量课按固定编号排：' + _legend + '。\n')
            fields['body'] += '\n## 每日重复部分（每次力量课都一样）\n\n' + modules_body([m for m in ss[w['session_ids'][0]]['modules'] if m['title'] in shared], assets) + '\n'
        numbers = '、'.join(str(FRAME_NO[t]) for t in shared if t in FRAME_NO)
        for sid in sorted(w['session_ids'], key=lambda sid: (ss[sid]['date'], ss[sid].get('start_time', ''), sid)):
            if shared and ss[sid]['kind'] == 'strength':
                fields['body'] += '\n## ' + ss[sid]['date'] + ' ' + text(ss[sid]['title']) + '\n\n> 当日只列变化部分；' + numbers + ' 见上文每日重复部分。\n\n' + session_body(ss[sid], assets, include_exception=False, endurance=endurance['sessions'][sid], skip=shared)
            else:
                fields['body'] += '\n## ' + ss[sid]['date'] + ' ' + text(ss[sid]['title']) + '\n\n' + session_body(ss[sid], assets, include_exception=False, endurance=endurance['sessions'][sid], skip=shared)
    elif view == 'session':
        s = next((x for x in p['sessions'] if x['id'] == session), None)
        if not s:
            raise selection_error('单次课', session, [x['id'] for x in p['sessions']])
        fields['title'] = text(s['title']); fields['body'] = session_body(s, assets, p['profile']['restrictions'], endurance=endurance['sessions'][s['id']])
    fields['execution_gaps'] = execution_gaps(p, result)
    balls = p.get('ball_days', [])
    if view == 'week':
        balls = [b for b in balls if (dt.date.fromisoformat(b['date']) - dt.date.fromisoformat(p['start_date'])).days // 7 + 1 == week]
    if balls and view in ('overall', 'week'):
        fields['body'] += '\n## 固定球类安排（不是训练处方）\n\n' + table(['日期', '运动', '开始', '时长'], [[b['date'], text(b['sport']), b.get('start_time', '未提供'), str(b['duration_minutes'])+'分钟' if b.get('duration_minutes') is not None else '未核定'] for b in balls])
    return Template((ROOT / f'assets/templates/{view}.md').read_text()).substitute(fields)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan'); parser.add_argument('--view', choices=['overall', 'block', 'week', 'session'], required=True)
    parser.add_argument('--week', type=int); parser.add_argument('--block'); parser.add_argument('--session'); parser.add_argument('--output', required=True); parser.add_argument('--draft', action='store_true')
    args = parser.parse_args()
    try:
        p = read_json(args.plan); check = validate(p)
        if check['errors']:
            raise ValueError('; '.join(check['errors']))
        content = render(p, args.view, args.week, args.block, args.session, allow_gaps=args.draft)
        if not check['ready_to_render_executable'] and not args.draft:
            raise ValueError('当前计划尚不能作为执行版；如需查看待完善内容，请加--draft生成明确标注的草案。')
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(content, encoding='utf-8'); print(str(out))
        return 0
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
