# -*- coding: utf-8 -*-
"""单次课摘要与耗时：由剂量生成文字，不手写，避免两处声明冲突。"""
import re

from work_timing import whole_set_seconds
from common import library

MAIN_TITLES = ('主跑', '持续游主组')


def _g(value):
    return '%g' % value


def _pool(session, pool_default):
    return session.get('pool_length_m') or pool_default


def _swim_items(session):
    assets = library()
    return [x for m in session['modules'] for x in m['items']
            if assets.get(x['unit_id'], {}).get('category') == 'swim'
            and assets.get(x['unit_id'], {}).get('swim_task_mode') != 'stationary']


def swim_distance(session):
    return sum((x['dose'].get('sets') or 0) * (x['dose'].get('distance_m') or 0)
               for x in _swim_items(session))


def main_module(session, titles=MAIN_TITLES):
    for m in session['modules']:
        if m.get('title') in titles:
            return m
    return None


def run_mini_goal(session):
    """跑课摘要只描述主跑段的真实剂量。"""
    m = main_module(session, ('主跑',))
    if not m:
        return session.get('mini_goal') or ''
    parts = []
    for x in m['items']:
        d = x['dose']
        sets, reps = d.get('sets') or 1, d.get('reps')
        dist, minutes = d.get('distance_m'), d.get('duration_minutes')
        if reps and dist:
            seg = _g(sets) + '×' + _g(dist) + '米'
        elif reps and minutes:
            seg = _g(sets) + '×' + _g(minutes) + '分钟'
        elif dist:
            seg = _g(sets * dist) + '米'
        elif minutes:
            seg = '轻松连续跑' + _g(sets * minutes) + '分钟'
        else:
            continue
        rest = d.get('rest_seconds') or 0
        if rest and (reps or sets > 1):
            seg += '（纯休' + _g(rest) + '秒）'
        parts.append(seg)
    return '；'.join(parts) or (session.get('mini_goal') or '')


def swim_mini_goal(session, pool_default=None):
    """泳课摘要：池长、净泳量、主组组距与纯休，口径与分项一致。"""
    pool = _pool(session, pool_default)
    total = swim_distance(session)
    main = main_module(session, ('持续游主组',))
    bits = []
    if pool:
        bits.append(_g(pool) + '米池')
    assets = library()
    strokes = {assets.get(x['unit_id'], {}).get('stroke') or (assets.get(x['unit_id'], {}).get('default_dose') or {}).get('stroke', 'freestyle')
               for m in session['modules'] for x in m['items'] if assets.get(x['unit_id'], {}).get('category') == 'swim'}
    label = '蛙泳' if strokes == {'breaststroke'} else ('自由泳' if strokes <= {'freestyle', 'freestyle_flutter_kick'} else '游泳')
    bits.append(label + _g(total) + '米')
    if main:
        for x in main['items']:
            d = x['dose']
            sets, dist = d.get('sets') or 1, d.get('distance_m')
            if not dist:
                continue
            seg = '主组' + _g(sets) + '×' + _g(dist) + '米'
            rest = d.get('rest_seconds') or 0
            if rest:
                seg += '，纯休' + _g(rest) + '秒'
            bits.append(seg)
    if len(bits) <= 1:
        return '，'.join(bits)
    return '，'.join(bits[:2]) + '；' + '，'.join(bits[2:]) if len(bits) > 2 else '，'.join(bits)


def mini_goal(session, kind, pool_default=None):
    if kind == 'run':
        return run_mini_goal(session)
    if kind == 'swim':
        return swim_mini_goal(session, pool_default)
    return session.get('mini_goal') or ''


def session_work_minutes(session):
    """按组数×(单组工作＋组间休息)累计实算耗时，用于核对声明时长。"""
    total = 0.0
    for m in session['modules']:
        for x in m['items']:
            d = x['dose']
            sets = d.get('sets') or 1
            work = whole_set_seconds(x) or 0
            rest = d.get('rest_seconds') or 0
            total += (sets * work + max(sets - 1, 0) * rest) / 60.0
    return round(total, 1)


def timing_audit(plan):
    """逐课声明时长与实算耗时的差；不判定是否超个人时间预算（那属于档案条件）。"""
    rows = []
    for s in plan['sessions']:
        computed = session_work_minutes(s)
        declared = s.get('duration_minutes')
        if computed is None or declared is None:
            continue
        rows.append({'id': s['id'], 'kind': s['kind'], 'declared': declared,
                     'computed': computed, 'gap': round(computed - declared, 1)})
    return rows


def summary_drift(plan, pool_default=None):
    """mini_goal 与剂量不一致的课次，逐条列出生成值与现值。

    摘要里写了数字就是可核对的声明，与剂量不符按错误处理；没有数字的摘要只是没写全，
    记为待补，不拦出表。
    """
    rows = []
    for s in plan['sessions']:
        if s['kind'] not in ('run', 'swim'):
            continue
        expected = mini_goal(s, s['kind'], pool_default)
        now = s.get('mini_goal')
        if expected and now != expected:
            rows.append({'id': s['id'], 'kind': s['kind'], 'now': now, 'expected': expected,
                         'quantified': bool(re.search(r'\d', now or ''))})
    return rows
