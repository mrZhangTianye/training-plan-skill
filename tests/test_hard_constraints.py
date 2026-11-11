# -*- coding: utf-8 -*-
"""四条硬约束回归：这些规则以前只写在散文里，脚本不查，等于没有。
本文件保证它们真的拦截，而不是又变成一句说明。"""
import sys
import copy
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import library
from design_checks import check
from test_workflows import fixture


class HardConstraintTest(unittest.TestCase):
    def setUp(self):
        self.plan = fixture()
        self.assets = library()

    def errors(self, plan):
        return check(plan, self.assets)[0]

    def test_weekly_high_intensity_cap(self):
        p = copy.deepcopy(self.plan)
        base = p['sessions'][0]
        p['sessions'] = []
        for i in range(5):
            s = copy.deepcopy(base)
            s['id'] = 'H%d' % i
            s['date'] = '2026-10-0%d' % (5 + i)
            s['recovery_cost'] = 'high'
            p['sessions'].append(s)
        errs = self.errors(p)
        self.assertTrue(any('超过每周 4 次上限' in e for e in errs), errs)

    def test_long_run_ratio_cap(self):
        p = copy.deepcopy(self.plan)
        runs = [s for s in p['sessions'] if s['kind'] == 'run']
        long_run = copy.deepcopy(runs[0])
        long_run['id'] = 'LONG'
        long_run['date'] = '2026-10-10'
        long_run['modules'][0]['items'][0]['dose']['distance_m'] = 8000
        runs[0]['modules'][0]['items'][0]['dose']['distance_m'] = 1000
        p['sessions'].append(long_run)
        errs = self.errors(p)
        self.assertTrue(any('单次最长跑' in e and '上限' in e for e in errs), errs)

    def test_heavy_strength_and_hard_swim_same_day(self):
        p = copy.deepcopy(self.plan)
        swim = copy.deepcopy(p['sessions'][0])
        swim['id'] = 'SWIM'
        swim['kind'] = 'swim'
        swim['recovery_cost'] = 'high'
        swim['date'] = p['sessions'][0]['date']
        swim['start_time'] = '17:00'
        p['sessions'][0]['recovery_cost'] = 'high'
        p['sessions'].append(swim)
        errs = self.errors(p)
        self.assertTrue(any('大重量力量课与高强度泳课同日' in e for e in errs), errs)


    def test_interval_volume_cap(self):
        """Daniels：单次 I 跑动 ≤ 周量 8%。"""
        p = copy.deepcopy(self.plan)
        run = [x for x in p['sessions'] if x['kind'] == 'run'][0]
        item = run['modules'][0]['items'][0]
        item['unit_id'] = 'aerobic_run_intervals'
        item['dose'] = {'sets': 10, 'distance_m': 800, 'duration_minutes': None,
                        'reps': None, 'per_side': False, 'load': None, 'rest_seconds': None, 'notes': ''}
        errs = self.errors(p)
        self.assertTrue(any('超过 8% 上限' in e for e in errs), errs)

    def test_repetition_volume_cap(self):
        """Daniels：单次 R 跑动 ≤ 周量 5%。"""
        p = copy.deepcopy(self.plan)
        run = [x for x in p['sessions'] if x['kind'] == 'run'][0]
        item = run['modules'][0]['items'][0]
        item['unit_id'] = 'repetition_run'
        item['dose'] = {'sets': 12, 'distance_m': 400, 'duration_minutes': None,
                        'reps': None, 'per_side': False, 'load': None, 'rest_seconds': None, 'notes': ''}
        errs = self.errors(p)
        self.assertTrue(any('超过 5% 上限' in e for e in errs), errs)


    def test_no_impact_limitation_blocks_jump(self):
        """登记 no_impact 后，计划里还排跑跳就必须报错——否则这条限制等于没写。"""
        p = copy.deepcopy(self.plan)
        p.setdefault('design_context', {})['limitations'] = [
            {'rule': 'no_impact', 'region': '膝', 'scope': '不跑不跳，等影像确认骨愈合'}]
        assets = library()
        jump = [k for k, v in assets.items() if v.get('impact') in
                ('jump', 'hop', 'bound', 'loaded_jump', 'loaded_receiving_foot_transition')]
        self.assertTrue(jump, '库里应有跑跳类动作')
        run = [x for x in p['sessions'] if x['kind'] == 'run'][0]
        run['modules'][0]['items'][0]['unit_id'] = jump[0]
        errs = self.errors(p)
        self.assertTrue(any('限制冲突' in e and 'no_impact' in e for e in errs), errs)

    def test_no_impact_flags_existing_run_work(self):
        """fixture 里本来就有跑步课，登记 no_impact 后必须被扫出来——证明检查真的读到了 unit_id。"""
        p = copy.deepcopy(self.plan)
        p.setdefault('design_context', {})['limitations'] = [
            {'rule': 'no_impact', 'region': '膝', 'scope': '不跑不跳'}]
        errs = [e for e in self.errors(p) if 'no_impact' in e]
        self.assertTrue(errs, '跑步课应触发 no_impact 冲突')

    def test_no_impact_clean_after_removing_run(self):
        """把跑步课换掉后，no_impact 不该误报。"""
        p = copy.deepcopy(self.plan)
        p.setdefault('design_context', {})['limitations'] = [
            {'rule': 'no_impact', 'region': '膝', 'scope': '不跑不跳'}]
        p['sessions'] = [x for x in p['sessions'] if x['kind'] != 'run']
        errs = [e for e in self.errors(p) if 'no_impact' in e]
        self.assertEqual(errs, [])

    def test_compliant_plan_stays_clean(self):
        errs = self.errors(copy.deepcopy(self.plan))
        self.assertEqual([e for e in errs if '超过' in e or '同日' in e], [])


    # ---- 跑量分档与限制额度（v1.8） ----

    def _run_session(self, sid, distance_m, date):
        base = [x for x in self.plan['sessions'] if x['kind'] == 'run'][0]
        s = copy.deepcopy(base)
        s['id'] = sid
        s['date'] = date
        s['modules'][0]['items'][0]['dose']['distance_m'] = distance_m
        return s

    def _with_runs(self, spec):
        """spec: [(id, distance_m, date)]，替换当天跑课并挂到第 1 周。"""
        p = copy.deepcopy(self.plan)
        p['sessions'] = [x for x in p['sessions'] if x['kind'] != 'run']
        ids = []
        for sid, dist, date in spec:
            p['sessions'].append(self._run_session(sid, dist, date))
            ids.append(sid)
        p['weeks'][0]['session_ids'] = [x for x in p['weeks'][0]['session_ids']
                                        if x != 'S3'] + ids
        return p

    def test_two_run_week_5050_split_not_rejected(self):
        """两跑周最长天然占一半，2 跑档上限 55%：50/50 必须放行。"""
        p = self._with_runs([('R1', 5000, '2026-10-07'), ('R2', 5000, '2026-10-09')])
        errs = self.errors(p)
        self.assertFalse([e for e in errs if '单次最长跑' in e], errs)

    def test_single_run_week_ratio_check_skipped(self):
        """只跑一次时整周量就在这一课里，比例不适用。"""
        p = self._with_runs([('R1', 8000, '2026-10-07')])
        errs = self.errors(p)
        self.assertFalse([e for e in errs if '单次最长跑' in e], errs)

    def test_limitation_until_week_expiry_triggers_review(self):
        """到了 until_week 必须复评，不自动解除。"""
        p = copy.deepcopy(self.plan)
        p.setdefault('design_context', {})['limitations'] = [
            {'region': '右膝', 'kind': '阶段性', 'rule': 'no_impact',
             'scope': '跑跳暂停', 'until_week': 1}]
        out = check(p, self.assets)
        review = out[1] if len(out) > 1 else []
        self.assertTrue(any('复评' in str(x) or 'until_week' in str(x) for x in review), review)

    def _four_high_week(self):
        p = copy.deepcopy(self.plan)
        base = p['sessions'][0]
        p['sessions'] = []
        for i in range(4):
            s = copy.deepcopy(base)
            s['id'] = 'H%d' % i
            s['date'] = '2026-10-0%d' % (5 + i)
            s['recovery_cost'] = 'high'
            p['sessions'].append(s)
        p['weeks'][0]['session_ids'] = [s['id'] for s in p['sessions']]
        return p

    def test_long_term_limitation_does_not_cut_intensity_cap(self):
        """长期结构性限制只改动作选择，不占恢复预算：4 次仍放行。"""
        p = self._four_high_week()
        p.setdefault('design_context', {})['limitations'] = [
            {'region': '右肩', 'kind': '长期', 'rule': 'no_overhead',
             'scope': '过头推举不做，其它可做'}]
        errs = self.errors(p)
        self.assertFalse([e for e in errs if '高强度课' in e], errs)

    def test_phase_limitation_still_cuts_cap(self):
        """阶段性限制占恢复预算：同一周 4 次必须被 3 次上限拦下。"""
        p = self._four_high_week()
        p.setdefault('design_context', {})['limitations'] = [
            {'region': '右膝', 'kind': '阶段性', 'rule': 'no_impact',
             'scope': '跑跳暂停', 'until_week': 3}]
        errs = self.errors(p)
        self.assertTrue([e for e in errs if '高强度课' in e and '3 次上限' in e], errs)

class SingleRunWeekTest(unittest.TestCase):
    """单跑周不能把原周量塞进一次：比例上限不适用，但要和本阶段已出现的单次最长值比。"""

    def setUp(self):
        self.plan = fixture()
        self.assets = library()

    def _plan(self, weeks):
        base = [s for s in self.plan['sessions'] if s['kind'] == 'run'][0]
        sessions = []
        for i, (wk, dist) in enumerate(weeks):
            s = copy.deepcopy(base)
            s['id'] = 'R%d' % i
            s['week_number'] = wk
            s['block_id'] = 'B1'
            s['date'] = '2026-10-%02d' % (i + 1)
            for m in s['modules']:
                for it in m['items']:
                    it['dose']['distance_m'] = None
                    it['dose']['sets'] = None
            s['modules'][0]['items'][0]['dose']['distance_m'] = dist
            s['modules'][0]['items'][0]['dose']['sets'] = 1
            sessions.append(s)
        p = copy.deepcopy(self.plan)
        p['sessions'] = sessions
        return p

    def test_single_run_over_phase_peak_needs_review(self):
        """单跑周单次超过本阶段已出现的最长单次 → 待审，不是放行。"""
        p = self._plan([(1, 3000), (1, 3000), (1, 4000), (2, 4000), (3, 6000)])
        review = check(p, self.assets)[1]
        self.assertTrue([r for r in review if '单跑周单次 6000' in r], review)

    def test_single_run_within_phase_peak_is_quiet(self):
        """等于本阶段已出现的单次最长值 → 不报。"""
        p = self._plan([(1, 3000), (1, 3000), (1, 4000), (2, 4000)])
        review = check(p, self.assets)[1]
        self.assertFalse([r for r in review if '单跑周' in r], review)

    def test_single_run_without_history_is_unverified(self):
        """本阶段没有可比的单次值 → 未核定，不当通过。"""
        p = self._plan([(1, 5000)])
        review = check(p, self.assets)[1]
        self.assertTrue([r for r in review if '未核定' in r and '单跑周' in r], review)


if __name__ == '__main__':
    unittest.main()

