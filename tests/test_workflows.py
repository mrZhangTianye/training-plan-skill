# -*- coding: utf-8 -*-
import copy
import datetime as dt
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import ROOT, read_json, library
from validate_plan import validate
from render_plan import render
from compare_plans import compare
from export_plan import export
from group_schedule import schedule


def item(uid, sets=3, reps=8, work=30, allocated=5):
    return {'unit_id': uid, 'duration_minutes': allocated, 'work_seconds_per_set': work,
            'dose_basis': '测试用近期可完成的3组8次，预先按正常完成安排递进',
            'cue': '保持控制', 'stop_condition': '新锐痛或失去控制时停止相关动作',
            'dose': {'sets': sets, 'reps': reps, 'duration_minutes': None, 'distance_m': None,
                     'per_side': False, 'load': {'target_rpe': 6, 'reference_weight_kg': None, 'reference_weight_unit': None,
                              'reference_weight_basis': None, 'selection_method': '首组取熟悉且偏轻的重量，做完明显多于3次按最小档加重，明显少于3次减重',
                              'description': '按目标RPE选择负重'},
                     'rest_seconds': 90, 'recovery_type': 'rest', 'notes': '保持质量'}}


def fixture():
    caps = read_json(ROOT / 'references/training-library/capabilities.json')
    goals = []
    for gid, cap, frequency, dose in [('G1', 'strength', 2, '3组8次，RPE6'), ('G2', 'endurance', 1, '轻松跑20分钟')]:
        goals.append({'id': gid, 'capability': cap, 'capability_ids': [cap], 'mode': 'develop',
                      'baseline': '虚构近期可完成剂量，仅供回归测试', 'desired_change': '正常完成后递进', 'rationale': '测试明确目标与刺激对应',
                      'baseline_basis': {'type': 'training_record', 'date': '2026-10-03', 'observation': '虚构已有训练起点', 'limitations': '回归测试，非真实用户', 'adequacy': 'sufficient'},
                      'progression_plan': [{'first_week': 1, 'last_week': 1, 'session_frequency': frequency, 'planned_dose': dose, 'progression': '正常完成既定剂量；下一周期增加一项变量'}]})
    sessions = []
    for ident, day in [('S1', '2026-10-05'), ('S2', '2026-10-07')]:
        sessions.append({'id': ident, 'week_number': 1, 'block_id': 'B1', 'date': day, 'title': '测试力量配对', 'kind': 'strength', 'role': 'training', 'status': 'planned',
                         'purpose': '发展力量', 'mini_goal': '完成3轮稳定动作', 'goal_ids': ['G1'], 'stimulus': '基础力量', 'fatigue_regions': ['legs', 'upper'],
                         'recovery_cost': 'moderate', 'duration_minutes': 10, 'session_rpe': None, 'start_time': '09:00', 'time_slot': '上午',
                         'modules': [{'title': '任意命名配对', 'group_label': 'A', 'duration_minutes': 10, 'items': [item('bodyweight_squat'), item('push_up')]}]})
    run = item('easy_run', sets=None, reps=None, work=1200, allocated=20)
    run['dose']['duration_minutes'] = 20
    run['dose']['rest_seconds'] = 0
    run['endurance_role'] = 'run'; run['run_intensity'] = 'easy'
    sessions.append({'id': 'S3', 'week_number': 1, 'block_id': 'B1', 'date': '2026-10-09', 'title': '测试轻松跑', 'kind': 'run', 'role': 'training', 'status': 'planned',
                     'purpose': '发展耐力', 'mini_goal': '轻松完成20分钟', 'goal_ids': ['G2'], 'stimulus': '轻松耐力', 'fatigue_regions': ['legs'], 'recovery_cost': 'low',
                     'duration_minutes': 20, 'session_rpe': None, 'start_time': '09:00', 'time_slot': '上午', 'modules': [{'title': '轻松跑', 'duration_minutes': 20, 'items': [run]}]})
    p = {'schema_version': '0.2', 'id': 'TEST', 'version': 1, 'level': 'week', 'title': '虚构回归测试', 'status': 'draft', 'intended_use': 'actual', 'start_date': '2026-10-05', 'duration_weeks': 1,
         'profile': {'pool': {'length_m': 25, 'pace_seconds_per_100m': 160}, 'id': 'fictional', 'baseline_date': '2026-10-03', 'available_minutes': {str(i): 60 for i in range(7)}, 'equipment': ['running_space', 'pool'],
                     'mastery': {'bodyweight_squat': 'independent', 'push_up': 'independent', 'easy_run': 'independent', 'swim_easy': 'independent'}, 'banned_units': [], 'restrictions': [],
                     'windows': [{'weekday': i, 'start': '06:00', 'end': '23:00'} for i in range(7)]},
         'objectives': goals, 'arrangement': {'status': 'selected', 'selection_basis': '虚构直接排课请求允许选择结构', 'rationale': '两次力量与一次轻松跑', 'weekly_template': ['两次力量', '一次跑'],
                                            'within_week_variation': '训练日之间安排恢复', 'between_week_variation': '按正常完成预先推进', 'progression_condition': '正常完成时推进，反馈可修正'},
         'blocks': [{'id': 'B1', 'first_week': 1, 'last_week': 1, 'focus': '建立剂量', 'goal_ids': ['G1', 'G2'], 'progression_condition': '正常完成后推进'}],
         'weeks': [{'number': 1, 'block_id': 'B1', 'focus': '测试基础安排', 'variation': '力量与轻松跑分开', 'module_summary': '力量2次，跑1次', 'detail_status': 'scheduled',
                    'session_ids': ['S1', 'S2', 'S3'], 'rest_days': ['2026-10-06', '2026-10-08', '2026-10-10', '2026-10-11'], 'progression_condition': '正常完成按预定推进'}],
         'sessions': sessions, 'evidence': [], 'design_review': [{'topic': t, 'outcome': 'pass', 'checked_ids': ['TEST', 'S1', 'S2', 'S3'], 'reason': '虚构测试检查了对应设计内容'} for t in ['goal_alignment', 'user_constraints', 'load_recovery', 'hierarchy', 'change_impact']],
         'design_context': {'coverage': [{'capability_id': c, 'mode': 'develop' if c in ('strength', 'endurance') else 'unassessed', 'rationale': '测试仅发展明确目标'} for c in caps],
                            'uncertainty_actions': [], 'recovery_review': '力量课间隔一天，跑为低成本', 'environment_context': '虚构标准条件', 'contact_budget': {}, 'review_resolutions': [],
                            'reentry': {'state': 'new', 'missed_days': 0, 'reason': '新建', 'current_basis': '虚构近期训练', 'first_session_strategy': '保守已熟悉剂量', 'association_review': '后续正常完成预定推进'}}}
    return p


def executable(p=None):
    p = p or fixture()
    p['status'] = 'executable'
    return p


class Workflows(unittest.TestCase):
    def assert_valid(self, p):
        result = validate(p)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['insufficient_basis'], [])
        return result

    def test_new_plan_and_selected_structure_without_log(self):
        r = self.assert_valid(executable())
        self.assertTrue(r['ready_to_render_executable'])
        self.assertEqual(fixture()['evidence'], [])

    def test_confirmed_structure_is_reused(self):
        p = executable(); p['arrangement']['status'] = 'confirmed'
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])

    def test_proposed_structure_is_not_executable(self):
        p = executable(); p['arrangement']['status'] = 'proposed'
        self.assertFalse(validate(p)['ready_to_render_executable'])

    def test_unknown_baseline_can_have_conservative_execution(self):
        p = executable(); b = p['objectives'][0]['baseline_basis']; b['type'] = 'unknown'; b['adequacy'] = 'unknown'
        p['design_context']['uncertainty_actions'] = ['先采用熟悉自重动作3组8次、RPE6，正常完成按预定推进']
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])

    def test_unknown_baseline_without_strategy_is_flagged(self):
        p = fixture(); p['objectives'][0]['baseline_basis']['adequacy'] = 'unknown'
        self.assertTrue(validate(p)['insufficient_basis'])

    def test_reference_weight_must_trace_to_tr(self):
        p = fixture()
        x = p['sessions'][0]['modules'][0]['items'][0]['dose']['load']
        x['reference_weight_kg'] = 20
        self.assertTrue(any('TR' in e for e in validate(p)['errors']))
        x['reference_weight_basis'] = 'TR 20kg×8（2026-05）'
        self.assertFalse(any('TR' in e for e in validate(p)['errors']))

    def test_selection_method_replaces_reference_weight(self):
        # 公斤数不是交付缺口：有组次＋目标RPE＋选重方法＋休息即可
        p = fixture()
        self.assertFalse(any('选重处方' in e for e in validate(p)['errors']))
        x = p['sessions'][0]['modules'][0]['items'][0]['dose']['load']
        del x['selection_method']
        self.assertTrue(any('选重处方' in e for e in validate(p)['errors']))
        x['reference_weight_kg'] = 20
        x['reference_weight_basis'] = 'TR 20kg×8（2026-05）'
        self.assertFalse(any('选重处方' in e for e in validate(p)['errors']))

    def test_loaded_item_needs_preset_rest(self):
        # 休息必须是预设单值：schema 层面禁 null，不靠执行时临场定
        p = fixture()
        x = p['sessions'][0]['modules'][0]['items'][0]['dose']
        x['rest_seconds'] = None
        self.assertTrue(any('rest_seconds' in e for e in validate(p)['errors']))

    def test_missing_progression_and_stage_overlap(self):
        p = fixture(); del p['objectives'][0]['progression_plan']
        self.assertTrue(any('递进' in x for x in validate(p)['insufficient_basis']))
        p = fixture(); p['objectives'][0]['progression_plan'] *= 2
        self.assertTrue(any('each plan week' in x for x in validate(p)['errors']))

    def test_stage_frequency_matches_actual_stimulus(self):
        p = fixture(); p['objectives'][0]['progression_plan'][0]['session_frequency'] = 3
        self.assertTrue(any('预定频率' in x for x in validate(p)['insufficient_basis']))

    def test_warmup_cannot_be_retagged_as_speed(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]; x['capability_ids'] = ['endurance', 'speed']
        self.assertTrue(any('capability override' in x for x in validate(p)['errors']))

    def test_unknown_mastery_in_first_group_item_is_flagged(self):
        p = fixture(); p['profile']['mastery']['bodyweight_squat'] = 'unknown'
        self.assertTrue(any('bodyweight_squat: mastery unknown' in x for x in validate(p)['insufficient_basis']))

    def test_simple_preparation_can_keep_unknown_without_blocking_complexity(self):
        p = fixture(); x = item('foam_roll', sets=None, reps=None, work=120, allocated=2)
        p['profile']['equipment'].append('foam_roller')
        x['dose']['duration_minutes'] = 2; x['dose']['rest_seconds'] = 0
        x['dose']['load']['target_rpe'] = None; x['dose']['load']['description'] = '温和、可控的已选局部准备'
        p['sessions'][0]['modules'].insert(0, {'title': '基础准备', 'duration_minutes': 2, 'items': [x]})
        p['sessions'][0]['duration_minutes'] += 2
        self.assertNotIn('foam_roll', p['profile']['mastery'])
        self.assert_valid(p)
        x['unit_id'] = 'hip_airplane'
        self.assertTrue(any('independent skill not established' in e for e in validate(p)['errors']))

    def test_pair_keeps_readable_order_and_rounds(self):
        p = executable(); self.assert_valid(p)
        body = render(p, 'session', session='S1')
        assets = library()
        self.assertLess(body.index(assets['bodyweight_squat']['name']), body.index(assets['push_up']['name']))
        self.assertIn('3轮', body)
        self.assertIn('A1', body)

    def test_triad_and_shared_recovery_are_feasible(self):
        p = fixture(); m = p['sessions'][0]['modules'][0]
        x = item('side_plank', reps=None, work=40, allocated=3)
        x['dose']['duration_minutes'] = 1 / 3; x['dose']['per_side'] = True
        p['profile']['mastery']['side_plank'] = 'independent'
        m['items'].append(x); m['duration_minutes'] = 13; p['sessions'][0]['duration_minutes'] = 13
        self.assert_valid(p)
        rendered = render(p, 'session', session='S1')
        assets = library()
        names = [assets[x['unit_id']]['name'] for x in m['items']]
        self.assertEqual(sorted(names, key=rendered.index), names)
        self.assertIn('3轮', rendered)
        self.assertIn('3×20秒/侧', rendered)
        # Per round 100 seconds; the other items satisfy part of the 90-second recovery.
        for x in m['items']:
            x['duration_minutes'] = 2
            x['dose']['rest_seconds'] = 120
        m['duration_minutes'] = 6; p['sessions'][0]['duration_minutes'] = 6
        self.assertTrue(any('combined active work and shared recovery' in x for x in validate(p)['errors']))

    def test_unequal_group_requires_explicit_set_order(self):
        p = fixture(); self.assert_valid(p)
        p['sessions'][0]['modules'][0]['items'][1]['dose']['sets'] = 2
        self.assertTrue(any('require an explicit set_sequence' in x for x in validate(p)['errors']))
        p['sessions'][0]['modules'][0]['set_sequence'] = [1, 2, 1, 2, 1]
        self.assert_valid(p)

    def test_three_two_two_preserves_dose_and_between_set_recovery(self):
        p = fixture(); m = p['sessions'][0]['modules'][0]
        m['items'][1]['dose']['sets'] = 2
        x = item('side_plank', sets=2, reps=None, work=40, allocated=3)
        x['dose']['duration_minutes'] = 1 / 3; x['dose']['per_side'] = True
        p['profile']['mastery']['side_plank'] = 'independent'
        m['items'].append(x); m['duration_minutes'] = 13; p['sessions'][0]['duration_minutes'] = 13
        m['set_sequence'] = [1, 2, 3, 1, 2, 3, 1]
        self.assert_valid(p)
        previous = {}
        for row in schedule(m):
            if row['item'] in previous:
                self.assertGreaterEqual(row['start'] - previous[row['item']], m['items'][row['item'] - 1]['dose']['rest_seconds'])
            previous[row['item']] = row['end']
        body = render(p, 'session', session='S1')
        self.assertIn('3／2／2组', body)
        self.assertNotIn('· 3轮', body)
        m['set_sequence'].append(2)
        self.assertTrue(any('counts must match' in e for e in validate(p)['errors']))

    def test_set_order_cannot_reference_missing_item_or_shorten_real_wait(self):
        p = fixture(); m = p['sessions'][0]['modules'][0]
        m['set_sequence'] = [1, 2, 3, 1, 2, 1]
        self.assertTrue(any('outside this group' in e for e in validate(p)['errors']))
        m['set_sequence'] = [1, 1, 1, 2, 2, 2]
        for x in m['items']: x['dose']['rest_seconds'] = 180
        self.assertTrue(any('combined active work' in e for e in validate(p)['errors']))

    def test_strength_wave_requires_same_anchor_both_days(self):
        p = fixture()
        p['design_context']['strength_waves'] = [{'unit_id': 'bodyweight_squat', 'first_week': 1, 'last_week': 1, 'rationale': '虚构同动作容量与较重工作组'}]
        a = p['sessions'][0]['modules'][0]['items'][0]
        b = p['sessions'][1]['modules'][0]['items'][0]
        a['wave_role'] = 'capacity'; b['wave_role'] = 'heavy'; b['dose']['reps'] = 5
        self.assert_valid(p)
        b['unit_id'] = 'push_up'
        self.assertTrue(any('缺少同动作' in e for e in validate(p)['insufficient_basis']))
        b['unit_id'] = 'bodyweight_squat'; b['dose']['reps'] = 8
        self.assertTrue(any('较低重复区间' in e for e in validate(p)['insufficient_basis']))

    def test_concrete_display_name_and_effort_anchor_are_visible(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]
        x['display_name'] = '轻松跑：连续主段'
        body = render(p, 'session', session='S3')
        self.assertIn('轻松跑：连续主段', body)
        x = p['sessions'][0]['modules'][0]['items'][0]
        x['dose']['load']['description'] = '做完约余3次规范动作'
        x['dose']['load']['target_rpe'] = 7
        self.assertIn('约余3次', render(p, 'session', session='S1'))
        x['dose']['load']['target_rpe'] = None
        x['dose']['load']['reference_weight_kg'] = 10
        x['dose']['load']['description'] = '每次下降3秒，完成后还能做3次规范动作'
        x['dose']['load']['execution_target'] = '每次下降3秒，完成后还能做3次规范动作'
        self.assertIn('下降3秒', render(p, 'session', session='S1'))

    def test_stage_preserves_changed_task_and_marks_unexpanded_weeks(self):
        p = fixture(); p['duration_weeks'] = 2; p['blocks'][0]['last_week'] = 2
        for g in p['objectives']:g['progression_plan'][0]['last_week'] = 2
        later = copy.deepcopy(p['sessions'])
        second = copy.deepcopy(p['weeks'][0]); second['number'] = 2; second['session_ids'] = []
        second['rest_days'] = [(dt.date.fromisoformat(d) + dt.timedelta(days=7)).isoformat() for d in second['rest_days']]
        for s in later:
            s['id'] += '-W2'; s['week_number'] = 2; s['date'] = (dt.date.fromisoformat(s['date']) + dt.timedelta(days=7)).isoformat()
            second['session_ids'].append(s['id'])
        p['sessions'] += later;p['weeks'].append(second)
        p['sessions'][2]['modules'][0]['items'][0]['display_name']='轻松跑：平路'
        later[2]['modules'][0]['items'][0]['display_name']='轻松跑：熟悉缓坡'
        later[0]['modules'][0]['items'][0]['dose']['rest_seconds']=120
        self.assert_valid(p)
        body=render(p,'block',block='B1')
        self.assertIn('轻松跑：熟悉缓坡',body)
        self.assertIn('恢复120秒',body)
        second['detail_status']='summary'
        self.assertIn('尚未展开执行课表',render(p,'overall'))

    def test_group_labels_are_unique_within_a_session(self):
        p = fixture(); self.assert_valid(p)
        s = p['sessions'][0]; s['modules'].append(copy.deepcopy(s['modules'][0])); s['duration_minutes'] = 20
        self.assertTrue(any('duplicate group label' in x for x in validate(p)['errors']))

    def test_title_does_not_create_a_group(self):
        p = fixture(); m = p['sessions'][0]['modules'][0]; del m['group_label']; m['title'] = '力量组合A'
        self.assert_valid(p)
        self.assertNotIn('组合顺序', render(p, 'session', session='S1'))

    def test_whole_set_seconds_already_include_sides(self):
        p = fixture(); x = p['sessions'][0]['modules'][0]['items'][0]; x['dose']['per_side'] = True
        self.assert_valid(p)  # work=30 is the complete bilateral set, not 60.
        x['dose']['duration_minutes'] = 0.5
        self.assertTrue(any('contradicts' in x for x in validate(p)['errors']))

    def test_repetition_work_time_is_required_and_checked(self):
        p = fixture(); x = p['sessions'][0]['modules'][0]['items'][0]; del x['work_seconds_per_set']
        self.assertTrue(any('work_seconds_per_set' in x for x in validate(p)['insufficient_basis']))
        p = fixture(); x = p['sessions'][0]['modules'][0]['items'][0]; x['work_seconds_per_set'] = 600
        self.assertTrue(any('active work exceeds' in x for x in validate(p)['errors']))

    def test_invalid_time_overlap_and_outside_window(self):
        p = fixture(); p['sessions'][0]['start_time'] = '99:00'; self.assertTrue(validate(p)['errors'])
        p = fixture(); p['sessions'][0]['start_time'] = '02:00'; self.assertTrue(any('outside availability' in x for x in validate(p)['errors']))
        p = fixture(); s = copy.deepcopy(p['sessions'][0]); s['id'] = 'extra'; p['sessions'].append(s); p['weeks'][0]['session_ids'].append('extra')
        self.assertTrue(any('overlapping sessions' in x for x in validate(p)['errors']))

    def test_flexible_single_session_and_provided_window(self):
        p = executable(); p['profile']['windows'] = []
        self.assertEqual(render(p, 'week', week=1).count('开始时间：09:00'), 3)
        for s in p['sessions']: del s['start_time']
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])
        body = render(p, 'week', week=1)
        self.assertNotIn('开始时间：', body)
        self.assertNotIn('09:00', body)
        p['profile']['windows'] = [{'weekday': 0, 'start': '06:00', 'end': '10:00'}]
        self.assertTrue(validate(p)['insufficient_basis'])

    def test_two_sessions_need_times_even_without_windows(self):
        p = fixture(); p['profile']['windows'] = []; s = copy.deepcopy(p['sessions'][0]); s['id'] = 'extra'; del s['start_time']; p['sessions'].append(s); p['weeks'][0]['session_ids'].append('extra')
        self.assertTrue(any('一日两练' in x for x in validate(p)['insufficient_basis']))

    def test_specific_overlap_requires_resolution(self):
        p = executable(); a, b = p['sessions'][:2]; b['date'] = '2026-10-06'; p['weeks'][0]['rest_days'][0] = '2026-10-07'
        a['recovery_cost'] = b['recovery_cost'] = 'high'
        r = validate(p); self.assertFalse(r['ready_to_render_executable'])
        self.assertEqual(r['review_requirements'][0]['review_id'], 'overlap:S1:S2')
        p['design_context']['review_resolutions'] = [{'review_id': 'overlap:S1:S2', 'context_hash': r['review_requirements'][0]['context_hash'], 'decision': 'accepted_tradeoff', 'rationale': '虚构短期安排：第二课仅保守RPE6、控制腿部总量，后两天不加高成本刺激'}]
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])

    def test_same_day_resolution_uses_stable_sorted_ids(self):
        p = fixture(); b = p['sessions'][1]; b['date'] = p['sessions'][0]['date']; b['start_time'] = '15:00'
        p['weeks'][0]['rest_days'].append('2026-10-07')
        r = validate(p); self.assertEqual(r['review_requirements'][0]['review_id'], 'same_day:S1:S2')
        self.assertTrue(any('same_day:S1:S2' in x for x in r['insufficient_basis']))

    def test_contact_budget_only_blocks_unhandled_tradeoff(self):
        p = executable(); x = p['sessions'][0]['modules'][0]['items'][0]; x['contacts_per_rep'] = 1
        p['design_context']['contact_budget']['2026-10-05'] = 10
        result = validate(p)
        self.assertFalse(result['ready_to_render_executable'])
        p['design_context']['review_resolutions'] = [{'review_id': 'contact_budget:2026-10-05', 'context_hash': result['review_requirements'][0]['context_hash'], 'decision': 'accepted_tradeoff', 'rationale': '虚构测试将预算内外差异逐项评估，保留24次但下次不加量'}]
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])

    def test_resolution_hash_tracks_substantive_changes_not_labels(self):
        p = executable(); a, b = p['sessions'][:2]; b['date'] = '2026-10-06'; p['weeks'][0]['rest_days'][0] = '2026-10-07'
        a['recovery_cost'] = b['recovery_cost'] = 'high'
        required = validate(p)['review_requirements'][0]
        p['design_context']['review_resolutions'] = [{'review_id': required['review_id'], 'context_hash': required['context_hash'], 'decision': 'accepted_tradeoff', 'rationale': '保留已有量和非力竭用力，后续两天只低成本活动'}]
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])
        a['title'] = '换标题与标点。'; a['modules'][0]['title'] = '重命名组合'; a['modules'][0]['group_label'] = 'Z'
        a['modules'][0]['items'][0]['dose']['load']['description'] = '按目标 RPE，选择负重。'
        a['modules'][0]['items'][0]['dose']['load']['target_rpe'] = 6.0
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])
        a['modules'][0]['items'][0]['dose']['load']['target_rpe'] = 8
        self.assertFalse(validate(p)['ready_to_render_executable'])
        self.assertTrue(any('旧处理' in x for x in validate(p)['review_items']))

    def test_contact_resolution_is_stale_after_count_or_budget_change(self):
        p = executable(); x = p['sessions'][0]['modules'][0]['items'][0]; x['contacts_per_rep'] = 1
        p['design_context']['contact_budget']['2026-10-05'] = 10
        required = validate(p)['review_requirements'][0]
        p['design_context']['review_resolutions'] = [{'review_id': required['review_id'], 'context_hash': required['context_hash'], 'decision': 'accepted_tradeoff', 'rationale': '按熟悉的24次接触和恢复配置保留此次安排'}]
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])
        x['dose']['reps'] = 9
        self.assertFalse(validate(p)['ready_to_render_executable'])
        x['dose']['reps'] = 8; p['design_context']['contact_budget']['2026-10-05'] = 12
        self.assertFalse(validate(p)['ready_to_render_executable'])

    def test_registered_contact_requirement_is_not_hardcoded(self):
        assets = copy.deepcopy(library())
        assets['bodyweight_squat']['requires_contact_count'] = True
        p = fixture()
        with patch('validate_plan.library', return_value=assets):
            self.assertTrue(any('接触量未定义' in x for x in validate(p)['insufficient_basis']))
            for s in p['sessions'][:2]:
                s['modules'][0]['items'][0]['contacts_per_rep'] = 1
                p['design_context']['contact_budget'][s['date']] = 24
            self.assert_valid(p)
            p['sessions'][0]['modules'][0]['items'][0]['contacts_per_rep'] = 0
            self.assertTrue(any('landing contacts must be positive' in x for x in validate(p)['errors']))

    def test_swim_sendoff_work_rest_and_total_time(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]; x['unit_id'] = 'swim_easy'; x['endurance_role'] = 'swim'; x.pop('run_intensity', None); x['dose']['distance_m'] = 25; x['dose']['sets'] = 4; x['dose']['duration_minutes'] = 1; x['work_seconds_per_set'] = 60
        x['dose']['recovery_type'] = 'sendoff'; x['dose']['sendoff_seconds'] = 90; x['dose']['rest_seconds'] = 0
        self.assert_valid(p)
        x['dose']['rest_seconds'] = 10; self.assertTrue(any('also add rest_seconds' in z for z in validate(p)['errors']))
        x['dose']['rest_seconds'] = 0; x['dose']['sendoff_seconds'] = 30; self.assertTrue(any('exceeds sendoff' in z for z in validate(p)['errors']))
        x['dose']['sendoff_seconds'] = 500; self.assertTrue(any('exceed allocated time' in z for z in validate(p)['errors']))
        x['dose']['recovery_type'] = 'rest'; self.assertTrue(any('requires sendoff recovery type' in z for z in validate(p)['errors']))

    def test_render_rejects_invalid_data_instead_of_claiming_pass(self):
        p = fixture(); p['sessions'][0]['modules'][0]['group_label'] = ''
        with self.assertRaises(ValueError): render(p, 'overall')

    def test_local_change_and_completed_history(self):
        a = fixture(); b = copy.deepcopy(a); b['version'] += 1; b['sessions'][0]['mini_goal'] = '用户要求调整本次小目标'
        r = compare(a, b, '用户主动修改，无需日志', [], '后续目标与剂量不变')
        self.assertTrue(r['changes']); self.assertIn('S1', r['affected_entities'])
        a['sessions'][0]['status'] = 'completed'
        with self.assertRaises(ValueError): compare(a, b, '修改历史', [], '核对')

    def test_optional_user_feedback_and_export(self):
        a = fixture(); b = copy.deepcopy(a); b['version'] += 1
        b['evidence'].append({'id': 'E1', 'date': '2026-10-05', 'source_type': 'performance', 'session_id': 'S1', 'raw': '虚构用户说今天困难', 'observations': ['主观困难'], 'interpretations': ['可调整后续'], 'actual_sets': []})
        self.assertEqual(compare(a, b, '用户反馈', ['E1'], '后续核对')['evidence_ids'], ['E1'])
        with tempfile.TemporaryDirectory() as d:
            names = export(executable(), Path(d) / 'v1'); self.assertEqual(len(names), 1)
            with self.assertRaises(ValueError): export(executable(), Path(d) / 'v1')

    def test_registered_asset_links(self):
        assets = library()
        for a in assets.values():
            for key in ('regressions', 'progressions'):
                for ident in a.get(key, []): self.assertIn(ident, assets)

    def test_aerobic_swim_counts_only_swimming_work_not_rest_or_sendoff(self):
        p = executable(); x = p['sessions'][2]['modules'][0]['items'][0]
        x['unit_id'] = 'swim_easy'; x['endurance_role'] = 'swim'; x.pop('run_intensity', None); x['dose']['sets'] = 6; x['dose']['duration_minutes'] = None
        x['dose']['distance_m'] = 100; x['work_seconds_per_set'] = 160; x['dose']['rest_seconds'] = 15
        x['aerobic_minutes'] = 16; x['aerobic_intensity'] = 'moderate'
        p['design_context']['aerobic_plan'] = {'target_weekly_equivalent_minutes': 16, 'rationale': '只统计已标注游进工作'}
        result = self.assert_valid(p)
        self.assertTrue(result['aerobic_summary']['goal_pass'])
        row = result['aerobic_summary']['weeks'][0]
        self.assertEqual(row['net_minutes'], 16); self.assertEqual(row['equivalent_minutes'], 16)
        self.assertNotEqual(row['net_minutes'], p['sessions'][2]['duration_minutes'])
        x['dose']['rest_seconds'] = 0; x['dose']['recovery_type'] = 'sendoff'; x['dose']['sendoff_seconds'] = 180
        self.assertEqual(self.assert_valid(p)['aerobic_summary']['weeks'][0]['net_minutes'], 16)

    def test_unknown_aerobic_intensity_is_not_inferred_from_type_or_rpe(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]; x['dose']['load']['target_rpe'] = 9
        result = self.assert_valid(p)
        self.assertEqual(result['aerobic_summary']['weeks'][0]['equivalent_minutes'], 0)
        self.assertFalse(result['aerobic_summary']['annotations_complete'])
        x['aerobic_minutes'] = 20
        p['design_context']['aerobic_plan'] = {'target_weekly_equivalent_minutes': 20, 'rationale': '本计划需明确工作强度'}
        self.assertFalse(validate(p)['aerobic_summary']['goal_pass'])
        self.assertEqual(validate(p)['aerobic_summary']['weeks'][0]['equivalent_minutes'], 0)
        x['aerobic_intensity'] = 'vigorous'
        result = self.assert_valid(p)
        self.assertEqual(result['aerobic_summary']['weeks'][0]['equivalent_minutes'], 40)
        self.assertTrue(result['aerobic_summary']['goal_pass'])

    def test_aerobic_allocation_cannot_claim_whole_strength_session_time(self):
        p = fixture(); x = p['sessions'][0]['modules'][0]['items'][0]
        x['aerobic_minutes'] = p['sessions'][0]['duration_minutes']; x['aerobic_intensity'] = 'moderate'
        self.assertTrue(any('aerobic minutes exceed active work' in e for e in validate(p)['errors']))

    def test_light_aerobic_work_has_no_moderate_equivalent(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]
        x['aerobic_minutes'] = 20; x['aerobic_intensity'] = 'light'
        row = self.assert_valid(p)['aerobic_summary']['weeks'][0]
        self.assertEqual(row['net_minutes'], 20); self.assertEqual(row['equivalent_minutes'], 0)

    def test_target_endpoint_gap_cannot_be_cleared_by_early_build_up(self):
        p = fixture(); p['duration_weeks'] = 2; p['blocks'][0]['last_week'] = 2
        for goal in p['objectives']: goal['progression_plan'][0]['last_week'] = 2
        second = copy.deepcopy(p['weeks'][0]); second['number'] = 2; second['session_ids'] = []
        second['rest_days'] = [(dt.date.fromisoformat(d) + dt.timedelta(days=7)).isoformat() for d in second['rest_days']]
        later = copy.deepcopy(p['sessions'])
        for s in later:
            s['id'] += '-W2'; s['week_number'] = 2; s['date'] = (dt.date.fromisoformat(s['date']) + dt.timedelta(days=7)).isoformat()
            second['session_ids'].append(s['id'])
        p['sessions'] += later; p['weeks'].append(second)
        for s in p['sessions']:
            if s['kind'] == 'run':
                x = s['modules'][0]['items'][0]; x['aerobic_minutes'] = 20; x['aerobic_intensity'] = 'moderate'
        p['design_context']['aerobic_plan'] = {'target_weekly_equivalent_minutes': 30, 'target_by_week': {}, 'rationale': '第一周建立量，第二周达到30分钟当量'}
        p['status'] = 'executable'
        result = validate(p)
        self.assertIsNone(result['aerobic_summary']['weeks'][0]['target_minutes'])
        self.assertEqual(result['aerobic_summary']['weeks'][0]['goal_status'], 'build_up')
        self.assertEqual(result['aerobic_summary']['weeks'][1]['goal_status'], 'gap')
        self.assertFalse(result['ready_to_render_executable']); self.assertFalse(result['aerobic_summary']['goal_pass'])
        with self.assertRaises(ValueError):
            render(p, 'overall')
        s = next(s for s in p['sessions'] if s['id'] == 'S3-W2'); x = s['modules'][0]['items'][0]
        x['aerobic_minutes'] = 30; x['dose']['duration_minutes'] = 30; x['work_seconds_per_set'] = 1800
        x['duration_minutes'] = 30; s['modules'][0]['duration_minutes'] = 30; s['duration_minutes'] = 30
        self.assertTrue(self.assert_valid(p)['ready_to_render_executable'])


if __name__ == '__main__':
    unittest.main()

STANDARD_FORM_OK = [
    (12, [(1, 3), (4, 6), (7, 9), (10, 12)]),
    (9, [(1, 3), (4, 6), (7, 9)]),
    (6, [(1, 3), (4, 6)]),
    (4, [(1, 1), (2, 2), (3, 3), (4, 4)]),
    (4, [(1, 4)]),
    (3, [(1, 3)]),
]

def _plan_of(spans):
    import copy
    p = copy.deepcopy(fixture())
    n = spans[-1][1]
    p['duration_weeks'] = n
    weeks = []
    for k in range(1, n + 1):
        weeks.append({'number': k, 'block_id': None, 'focus': 'f', 'variation': 'v',
                      'module_summary': 'm', 'detail_status': 'summary', 'session_ids': [],
                      'rest_days': [], 'progression_condition': 'c'})
    p['weeks'] = weeks
    blocks = []
    for i, (a, b) in enumerate(spans):
        bid = 'B' + str(i + 1)
        blocks.append({'id': bid, 'first_week': a, 'last_week': b, 'focus': 'f',
                       'goal_ids': ['G1'], 'progression_condition': 'c'})
        for w in p['weeks']:
            if a <= w['number'] <= b:
                w['block_id'] = bid
    p['blocks'] = blocks
    return p

def test_periodization_accepts_all_standard_lengths():
    """周数是参数：12/9/6/4/3 各有标准切分，全部放行。"""
    for n, spans in STANDARD_FORM_OK:
        errs = validate(_plan_of(spans))['errors']
        assert not any('切分应为' in e for e in errs), (n, spans, errs)

def test_periodization_rejects_mis_split_blocks():
    """同长度错切分必须被拒：12 周切成三个 4 周、4 周切成两个 2 周都不合法。"""
    for n, spans in [(12, [(1, 4), (5, 8), (9, 12)]), (4, [(1, 2), (3, 4)])]:
        errs = validate(_plan_of(spans))['errors']
        assert any('切分应为' in e for e in errs), (n, spans, errs)
