# -*- coding: utf-8 -*-
"""Regression contracts for prescribed distance, derived time and review validity."""
import copy
import unittest

from test_workflows import fixture, item
from render_plan import render
from validate_plan import validate
from work_timing import derived_estimates, whole_set_seconds


TIMING_CONFLICT = ('whole-set work estimate contradicts prescribed timed work: '
                   '组工作时间与次数节奏或泳速推导不一致')


def swim_fixture(distance=25):
    """Keep the original fixture's dates and goals; replace only its endurance task."""
    plan = fixture()
    session = plan['sessions'][2]
    session['kind'] = 'swim'
    plan['weeks'][0]['module_summary'] = '力量2次，泳1次'
    task = session['modules'][0]['items'][0]
    task['unit_id'] = 'swim_easy'
    task['endurance_role'] = 'swim'
    task.pop('run_intensity')
    task['work_seconds_per_set'] = 40
    task['dose'].update(sets=4, reps=None, duration_minutes=None,
                        distance_m=distance, rest_seconds=30)
    task['dose']['load']['target_rpe'] = None
    task['dose']['load']['description'] = '轻松游，动作与呼吸可控'
    return plan


class EnduranceContract(unittest.TestCase):
    def assert_clean(self, plan):
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['insufficient_basis'], [])
        return result

    def test_unknown_run_distance_stays_unknown_in_session_and_week(self):
        plan = fixture()
        result = self.assert_clean(plan)['endurance_summary']
        for row in (result['sessions']['S3'], result['weeks'][0]):
            self.assertEqual(row['run_minutes'], 20)
            self.assertIsNone(row['run_distance_m'])
            self.assertFalse(row['run_distance_complete'])
            self.assertEqual(row['run_distance_status'], 'unknown')
        body = render(plan, 'session', session='S3')
        self.assertIn('总跑动20分钟；距离未估算', body)
        self.assertNotIn('总跑量0米', body)
        self.assertNotIn('总跑量0公里', body)

    def test_known_partial_run_distance_cannot_become_a_complete_total(self):
        plan = fixture()
        session = plan['sessions'][2]
        known = copy.deepcopy(session['modules'][0]['items'][0])
        known['duration_minutes'] = 5
        known['work_seconds_per_set'] = 300
        known['dose'].update(duration_minutes=5, distance_m=1000)
        session['modules'][0]['items'].append(known)
        session['modules'][0]['duration_minutes'] = session['duration_minutes'] = 25
        summary = self.assert_clean(plan)['endurance_summary']
        for row in (summary['sessions']['S3'], summary['weeks'][0]):
            self.assertEqual(row['run_distance_known_m'], 1000)
            self.assertIsNone(row['run_distance_m'])
            self.assertFalse(row['run_distance_complete'])
            self.assertEqual(row['run_distance_status'], 'unknown')
        self.assertIn('总跑动25分钟；距离未估算', render(plan, 'session', session='S3'))

    def test_estimated_run_distance_is_not_rendered_as_exact_distance(self):
        plan = fixture()
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['dose']['distance_estimate_m'] = 3000
        task['dose']['distance_estimate_basis'] = '虚构近期20分钟约3000米，作为本堂预算'
        summary = self.assert_clean(plan)['endurance_summary']
        for row in (summary['sessions']['S3'], summary['weeks'][0]):
            self.assertEqual(row['run_distance_m'], 3000)
            self.assertTrue(row['run_distance_complete'])
            self.assertEqual(row['run_distance_status'], 'estimated')
        self.assertIn('预计总跑量3公里', render(plan, 'session', session='S3'))
        task['dose']['distance_m'] = 3000
        result = validate(plan)
        self.assertIn('S3/easy_run: 预计跑距只用于没有确定距离的跑段', result['errors'])

    def test_estimated_run_distance_without_basis_is_an_execution_gap(self):
        plan = fixture()
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['dose']['distance_estimate_m'] = 3000
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn('S3/easy_run: 预计跑距需有个人配速等估算依据', result['insufficient_basis'])
        self.assertFalse(result['ready_to_render_executable'])

    def test_swim_33m_repeats_are_rejected_in_a_25m_pool(self):
        plan = swim_fixture(distance=33)
        result = validate(plan)
        self.assertIn('S3/swim_easy: 组距必须符合池长；局部短段需明确partial_length及安全完成方式',
                      result['errors'])
        self.assertFalse(result['deterministic_pass'])

    def test_session_pool_override_controls_the_distance_rule(self):
        plan = swim_fixture()
        self.assert_clean(plan)  # Four 25m lengths fit the profile's 25m pool.
        plan['sessions'][2]['pool_length_m'] = 50
        result = validate(plan)
        self.assertIn('S3/swim_easy: 组距必须符合池长；局部短段需明确partial_length及安全完成方式',
                      result['errors'])
        plan['sessions'][2]['modules'][0]['items'][0]['dose']['distance_m'] = 50
        self.assert_clean(plan)

    def test_partial_length_requires_an_explicit_completion_route(self):
        plan = swim_fixture()
        plan['sessions'][2]['pool_length_m'] = 50
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['partial_length'] = True
        task['dose']['sets'] = 1
        task['dose']['rest_seconds'] = 0
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn('S3/swim_easy: 池中短段需说明起止位置及如何完成剩余池长', result['insufficient_basis'])
        task['execution_note'] = '从池边起游25米关注点段，直接接后项25米轻松整泳到对岸，中途不休息'
        remainder = copy.deepcopy(task)
        remainder['execution_note'] = '直接承接前项，从池中25米位置轻松游到对岸；两项构成完整50米后结束'
        plan['sessions'][2]['modules'][0]['items'].append(remainder)
        plan['sessions'][2]['modules'][0]['duration_minutes'] = 40
        plan['sessions'][2]['duration_minutes'] = 40
        summary = self.assert_clean(plan)['endurance_summary']['sessions']['S3']
        self.assertEqual(summary['swim_distance_m'], 50)
        self.assertTrue(summary['swim_distance_complete'])

    def test_swim_distance_cannot_be_multiplied_per_side(self):
        plan = swim_fixture()
        plan['sessions'][2]['modules'][0]['items'][0]['dose']['per_side'] = True
        self.assertIn('S3/swim_easy: 泳距离不按左右侧重复计量', validate(plan)['errors'])

    def test_actual_swim_needs_a_pool_length_but_allows_a_session_override(self):
        plan = swim_fixture()
        del plan['profile']['pool']
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn('S3: 需明确本课泳池长度', result['insufficient_basis'])
        plan['sessions'][2]['pool_length_m'] = 25
        self.assert_clean(plan)

    def test_tempo_derives_complete_set_time_without_a_declared_estimate(self):
        plan = fixture()
        task = plan['sessions'][0]['modules'][0]['items'][0]
        task['tempo_seconds_per_rep'] = 4
        del task['work_seconds_per_set']
        self.assertEqual(derived_estimates(task), {'repetitions': 32})
        self.assertEqual(whole_set_seconds(task), 32)
        self.assert_clean(plan)

    def test_tempo_and_declared_set_seconds_must_agree(self):
        plan = fixture()
        task = plan['sessions'][0]['modules'][0]['items'][0]
        task['tempo_seconds_per_rep'] = 4  # Eight repetitions require 32s, not the fixture's 30s.
        self.assertIn('S1/bodyweight_squat: ' + TIMING_CONFLICT, validate(plan)['errors'])
        task['work_seconds_per_set'] = 32
        self.assert_clean(plan)

    def test_per_side_tempo_is_a_whole_set_estimate_not_a_second_set_count(self):
        task = item('split_squat', sets=3, reps=6, work=48)
        task['dose']['per_side'] = True
        task['tempo_seconds_per_rep'] = 4
        self.assertEqual(derived_estimates(task), {'repetitions': 48})
        self.assertEqual(whole_set_seconds(task), 48)

    def test_swim_pace_derives_net_swimming_time_separately_from_rest(self):
        plan = swim_fixture()
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['swim_pace_seconds_per_100m'] = 200
        del task['work_seconds_per_set']
        task['aerobic_minutes'] = 10 / 3
        task['aerobic_intensity'] = 'moderate'
        result = self.assert_clean(plan)
        self.assertEqual(derived_estimates(task), {'swim_pace': 50})
        self.assertEqual(whole_set_seconds(task), 50)
        self.assertAlmostEqual(result['aerobic_summary']['weeks'][0]['net_minutes'], 10 / 3)
        self.assertNotEqual(result['aerobic_summary']['weeks'][0]['net_minutes'],
                            task['duration_minutes'])
        self.assertEqual(result['endurance_summary']['sessions']['S3']['swim_distance_m'], 100)

    def test_swim_pace_and_declared_time_cannot_disagree(self):
        plan = swim_fixture()
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['swim_pace_seconds_per_100m'] = 200
        self.assertIn('S3/swim_easy: ' + TIMING_CONFLICT, validate(plan)['errors'])
        task['work_seconds_per_set'] = 50
        self.assert_clean(plan)

    def test_actual_strength_needs_an_effort_or_quality_execution_anchor(self):
        plan = fixture()
        task = plan['sessions'][0]['modules'][0]['items'][0]
        task['dose']['load']['target_rpe'] = None
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn('S1/bodyweight_squat: 缺少本组努力或质量的执行锚点，需execution_target或适用的目标RPE',
                      result['insufficient_basis'])
        task['dose']['load']['execution_target'] = '做完规定次数还能按相同质量完成4次'
        self.assert_clean(plan)

    def test_missing_review_references_are_an_execution_gap(self):
        plan = fixture()
        del plan['design_review'][0]['checked_ids']
        result = validate(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn('goal_alignment: 设计审查需关联具体目标、阶段或课程ID', result['insufficient_basis'])
        plan['design_review'][0]['checked_ids'] = ['G1', 'B1', 'S1']
        self.assert_clean(plan)

    def test_unknown_review_reference_is_a_structural_error(self):
        plan = fixture()
        plan['design_review'][0]['checked_ids'] = ['G1', 'missing-session']
        self.assertIn('goal_alignment: 审查引用未知目标、阶段或课程ID', validate(plan)['errors'])

    def resolved_recovery_plan(self, mode='strength', prepare=None):
        plan = swim_fixture() if mode == 'swim' else fixture()
        plan['status'] = 'executable'
        if prepare:
            prepare(plan)
        if mode == 'strength':
            first, second = plan['sessions'][:2]
            second['date'] = '2026-10-06'
            plan['weeks'][0]['rest_days'][0] = '2026-10-07'
            first['recovery_cost'] = second['recovery_cost'] = 'high'
            review_id = 'overlap:S1:S2'
        else:
            first, second = plan['sessions'][0], plan['sessions'][2]
            second['date'] = first['date']
            second['start_time'] = '15:00'
            second['recovery_cost'] = 'moderate'
            plan['weeks'][0]['rest_days'].append('2026-10-09')
            review_id = 'same_day:S1:S3'
        result = validate(plan)
        requirement = next(r for r in result['review_requirements'] if r['review_id'] == review_id)
        plan['design_context']['review_resolutions'] = [{
            'review_id': review_id, 'context_hash': requirement['context_hash'],
            'decision': 'accepted_tradeoff',
            'rationale': '虚构测试保留当前具体剂量和恢复，不增加其他高成本训练'}]
        self.assertTrue(self.assert_clean(plan)['ready_to_render_executable'])
        return plan, review_id, requirement['context_hash']

    def assert_resolution_stale(self, plan, review_id, prior_hash):
        result = validate(plan)
        requirement = next(r for r in result['review_requirements'] if r['review_id'] == review_id)
        self.assertNotEqual(requirement['context_hash'], prior_hash)
        self.assertIsNone(requirement['resolution'])
        self.assertIn(review_id + ': 需在review_resolutions记录当前context_hash、本项决定与具体理由',
                      result['insufficient_basis'])
        self.assertFalse(result['ready_to_render_executable'])

    def test_recovery_resolution_is_stale_after_execution_target_changes(self):
        def prepare(plan):
            task = plan['sessions'][0]['modules'][0]['items'][0]
            task['dose']['load']['execution_target'] = '做完约余4次相同质量动作'
        plan, review_id, prior_hash = self.resolved_recovery_plan(prepare=prepare)
        task = plan['sessions'][0]['modules'][0]['items'][0]
        task['dose']['load']['execution_target'] = '做完约余2次相同质量动作'
        self.assert_resolution_stale(plan, review_id, prior_hash)

    def test_recovery_resolution_is_stale_after_run_intensity_changes(self):
        def prepare(plan):
            task = plan['sessions'][2]['modules'][0]['items'][0]
            task['unit_id'] = 'controlled_hard_run'
            task['run_intensity'] = 'tempo'
            plan['profile']['mastery']['controlled_hard_run'] = 'independent'
        plan, review_id, prior_hash = self.resolved_recovery_plan(mode='run', prepare=prepare)
        plan['sessions'][2]['modules'][0]['items'][0]['run_intensity'] = 'interval'
        self.assert_resolution_stale(plan, review_id, prior_hash)

    def test_recovery_resolution_is_stale_after_estimated_run_distance_changes(self):
        def prepare(plan):
            task = plan['sessions'][2]['modules'][0]['items'][0]
            task['dose']['distance_estimate_m'] = 3000
            task['dose']['distance_estimate_basis'] = '按虚构近期个人轻松配速估算20分钟距离'
        plan, review_id, prior_hash = self.resolved_recovery_plan(mode='run', prepare=prepare)
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['dose']['distance_estimate_m'] = 3300
        self.assert_resolution_stale(plan, review_id, prior_hash)

    def test_recovery_resolution_is_stale_after_tempo_derived_time_changes(self):
        def prepare(plan):
            task = plan['sessions'][0]['modules'][0]['items'][0]
            task['tempo_seconds_per_rep'] = 4
            del task['work_seconds_per_set']
        plan, review_id, prior_hash = self.resolved_recovery_plan(prepare=prepare)
        task = plan['sessions'][0]['modules'][0]['items'][0]
        task['tempo_seconds_per_rep'] = 5
        self.assert_resolution_stale(plan, review_id, prior_hash)

    def test_recovery_resolution_is_stale_after_swim_pace_derived_time_changes(self):
        def prepare(plan):
            task = plan['sessions'][2]['modules'][0]['items'][0]
            task['swim_pace_seconds_per_100m'] = 160
            del task['work_seconds_per_set']
        plan, review_id, prior_hash = self.resolved_recovery_plan(mode='swim', prepare=prepare)
        task = plan['sessions'][2]['modules'][0]['items'][0]
        task['swim_pace_seconds_per_100m'] = 200
        self.assert_resolution_stale(plan, review_id, prior_hash)


if __name__ == '__main__':
    unittest.main()
