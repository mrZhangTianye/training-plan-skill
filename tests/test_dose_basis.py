"""跑量口径与泳量涨幅的验收测试（跑步教练／游泳教练提的两条缺口）。

写死三条：
1. 跑次＝本周全部跑课，不是「给了距离的课数」——按后者算，三跑周只两课有距离就掉到 2 跑档（55%），
   一课有距离还会掉进单跑周分支、比例完全不核算。
2. 距离不全不拿部分距离当分母，全周统一按时长口径核算，超限照样报 error。
3. 同一阶段相邻两次同课型泳总量涨幅 >10% 报 review（10% 是包内上限带，不是通用生理阈值）；
   没给泳距的标未核定，不给假通过。
"""
import copy
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from validate_plan import validate  # noqa: E402

EXAMPLE = os.path.join(ROOT, 'assets', 'examples', 'plan.json')


def example():
    return json.load(io.open(EXAMPLE, encoding='utf-8'))


def main_item(plan, sid):
    s = next(x for x in plan['sessions'] if x['id'] == sid)
    return s, next(m for m in s['modules'] if m['title'] == '主跑')


NON_RUN = ('warmup', 'cooldown', 'brisk_walk', 'run_warmup', 'run_cooldown',
           'mobility', 'foam_roll', 'static_stretch')


def week_run_minutes(plan, week=1):
    """本周跑动分钟（不含快走与课首尾过渡）与单次最长值。"""
    total = longest = 0
    for s in plan['sessions']:
        if s['week_number'] != week or s['kind'] != 'run':
            continue
        m = sum((i['dose'].get('duration_minutes') or 0) * (i['dose'].get('sets') or 1)
                for mod in s['modules'] for i in mod['items'] if i['unit_id'] not in NON_RUN)
        total += m
        longest = max(longest, m)
    return total, longest


def set_run(plan, sid, minutes=None, meters=None):
    s, main = main_item(plan, sid)
    it = main['items'][0]
    if minutes is not None:
        it['dose']['duration_minutes'] = minutes
        main['duration_minutes'] = minutes + 2
        s['duration_minutes'] = sum(m['duration_minutes'] for m in s['modules'])
    if meters is not None:
        it['dose']['distance_m'] = meters


class RunVolumeBasisTest(unittest.TestCase):
    """距离不全时，跑次和分母都不许被『补上的那一个字段』带偏。"""

    def test_partial_distance_keeps_real_run_count_and_catches_over_cap(self):
        p = example()
        set_run(p, 'W01-R1', minutes=60, meters=9000)   # 只有这一课补了距离
        p['profile']['available_minutes']['0'] = 300    # 排除预算先命中，只看跑量逻辑
        result = validate(p)
        hits = [e for e in result['errors'] if '单次最长跑' in e and '上限' in e]
        self.assertTrue(hits, '混合口径周必须按全周时长超限报错，实际：' + str(result['errors']))
        self.assertIn('本周跑 3 次', hits[0], '跑次必须按真实跑课数算，不是给了距离的课数')
        # 分母是跑动分钟（不含快走与冷身），按计划现算，示例改剂量时不用改测试
        total, longest = week_run_minutes(p)
        self.assertIn(str(total) + ' 分钟', hits[0])
        self.assertIn(str(round(100.0 * longest / total)) + '%', hits[0])
        self.assertTrue([r for r in result['review_items'] if '跑量口径不统一' in r])

    def test_walk_and_transition_are_not_run_volume(self):
        """快走与课首尾过渡不计入跑量：把它们加长，报出来的分母与占比不该动。"""
        p = example()
        set_run(p, 'W01-R1', minutes=60)
        p['profile']['available_minutes']['0'] = 300
        before = [e for e in validate(p)['errors'] if '单次最长跑' in e][0]
        total_before, _ = week_run_minutes(p)
        self.assertIn(str(total_before) + ' 分钟', before)

        s = next(x for x in p['sessions'] if x['id'] == 'W01-R1')
        for m in s['modules']:
            for it in m['items']:
                if it['unit_id'] in ('brisk_walk', 'cooldown'):
                    it['duration_minutes'] = 20
                    it['dose']['duration_minutes'] = 20
                    if 'aerobic_minutes' in it:
                        it['aerobic_minutes'] = 20
        s['duration_minutes'] = sum(m['duration_minutes'] for m in s['modules'])
        after = [e for e in validate(p)['errors'] if '单次最长跑' in e][0]
        self.assertIn(str(total_before) + ' 分钟', after, '走段与冷身进了分母，分母就会变大')
        self.assertEqual(before.split('超过')[1], after.split('超过')[1])

    def test_two_of_three_with_distance_does_not_relax_cap(self):
        """旧逻辑：rc=2 → 上限 55%，45% 不报。现在必须报。"""
        p = example()
        set_run(p, 'W01-R1', meters=4500, minutes=28)
        set_run(p, 'W01-R2', meters=4000, minutes=28)
        p['profile']['available_minutes']['0'] = 300
        result = validate(p)
        hits = [e for e in result['errors'] if '单次最长跑' in e and '40% 包内上限' in e]
        self.assertTrue(hits, '三跑周不许因为只有两课给距离就松到 55%% 档：' + str(result['errors']))

class SwimProgressionTest(unittest.TestCase):
    """泳量涨幅是泳侧唯一硬线，校验器必须管。"""

    def swim_total(self, plan, sid):
        s = next(x for x in plan['sessions'] if x['id'] == sid)
        return sum((i['dose'].get('distance_m') or 0) * (i['dose'].get('sets') or 1)
                   for m in s['modules'] for i in m['items'])

    def test_example_swim_is_flat_maintenance(self):
        """游泳在本示例是维持档：12 周每次都是 800 m，泳侧不该有任何涨幅提醒。"""
        p = example()
        self.assertEqual(self.swim_total(p, 'W01-S'), self.swim_total(p, 'W12-S'),
                         '维持档的泳课量必须全周期不变')
        self.assertEqual(600, self.swim_total(p, 'W01-S'),
                         '600 = 技术4×50（200）＋主组4×100（400）；陆地热身与泳后拉伸不计水中量')
        result = validate(p)
        self.assertEqual([], [r for r in result['review_items'] if '泳总量' in r])

    def test_swim_ramp_is_flagged(self):
        """把某一周的泳量抬上去，泳涨幅校验仍必须报出来。"""
        p = example()
        s = next(x for x in p['sessions'] if x['id'] == 'W02-S')
        main = next(m for m in s['modules'] if m['title'] == '持续游主组')
        self.assertEqual(4, main['items'][0]['dose']['sets'])
        main['items'][0]['dose']['sets'] = 8
        hits = [r for r in validate(p)['review_items'] if '泳总量' in r]
        self.assertTrue(hits, '600 → 1000（+67%）必须报出来')

    def test_within_band_is_silent(self):
        p = example()
        s = next(x for x in p['sessions'] if x['id'] == 'W02-S')
        tech = next(m for m in s['modules'] if m['title'] == '技术巩固')
        tech['items'][0]['dose']['sets'] = 5  # 600 → 650（+8.3%）在 10% 带内
        result = validate(p)
        self.assertEqual([], [r for r in result['review_items'] if 'W02-S 泳总量' in r])

if __name__ == '__main__':
    unittest.main()
