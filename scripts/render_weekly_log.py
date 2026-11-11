#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周训练计划（记录式）渲染：一个文档 = 一周，一张表铺到底。

样式：一周一个文档、每天一张表铺到底（序号 | 动作 | 计划 | 要点 | 表现），末列留给练完回填。
表现列真源：练完手写的回填记录。重渲染前必须先把它合进来（默认读 plan.json 同目录的 表现回填.json），
否则空列表格一推上去就把用户写的记录覆盖掉——**禁止用空值覆盖已填回填**。
与 render_plan.py 同一套契约：先校验、错误则拒绝渲染；未就绪时须加 --draft。

用法：
  python3 scripts/render_weekly_log.py plan.json --week 1 --output 第1周训练计划.md
  python3 scripts/render_weekly_log.py plan.json --weeks 1-4 --output-dir 周计划/
"""
import argparse
import datetime as dt
import os
import re
import sys
from common import read_json, library
from validate_plan import validate
from endurance_stats import calculate as calculate_endurance
from aerobic_stats import calculate as calculate_aerobic
from render_plan import session_volume, week_endurance_body

WEEKDAY = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
KIND_LABEL = {'strength': '力量', 'swim': '游泳', 'run': '跑步', 'relax': '放松', 'mobility': '放松'}
MEANINGFUL = re.compile(r'RPE|TR |kg|秒|自重|负重|保持|呼吸|速度|幅度上限')
NOISE = re.compile(r'参考重量待补|^RPE\d')
# 热身五段各压成一行（动作列用 ｜ 串起来），五段之外不合并。
MERGE_SECTIONS = ('拉伸循环', '纠正', '激活', '动作准备', '动作技能')
# 配对组／超级组：序号共用数字加字母（1-A、1-B、1-C）。
GROUP_SECTIONS = ('前置组合', '力量配对', '后续三联')


def md_table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    for r in rows:
        out.append('| ' + ' | '.join('' if c is None else str(c) for c in r) + ' |')
    return '\n'.join(out)


def name_of(item, assets):
    """display_name 是可选字段，缺省回退到动作库条目名，再退到 unit_id。"""
    return (item.get('display_name')
            or (assets.get(item.get('unit_id'), {}) or {}).get('name')
            or item.get('unit_id')
            or '未命名项')


def dose_text(item, session_tempo=None, plain=False):
    """计划列＝剂量＋载重档＋RPE（＋偏离全课节拍时的短后缀）。
    只认短字段：page_dose_text / load.page_load / load.target_rpe / dose.tempo。
    长描述（load.description、notes、cue）只当文档，不进页面。"""
    dose = item.get('dose') or {}
    sets = dose.get('sets')
    reps = dose.get('reps')
    if item.get('page_dose_text'):
        body = item['page_dose_text']
    elif dose.get('duration_minutes') is not None:
        mins = dose['duration_minutes']
        body = '%d秒' % round(mins * 60) if mins * 60 < 60 else '%g分钟' % mins
        if sets and sets > 1:
            body = '%d×%s' % (sets, body)
    elif dose.get('distance_m'):
        body = '%d×%gm%s' % (sets or 1, dose['distance_m'], '/侧' if dose.get('per_side') else '')
        if reps and reps > 1:
            body = '%d×%d×%gm%s' % (sets or 1, reps, dose['distance_m'],
                                    '/侧' if dose.get('per_side') else '')
    elif reps:
        body = '%d×%d%s' % (sets or 1, reps, '/侧' if dose.get('per_side') else '')
    elif sets:
        body = '%d组' % sets
    else:
        body = '—'
    if plain:
        return body
    load = dose.get('load') or {}
    text = load.get('page_load')
    if text and text not in body:
        body += ' · ' + text
    rpe = load.get('target_rpe')
    if isinstance(rpe, (int, float)):
        body += ' · RPE%g' % rpe
    # 计划列只有四样：组数、次数、RPE、重量。节拍/停顿属执行提示，不进计划列。
    return body


def rest_label(module_title, rest_seconds):
    """恢复口径：只在课首说明里用一次，不进逐行。"""
    if not rest_seconds or rest_seconds < 60:
        return ''
    return '%g分' % (rest_seconds / 60)


def session_rest_minutes(session):
    """配对/三联的轮后恢复：取这些环节里出现最多的那一档（≥1分）。"""
    vals = []
    for module in session['modules']:
        if not (module.get('group_label') or module['title'].startswith(GROUP_SECTIONS)):
            continue
        for it in module['items']:
            r = (it.get('dose') or {}).get('rest_seconds')
            if r and r >= 60:
                vals.append(round(r / 60.0, 1))
    if not vals:
        return None
    return max(set(vals), key=vals.count)


def session_tempo_seconds(session):
    """全课默认节拍：力量项里出现最多的离心秒数。"""
    vals = []
    for module in session['modules']:
        for it in module['items']:
            dose = it.get('dose') or {}
            if not (dose.get('sets') or dose.get('reps')):
                continue
            ecc = (dose.get('tempo') or {}).get('eccentric_seconds')
            if ecc:
                vals.append(ecc)
    if not vals:
        return None
    return max(set(vals), key=vals.count)


def rest_text(item, grouped=False):
    """组间休息的页面写法：配对组说「同动作恢复」，普通段说「组间」。"""
    rs = (item.get('dose') or {}).get('rest_seconds') or 0
    if not rs:
        return ''
    label = '同动作恢复' if grouped else '组间'
    if rs % 60 == 0:
        return '%s%d分' % (label, rs // 60)
    return '%s%g分' % (label, round(rs / 60.0, 1))


def cue_text(item, module_title='', grouped=False, rest_override=None):
    """要点＝该行独有的硬条件（page_cue，缺省取 notes 首句）＋组间休息。
    技术提示、转项、器材替代、姿势描述一律不进页面。"""
    parts = []
    cue = (item.get('page_cue') or '').strip()
    if cue:
        parts.append(cue)
    else:
        notes = (item.get('dose') or {}).get('notes') or ''
        first = notes.split('；')[0].strip() if notes else ''
        if first:
            parts.append(first)
    rest = rest_text(item, grouped) if rest_override is None else rest_override
    if rest:
        parts.append(rest)
    return '；'.join(parts)


def section_action_text(module, assets):
    """热身段合并行的动作列：各子项名用 ｜ 串联（参数进「计划」列，不塞进名字）。"""
    return '｜'.join(name_of(it, assets) for it in module['items'])


def section_dose_text(module, assets):
    """热身段合并行的计划列：有段总时长就写时长，否则各子项参数按位对齐｜串联。"""
    if module.get('duration_minutes'):
        return '%d分钟' % module['duration_minutes']
    return '｜'.join(dose_text(it, None, plain=True) for it in module['items'])


def section_feedback(module, assets, feedback, session):
    """合并行的表现＝把段内各动作的回填合成一格：相同的只说一次，不同的按动作名列出。"""
    pairs = [(name_of(it, assets), (feedback or {}).get((session['id'], name_of(it, assets)), ''))
             for it in module['items']]
    vals = [v.strip() for _, v in pairs if v.strip()]
    if not vals:
        return ''
    uniq = list(dict.fromkeys(vals))
    keep = [v for v in uniq if not any(v != w and v in w for w in uniq)]
    if len(keep) == 1:
        return keep[0]
    base = max(keep, key=lambda v: sum(1 for x in vals if x == v))
    return base + ''.join('；%s：%s' % (n, v) for n, v in pairs if v.strip() and v != base)


def session_rows(session, assets, feedback=None):
    """当天连续编号；配对组/超级组共用编号＋A/B/C。热身五段各占一行。"""
    rows, n = [], 0
    tempo = session_tempo_seconds(session)
    for module in session['modules']:
        title = module['title']
        if title in MERGE_SECTIONS:
            n += 1
            rows.append([str(n), section_action_text(module, assets),
                         section_dose_text(module, assets), title,
                         section_feedback(module, assets, feedback, session)])
            continue
        items = module['items']
        # 只有三个组合段共用编号（11-A/11-B…）；增强式、药球等仍各占一个序号。
        grouped = (bool(module.get('group_label')) or title.startswith(GROUP_SECTIONS)) and len(items) > 1
        group_rest = None
        if grouped:
            rest_vals = [(it.get('dose') or {}).get('rest_seconds') or 0 for it in items]
            mx = max(rest_vals)
            if mx:
                # 组内各 item 恢复一致时才共用一行；不一致则逐行写自己的恢复
                if min(rest_vals) == mx:
                    group_rest = rest_text({'dose': {'rest_seconds': mx}}, True)
                else:
                    group_rest = None  # 不一致：逐行写自己的恢复
        for j, item in enumerate(items):
            cue = cue_text(item, title, grouped, group_rest)
            name = name_of(item, assets)
            if grouped:
                label = '%d-%s' % (n + 1, chr(65 + j))
            else:
                n += 1
                label = str(n)
            rows.append([label, name, dose_text(item, tempo),
                         '%s ｜ %s' % (title, cue) if cue else title,
                         (feedback or {}).get((session['id'], name), '')])
        if grouped:
            n += 1
    return rows


def day_section(session, assets, endurance_row=None, feedback=None):
    date = dt.date.fromisoformat(session['date'])
    volume = session_volume(endurance_row, session['kind']) if endurance_row else ''
    head = '## %s %d/%02d — %s（约%d分钟%s）' % (
        WEEKDAY[date.weekday()], date.month, date.day,
        session['title'], session['duration_minutes'],
        ' · ' + volume if volume else '')
    rows = session_rows(session, assets, feedback)
    parts = [head]
    if session.get('mini_goal'):
        parts.append('**本次小目标**：' + session['mini_goal'])
    note = []
    if session.get('kind') == 'strength':
        tempo = session_tempo_seconds(session)
        if tempo:
            note.append('离心%d秒、向心自然起' % tempo)
        rest = session_rest_minutes(session)
        note.append('按上表序号执行，序号即顺序；配对轮内换项≤1分不另计长休，各组恢复逐行列出，一轮后的轮后恢复取该轮最长档' +
                    ('（%g分）' % rest if rest else ''))
    if note:
        parts.append('**节奏与恢复**：' + '；'.join(note) + '。')
    parts.append(md_table(['序号', '动作', '计划', '要点', '表现'], rows))
    return '\n\n'.join(parts)


def number(value):
    text = '%.1f' % value
    return text.rstrip('0').rstrip('.') if '.' in text else text


def week_volume_lines(week, endurance, aerobic):
    """周总量一行、计划有氧当量一行——周文档顶部固定两行，下游按行分段，缺一行即算残缺文档。"""
    row = next((r for r in endurance.get('weeks', []) if r['week'] == week), None)
    volume = week_endurance_body(row).strip().replace('计划周总量：', '', 1).strip() if row else ''
    lines = ['本周总量：' + volume if volume else '本周总量：本周无跑泳剂量。']
    aero = next((r for r in aerobic.get('weeks', []) if r['week'] == week), None)
    if aero and aero.get('target_minutes'):
        lines.append('计划有氧当量：%s 分钟（周下限 %s 分钟）。' % (
            number(aero['equivalent_minutes']), number(aero['target_minutes'])))
    elif aero and aero.get('equivalent_minutes'):
        lines.append('计划有氧当量：%s 分钟。' % number(aero['equivalent_minutes']))
    return lines


def load_feedback(plan_path, explicit=None):
    """读「表现」回填。默认 plan.json 同目录 表现回填.json。

    entries: [{"记录动作名": 用户当时写的名字, "当前动作名": 课表现在用的名字, "表现": 原文}]
    只按「当前动作名」匹配；动作改过名时在文件里显式写别名，不做模糊匹配。
    """
    path = explicit or os.path.join(os.path.dirname(os.path.abspath(plan_path)), '表现回填.json')
    if not os.path.exists(path):
        return {}, path
    data = read_json(path)
    out = {}
    for e in data.get('entries') or []:
        name = e.get('当前动作名') or e.get('记录动作名')
        if not name or not (e.get('表现') or '').strip():
            continue
        # 必须带课次：同名准备动作每天都有，只按动作名匹配会把一天的记录串到整周
        if not e.get('课'):
            print('表现回填缺「课」被忽略：%s' % name, file=sys.stderr)
            continue
        out[(e['课'], name)] = e['表现'].strip()
    return out, path


def week_doc(plan, week, assets, endurance=None, aerobic=None, feedback=None):
    meta = next((w for w in plan['weeks'] if w['number'] == week), None)
    if meta is None:
        return None
    sessions = sorted([s for s in plan['sessions'] if s['week_number'] == week],
                      key=lambda s: s['date'])
    balls = [b for b in plan.get('ball_days', []) if (dt.date.fromisoformat(b['date']) - dt.date.fromisoformat(plan['start_date'])).days // 7 + 1 == week]
    if not sessions and not balls:
        return None
    block = next((b for b in plan.get('blocks', []) if b['id'] == meta.get('block_id')), {})
    focus = meta.get('focus') or block.get('focus') or ''
    event_dates = sorted([s['date'] for s in sessions] + [b['date'] for b in balls])
    d0 = dt.date.fromisoformat(event_dates[0])
    d1 = dt.date.fromisoformat(event_dates[-1])
    total = sum(s['duration_minutes'] for s in sessions)
    single_day = plan.get('scope', {}).get('window') == 'day'
    lines = ['# W%d 训练计划（%s ~ %s）· %s' % (week, d0.isoformat(), d1.strftime('%m-%d'), focus),
             '',
             '本周共 %d 次训练、合计约 %d 分钟；最后一列留给练完回填（重量组次 / 余力 / 当晚反应 / 次晨反应，踝膝分开）。' % (
                 len(sessions), total),
             '']
    if single_day:
        lines[0] = '# ' + plan['start_date'] + ' 单日训练计划 · ' + focus
        lines[2] = lines[2].replace('本周共', '当日共')
    endurance = endurance if endurance is not None else calculate_endurance(plan, assets)
    if aerobic is None:
        aerobic = calculate_aerobic(plan, assets)[0]
    lines.extend(week_volume_lines(week, endurance, aerobic))
    lines.extend(['', '---', ''])
    for s in sessions:
        lines.append(day_section(s, assets, endurance['sessions'].get(s['id']), feedback))
        lines.append('')
        lines.append('---')
        lines.append('')
    if balls:
        lines.append('## 固定球类安排（不是训练处方）\n')
        lines.append(md_table(['日期', '运动', '开始', '时长'], [[b['date'], b['sport'], b.get('start_time', '未提供'), str(b['duration_minutes'])+'分钟' if b.get('duration_minutes') is not None else '未核定'] for b in balls]))
    lines.append('## 当日要点\n' if single_day else '## 本周要点\n')
    counts = {}
    for s in sessions:
        counts[s['kind']] = counts.get(s['kind'], 0) + 1
    lines.append('- 训练安排：' + '、'.join(
        '%s %d 次' % (KIND_LABEL.get(k, k), v) for k, v in counts.items()))
    for line in meta.get('notes') or []:
        lines.append('- ' + line)
    lines.append('')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan')
    ap.add_argument('--week', type=int)
    ap.add_argument('--weeks', default=None, help='如 1-4')
    ap.add_argument('--output')
    ap.add_argument('--output-dir')
    ap.add_argument('--draft', action='store_true')
    ap.add_argument('--feedback', default=None, help='表现回填.json 路径（默认取 plan 同目录）')
    a = ap.parse_args()
    try:
        plan = read_json(a.plan)
        check = validate(plan)
        if check['errors']:
            raise ValueError('; '.join(check['errors']))
        scheduled = set(check.get('ready_weeks') or [])
        blocked = dict(check.get('blocked_week_reasons') or {})
        gaps = list(check.get('global_gaps') or [])
        assets = library()
        feedback, fb_path = load_feedback(a.plan, a.feedback)
        if a.week:
            weeks = [a.week]
        elif a.weeks:
            lo, _, hi = a.weeks.partition('-')
            weeks = list(range(int(lo), int(hi or lo) + 1))
        else:
            weeks = sorted(w['number'] for w in plan['weeks'])
        endurance = calculate_endurance(plan, assets)
        aerobic = calculate_aerobic(plan, assets)[0]
        written = []
        for w in weeks:
            if not a.draft:
                if gaps:
                    raise ValueError('计划层面的设计前提还没定，不能出正式周文档（W%d）：%s。先补齐，或加--draft 生成草案。'
                                     % (w, '；'.join(gaps[:3])))
                if w in blocked:
                    raise ValueError('W%d 的设计前提还没定，不能出正式周文档：%s。先补齐，或加--draft 生成草案。'
                                     % (w, '；'.join(blocked[w][:3])))
            if w not in scheduled and not a.draft:
                raise ValueError('W%d 还没排到具体日期，只有模块骨架；如需查看待完善内容，请加--draft。' % w)
            doc = week_doc(plan, w, assets, endurance, aerobic, feedback)
            if doc is None:
                continue
            if a.draft:
                doc = '> **草案**：本文件含未定项（未排期或设计前提未确认），不是正式课表，不要照此执行。\n\n' + doc
            if a.output:
                path = a.output
            else:
                d = a.output_dir or '.'
                os.makedirs(d, exist_ok=True)
                filename = (plan['start_date'] + '单日训练计划.md') if plan.get('scope', {}).get('window') == 'day' else '第%d周训练计划.md' % w
                path = os.path.join(d, filename)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(doc)
            written.append(path)
        if not written:
            raise ValueError('没有匹配的周；请检查 --week/--weeks。')
        for path in written:
            print(path)
        names = set()
        for s in plan['sessions']:
            for m in s['modules']:
                for it in m['items']:
                    names.add((s['id'], name_of(it, assets)))
        filled = sorted(k for k in feedback if k in names)
        missing = sorted(k for k in feedback if k not in names)
        print('表现回填：%s（匹配 %d 行）' % (fb_path, len(filled)))
        if missing:
            print('未匹配到课表行的回填：', '、'.join(str(x) for x in missing), file=sys.stderr)
        return 0
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
