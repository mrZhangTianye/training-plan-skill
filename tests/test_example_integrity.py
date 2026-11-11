"""包内自带示例必须校验干净——示例坏了，其它测试照绿属于假通过。"""
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from validate_plan import validate  # noqa: E402


class ExampleIntegrityTest(unittest.TestCase):
    def test_bundled_example_validates_clean(self):
        path = os.path.join(ROOT, 'assets', 'examples', 'plan.json')
        plan = json.load(io.open(path, encoding='utf-8'))
        result = validate(plan)
        self.assertEqual(
            [], result['errors'],
            '自带示例必须校验干净，否则文档给出的形态与硬门已脱节：' + str(result['errors']))

    def test_example_blocks_are_four_three_week_stages(self):
        path = os.path.join(ROOT, 'assets', 'examples', 'plan.json')
        plan = json.load(io.open(path, encoding='utf-8'))
        spans = [(b['first_week'], b['last_week']) for b in plan['blocks']]
        self.assertEqual([(1, 3), (4, 6), (7, 9), (10, 12)], spans,
                         '示例应按 12 周 = 四个 3 周阶段')

    def test_eight_week_plan_is_accepted(self):
        """8 周＝两个完整阶段＋末阶段压到 2 周，不能因为不在 12/9/6/4/3 里就被拒。"""
        path = os.path.join(ROOT, 'assets', 'examples', 'plan.json')
        plan = json.load(io.open(path, encoding='utf-8'))
        plan = json.loads(json.dumps(plan))
        plan['duration_weeks'] = 8
        plan['blocks'] = [
            {'id': 'B1', 'first_week': 1, 'last_week': 3, 'focus': '装模式', 'goal_ids': ['G1'], 'progression_condition': '见修订'},
            {'id': 'B2', 'first_week': 4, 'last_week': 6, 'focus': '上强度', 'goal_ids': ['G1'], 'progression_condition': '见修订'},
            {'id': 'B3', 'first_week': 7, 'last_week': 8, 'focus': '接爆发（末段压缩）', 'goal_ids': ['G1'], 'progression_condition': '见修订'},
        ]
        plan['weeks'] = [w for w in plan['weeks'] if w['number'] <= 8]
        for w in plan['weeks']:
            w['block_id'] = 'B1' if w['number'] <= 3 else ('B2' if w['number'] <= 6 else 'B3')
        wk = {w['number']: w['block_id'] for w in plan['weeks']}
        plan['sessions'] = [s for s in plan['sessions'] if s['week_number'] <= 8]
        for s in plan['sessions']:
            s['block_id'] = wk[s['week_number']]
        result = validate(plan)
        self.assertFalse([e for e in result['errors'] if '不在支持' in e], result['errors'])


if __name__ == '__main__':
    unittest.main()
