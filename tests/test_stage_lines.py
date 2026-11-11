"""联合递进与球类条件分支的验收测试。

两条边界写死在这里：
1. 同一阶段里跑动、泳量、力量量中超过一条在涨，必须报 review（不是 error）——
   允许两条同涨，但要写出本阶段主次，不许三套各自默默递进。
2. 球类规则是条件分支：课表没有球类课次时，球前／球后约束不该出现；出现了要报 review，
   而不是默认生效、也不是新建一套球类编排。
"""
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from validate_plan import validate  # noqa: E402
from design_checks import stage_load_lines, line_rise_points, _week_lines  # noqa: E402

EXAMPLE = os.path.join(ROOT, 'assets', 'examples', 'plan.json')


def example():
    return json.load(io.open(EXAMPLE, encoding='utf-8'))


def swim_main(plan, sid):
    s = next(x for x in plan['sessions'] if x['id'] == sid)
    return next(m for m in s['modules'] if m['title'] == '持续游主组')


class StageLinesTest(unittest.TestCase):
    def test_example_rises_only_at_block_edges(self):
        """示例把跑收成三档（62／75／88／100），阶段内三条线都不动，抬档只落在边界。"""
        p = example()
        rows = stage_load_lines(p)
        self.assertEqual(['B1', 'B2', 'B3', 'B4'], [r['block_id'] for r in rows])
        for row in rows:
            self.assertEqual([], row['rising'],
                             row['block_id'] + ' 阶段内不该有线上抬，实际：' + str(row['rising']))
        self.assertEqual([4, 7, 10], line_rise_points(p, 'run')[1],
                         '抬档点应落在三个阶段边界，且每档稳 3 周')
        items = validate(p)['review_items']
        self.assertEqual([], [r for r in items if '同时上抬' in r])
        self.assertEqual([], [r for r in items if '只隔' in r or '连续' in r and '阶段都在上抬' in r],
                         '三档写法不该触发逐周抬档或连续上抬提醒')

    def test_swim_frozen_keeps_volume_identical(self):
        p = example()
        volumes = {w: _week_lines(p, w)['swim']['volume'] for w in (1, 6, 12)}
        self.assertEqual(600.0, volumes[1])
        self.assertEqual(volumes[1], volumes[6])
        self.assertEqual(volumes[1], volumes[12])

    def test_two_lines_rising_triggers_review(self):
        """同一阶段让泳和力量一起抬，必须报 review（示例本身阶段内是平的）。"""
        p = example()
        mod = swim_main(p, 'W03-S')
        mod['items'][0]['dose']['sets'] = 5          # 600 → 700（+16.7%）
        mod['items'][0]['duration_minutes'] = 15.0
        mod['duration_minutes'] = 15.0
        sess = next(x for x in p['sessions'] if x['id'] == 'W03-S')
        sess['duration_minutes'] += 3.0
        lift = next(x for x in p['sessions'] if x['id'] == 'W03-F1')
        for m in lift['modules']:
            for item in m['items']:
                load = item['dose'].get('load') or {}
                if load.get('target_rpe') is not None:
                    load['target_rpe'] = load['target_rpe'] + 0.5   # 强度抬 0.5 也算上抬
        result = validate(p)
        self.assertEqual([], result['errors'], '联合递进是 review，不是 error')
        hits = [r for r in result['review_items'] if '同时上抬' in r]
        self.assertTrue(hits, 'B1 里泳与力量同时上抬，必须报出来')
        self.assertIn('B1', hits[0])
        self.assertIn('力量', hits[0])
        self.assertIn('泳', hits[0])

    def test_shortening_rest_counts_as_a_rise(self):
        """压缩休息本身也是加量：主组休息从 25 s 压到 20 s 要与加米同样对待。"""
        p = example()
        item = swim_main(p, 'W03-S')['items'][0]
        item['dose']['rest_seconds'] = 15
        self.assertIn('swim', stage_load_lines(p)[0]['rising'])


class RampsAndStreaksTest(unittest.TestCase):
    """抬档节拍：可以抬，但两档之间至少稳 3 周；同一条线不许连涨整轮。"""

    def _bump_week_runs(self, p, week, extra):
        for s in p['sessions']:
            if s['kind'] != 'run' or s['week_number'] != week:
                continue
            main = next(m for m in s['modules'] if m['title'] == '主跑')
            main['items'][0]['dose']['duration_minutes'] += extra
            main['items'][0]['duration_minutes'] += extra
            main['duration_minutes'] += extra
            s['duration_minutes'] += extra

    def test_tight_ramp_triggers_review(self):
        """W2 就抬一次档，与 W1 只隔 1 周，必须报 review。"""
        p = example()
        self._bump_week_runs(p, 2, 12)   # 62 → 74，W2 成为抬档点
        self.assertIn(2, line_rise_points(p, 'run')[1])
        hits = [r for r in validate(p)['review_items'] if '只隔' in r]
        self.assertTrue(hits, '抬档只隔 1 周必须报出来')
        self.assertIn('W2', hits[0])

    def test_streak_triggers_review(self):
        """三个阶段的最后一周都把泳量抬上去，就是同一条线连涨三轮，必须报 review。"""
        p = example()
        for sid in ('W03-S', 'W06-S', 'W09-S'):
            mod = swim_main(p, sid)
            mod['items'][0]['dose']['sets'] = 6      # 600 → 800
            mod['items'][0]['duration_minutes'] = 18.0
            mod['duration_minutes'] = 18.0
            sess = next(x for x in p['sessions'] if x['id'] == sid)
            sess['duration_minutes'] += 6.0
        hits = [r for r in validate(p)['review_items'] if '阶段都在上抬' in r]
        self.assertTrue(hits, '连续三个阶段都在抬，必须报出来')
        self.assertIn('泳', hits[0])


class BallRuleTest(unittest.TestCase):
    def test_example_without_ball_has_no_ball_rules(self):
        p = example()
        self.assertEqual([], [r for r in validate(p)['review_items'] if '球类课次' in r])
        self.assertEqual({'run', 'strength', 'swim'}, {s['kind'] for s in p['sessions']})

    def test_ball_rule_without_ball_session_triggers_review(self):
        p = example()
        target = next(s for s in p['sessions'] if s['id'] == 'W01-F1')
        target['purpose'] = target['purpose'] + '；有球赛时按球前 48 小时处理'
        result = validate(p)
        self.assertEqual([], result['errors'], '球类空转是 review，不是 error')
        hits = [r for r in result['review_items'] if '球类课次' in r]
        self.assertTrue(hits, '提到球前却没有任何球类课次，必须报出来')


if __name__ == '__main__':
    unittest.main()
