# -*- coding: utf-8 -*-
"""单次摘要与阶段衔接的验收测试。

两条边界：
1. 摘要（mini_goal）里写了数字就是可核对的声明，必须与单次剂量一致；改剂量不改摘要要被抓出来。
2. 阶段内持平不等于整轮受控：上一阶段末周→下一阶段首周的增量为单独一条，不能被首末周对比吞掉。
"""
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from validate_plan import validate  # noqa: E402
from design_checks import stage_load_lines  # noqa: E402
from session_summary import mini_goal, summary_drift, run_mini_goal  # noqa: E402
from design_checks import baseline_entry_check  # noqa: E402
import duration_model  # noqa: E402

EXAMPLE = os.path.join(ROOT, 'assets', 'examples', 'plan.json')


def example():
    return json.load(io.open(EXAMPLE, encoding='utf-8'))


def pool(plan):
    return (plan['profile'].get('pool') or {}).get('length_m')


class SummaryTest(unittest.TestCase):
    def test_example_summaries_match_dose(self):
        """示例里每一节跑课和泳课的摘要都由剂量生成，没有手写残留。"""
        p = example()
        self.assertEqual([], summary_drift(p, pool(p)))

    def test_stale_summary_is_reported(self):
        """剂量改了、摘要没改，必须报出来（review 而非 error：不改训练结构）。"""
        p = example()
        sess = next(x for x in p['sessions'] if x['id'] == 'W04-R1')
        sess['mini_goal'] = '轻松连续跑30分钟'
        result = validate(p)
        self.assertEqual([], result['errors'])
        self.assertTrue(any('W04-R1' in m and 'mini_goal 与单次剂量不一致' in m for m in result['review_items']),
                        result['review_items'])

    def test_run_summary_uses_main_section_only(self):
        """跑课摘要只描述主跑段：热身与冷身不进摘要。"""
        p = example()
        sess = next(x for x in p['sessions'] if x['id'] == 'W01-R1')
        self.assertEqual('轻松连续跑19分钟', run_mini_goal(sess))

    def test_swim_summary_carries_pool_total_and_rest(self):
        """泳课摘要必须带池长、净泳量、主组组距与纯休。"""
        p = example()
        sess = next(x for x in p['sessions'] if x['id'] == 'W01-S')
        self.assertEqual('50米池，自由泳600米；主组4×100米，纯休20秒', mini_goal(sess, 'swim', pool(p)))


class HandoffTest(unittest.TestCase):
    def test_example_rises_only_at_stage_boundaries(self):
        """示例的跑量只在不衔接处抬档：阶段内三线全平，抬档全部落在 handoff。"""
        p = example()
        rows = stage_load_lines(p)
        self.assertEqual([['run'], ['run'], ['run']], [r['handoff_rising'] for r in rows[1:]])
        for row in rows:
            self.assertEqual([], row['rising'])

    def test_handoff_reports_the_week_line_delta(self):
        """衔接处的增量要写清上一阶段末周与下一阶段首周的两个量。"""
        p = example()
        row = stage_load_lines(p)[1]
        self.assertEqual([62.0, 75.0], [round(row['handoff']['run']['volume'][0], 1),
                                        round(row['handoff']['run']['volume'][1], 1)])

    def test_unresolved_handoff_blocks_actual_output(self):
        """未处理的衔接增量在 actual 模式下不能算过：缺 resolution 就不给出表。"""
        p = example()
        p['design_context']['review_resolutions'] = [
            r for r in p['design_context']['review_resolutions']
            if not r['review_id'].startswith('stage_handoff')]
        p['intended_use'] = 'actual'
        result = validate(p)
        self.assertTrue(any('stage_handoff' in g for g in result['global_gaps']), result['global_gaps'])
        self.assertEqual([], result['ready_weeks'])


class DurationModelTest(unittest.TestCase):
    def test_strength_minutes_come_from_the_model(self):
        """力量课耗时不再手写：文件里的值与模型对同一节算出来的值一致。"""
        p = example()
        for s in p['sessions']:
            if s['kind'] != 'strength':
                continue
            self.assertAlmostEqual(s['duration_minutes'], duration_model.session_minutes(s), delta=0.011, msg=s['id'])

    def test_no_single_constant_minutes(self):
        """24 节力量课不再共用同一个手写常量。"""
        p = example()
        values = {round(s['duration_minutes'], 1) for s in p['sessions'] if s['kind'] == 'strength'}
        self.assertGreater(len(values), 1, values)

    def test_prep_item_takes_asset_work_seconds(self):
        """准备段按备注给出的整组工作秒算（3 次呼吸约 9 秒/次 → 0.45 分钟），不被 4 秒/次压低。"""
        p = example()
        sess = next(x for x in p['sessions'] if x['id'] == 'W01-F1')
        warmup = next(x for x in sess['modules'][0]['items'] if x['unit_id'] == 'warmup')
        self.assertAlmostEqual(warmup['duration_minutes'], 0.45, delta=0.001)


class BaselineEntryTest(unittest.TestCase):
    def test_example_passes_by_frequency_not_percentage(self):
        """加跑次、单次不上抬：不报，哪怕周量口径上的涨幅看起来很大。"""
        self.assertEqual([], baseline_entry_check(example()))

    def test_same_frequency_with_volume_jump_is_flagged(self):
        """跑次不变而周量抬超过 10%，要说明。"""
        p = example()
        next(g for g in p['objectives'] if g['id'] == 'G2')['baseline_basis']['run_sessions_per_week'] = 3
        rows = baseline_entry_check(p)
        self.assertEqual(['volume_same_frequency'], [r['kind'] for r in rows], rows)

    def test_longer_single_with_new_frequency_is_flagged(self):
        """加跑次的同时延长了单次，等于两条线一起抬。"""
        p = example()
        sess = next(x for x in p['sessions'] if x['id'] == 'W01-R1')
        for m in sess['modules']:
            for x in m['items']:
                if x['unit_id'] == 'easy_run' and x['dose'].get('target_rpe') is None:
                    x['dose']['duration_minutes'] = 26
                    break
        rows = baseline_entry_check(p)
        self.assertEqual(['frequency_plus_longer'], [r['kind'] for r in rows], rows)
        self.assertIn('26', rows[0]['message'])


if __name__ == '__main__':
    unittest.main()
