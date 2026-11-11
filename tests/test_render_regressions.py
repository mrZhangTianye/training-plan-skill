# -*- coding: utf-8 -*-
"""Regression coverage for user-visible totals and semantic stage alignment."""
import copy
import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import ROOT, library, write_json
from render_plan import render, session_body, stage_matrix, intensity_string
from test_workflows import fixture, item


def render_fixture():
    p = fixture()
    p['sessions'][0]['title'] = '容量课'
    p['sessions'][1]['title'] = '较重课'
    for session in p['sessions']:
        for module in session['modules']:
            for entry in module['items']:
                entry['dose']['load']['description'] = '做完仍余4次规范动作'
                entry['dose']['load']['execution_target'] = '做完仍余4次规范动作'
                if session['kind'] == 'run':
                    entry['dose']['load']['target_rpe'] = None
                    entry['dose']['load']['description'] = '能连贯交谈，呼吸提高且可控'
                    entry['dose']['load']['execution_target'] = '能连贯交谈，呼吸提高且可控'
                    entry['endurance_role'] = 'run'
                    entry['run_intensity'] = 'easy'
    return p


def two_weeks():
    p = render_fixture()
    p['duration_weeks'] = 2
    p['blocks'][0]['last_week'] = 2
    for goal in p['objectives']:
        goal['progression_plan'][0]['last_week'] = 2
    later = copy.deepcopy(p['sessions'])
    week = copy.deepcopy(p['weeks'][0])
    week['number'] = 2
    week['session_ids'] = []
    week['rest_days'] = [(dt.date.fromisoformat(day) + dt.timedelta(days=7)).isoformat() for day in week['rest_days']]
    for session in later:
        session['id'] += '-W2'
        session['week_number'] = 2
        session['date'] = (dt.date.fromisoformat(session['date']) + dt.timedelta(days=7)).isoformat()
        week['session_ids'].append(session['id'])
    p['sessions'] += later
    p['weeks'].append(week)
    return p, later


def timed_entry(uid, minutes, role, intensity=None, sets=None):
    entry = item(uid, sets=sets, reps=None, work=minutes * 60, allocated=minutes * (sets or 1))
    entry['dose']['duration_minutes'] = minutes
    entry['dose']['rest_seconds'] = 0
    entry['dose']['load']['target_rpe'] = None
    entry['dose']['load']['description'] = '以规定呼吸和可控动作完成'
    entry['dose']['load']['execution_target'] = '以规定呼吸和可控动作完成'
    entry['endurance_role'] = role
    if intensity:
        entry['run_intensity'] = intensity
    return entry


class RenderRegressions(unittest.TestCase):
    def test_date_reordering_does_not_exchange_capacity_and_heavy_rows(self):
        p, later = two_weeks()
        for session in (p['sessions'][1], later[1]):
            for entry in session['modules'][0]['items']:
                entry['dose']['reps'] = 5
        later[0]['date'], later[1]['date'] = later[1]['date'], later[0]['date']
        body = render(p, 'block', block='B1')
        capacity = body.split('### 容量课', 1)[1].split('### 较重课', 1)[0]
        heavy = body.split('### 较重课', 1)[1].split('\n### ', 1)[0]
        self.assertNotIn('3×5', capacity)
        self.assertNotIn('3×8', heavy)
        self.assertIn('3×8', capacity)
        self.assertIn('3×5', heavy)

    def test_reordered_modules_and_items_match_semantic_identity(self):
        p, later = two_weeks()
        for session in (p['sessions'][0], later[0]):
            module = copy.deepcopy(session['modules'][0])
            module['title'] = '辅助配对'
            module['group_label'] = 'B'
            for entry in module['items']:
                entry['dose']['reps'] = 6
            session['modules'].append(module)
        later[0]['modules'].reverse()
        for module in later[0]['modules']:
            module['items'].reverse()
        body = stage_matrix(p, p['blocks'][0], library())
        capacity = body.split('### 容量课', 1)[1].split('### 较重课', 1)[0]
        primary = capacity.split('#### 任意命名配对', 1)[1].split('#### 辅助配对', 1)[0]
        self.assertNotIn('3×6', primary)
        row = next(line for line in primary.splitlines() if '自重深蹲' in line)
        self.assertEqual(row.count('3×8'), 2)

    def test_explicit_ids_preserve_renamed_course_module_and_item(self):
        p, later = two_weeks()
        for session in (p['sessions'][0], later[0]):
            session['course_id'] = 'capacity'
            session['modules'][0]['id'] = 'main'
            for index, entry in enumerate(session['modules'][0]['items']):
                entry['id'] = 'main-' + str(index)
        later[0]['title'] = '容量课新标题'
        later[0]['modules'][0]['title'] = '主力配对新标题'
        later[0]['modules'][0]['items'][0]['display_name'] = '主力自重蹲'
        body = stage_matrix(p, p['blocks'][0], library())
        self.assertEqual(body.count('### 容量课\n'), 1)
        self.assertIn('主力自重蹲 · 3×8', body)
        self.assertIn('W2：课程：容量课新标题', body)
        self.assertIn('W2：模块：主力配对新标题', body)

    def test_ambiguous_legacy_courses_are_split_with_visible_notice(self):
        p, later = two_weeks()
        for session in p['sessions']:
            if session['kind'] == 'strength':
                session['title'] = '同名力量课'
        body = stage_matrix(p, p['blocks'][0], library())
        self.assertIn('重名课程', body)
        self.assertIn('未跨周合并', body)
        self.assertEqual(body.count('### 同名力量课 · '), 4)
        for line in body.splitlines():
            if '自重深蹲' in line:
                self.assertEqual(line.count('3×8'), 1)

    def test_duplicate_explicit_course_or_item_ids_raise_clear_errors(self):
        p = render_fixture()
        p['sessions'][0]['course_id'] = 'duplicate'
        p['sessions'][1]['course_id'] = 'duplicate'
        with self.assertRaisesRegex(ValueError, '稳定编号重复.*duplicate'):
            stage_matrix(p, p['blocks'][0], library())
        p = render_fixture()
        for entry in p['sessions'][0]['modules'][0]['items']:
            entry['id'] = 'duplicate'
        with self.assertRaisesRegex(ValueError, '稳定编号重复.*duplicate'):
            stage_matrix(p, p['blocks'][0], library())

    def test_mixed_note_rows_have_dash_for_missing_necessary_note(self):
        p = render_fixture()
        p['sessions'][0]['modules'][0]['items'][0]['execution_note'] = '下放保持可控'
        p['sessions'][0]['modules'][0]['items'][1]['execution_note'] = '  '
        body = session_body(p['sessions'][0], library())
        self.assertIn('必要提示', body)
        row = next(line for line in body.splitlines() if '| A2 ' in line)
        self.assertTrue(row.endswith('| — |'))

    def test_only_explicit_execution_notes_are_shown_without_prose_filters(self):
        p = render_fixture()
        entry = p['sessions'][0]['modules'][0]['items'][0]
        entry['dose']['notes'] = '后台剂量判断不应显示'
        entry['execution_note'] = '正常完成后按指定组序继续'
        body = session_body(p['sessions'][0], library())
        self.assertIn('正常完成后按指定组序继续', body)
        self.assertNotIn('后台剂量判断不应显示', body)
        self.assertEqual(intensity_string({'target_rpe': None, 'reference_weight_kg': None, 'description': '保持质量'}), '保持质量')
        self.assertIn('躯干方向稳定', intensity_string({'target_rpe': None, 'reference_weight_kg': None, 'description': '兼容说明', 'execution_target': '躯干方向稳定'}))
        self.assertIn('约余3次', intensity_string({'target_rpe': 7, 'reference_weight_kg': None, 'description': '规范重复'}))

    def test_draft_shows_concrete_execution_gaps_in_every_view(self):
        p = render_fixture()
        p['sessions'][0]['modules'][0]['items'][0].pop('dose_basis')
        for view, args in [('overall', {}), ('block', {'block': 'B1'}), ('week', {'week': 1}), ('session', {'session': 'S1'})]:
            body = render(p, view, **args)
            self.assertIn('执行前需补齐', body)
            self.assertIn('S1/bodyweight_squat', body)
            self.assertIn('剂量依据', body)
            self.assertNotIn('数据结构与声明时间检查通过', body)

    def test_draft_missing_group_work_time_remains_renderable(self):
        p = render_fixture()
        p['sessions'][0]['modules'][0]['items'][0].pop('work_seconds_per_set')
        body = render(p, 'session', session='S1')
        self.assertIn('work_seconds_per_set', body)
        self.assertIn('完整组工作时间待补', body)

    def test_unknown_ids_list_available_choices_in_chinese(self):
        p = render_fixture()
        for view, args, label, known in [('session', {'session': 'missing'}, '单次课', 'S1'), ('block', {'block': 'missing'}, '阶段', 'B1'), ('week', {'week': 7}, '周', '1')]:
            with self.assertRaisesRegex(ValueError, label + '编号.*可用编号.*' + known):
                render(p, view, **args)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            write_json(path, p)
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/render_plan.py'), str(path), '--view', 'session', '--session', 'missing', '--output', str(Path(directory) / 'session.md')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('可用编号：S1', result.stderr)

    def test_session_and_week_run_totals_include_all_running_and_exclude_walking(self):
        p = render_fixture()
        session = p['sessions'][2]
        entries = [timed_entry('warmup', 5, 'walk'), timed_entry('easy_run', 5, 'run', 'easy'), timed_entry('controlled_hard_run', 4, 'run', 'interval', sets=2), timed_entry('brisk_walk', 2, 'walk'), timed_entry('easy_run', 3, 'run', 'easy')]
        session['modules'][0]['items'] = entries
        session['duration_minutes'] = session['modules'][0]['duration_minutes'] = 23
        p['profile']['mastery'].update({'controlled_hard_run': 'independent', 'brisk_walk': 'independent'})
        body = render(p, 'week', week=1)
        self.assertIn('总跑动16分钟；距离未估算', body)
        self.assertIn('轻松8分钟（50%），非轻松8分钟（50%）', body)
        self.assertIn('间歇8分钟', body)
        self.assertIn('跑泳单次总量', body)

    def test_handwritten_numeric_variation_is_rejected_instead_of_displayed(self):
        p = render_fixture()
        p['weeks'][0]['variation'] = '容量3×12，主跑20分钟'
        with self.assertRaisesRegex(ValueError, 'variation含手写数字处方'):
            render(p, 'week', week=1)

    def test_week_strength_wave_summary_uses_actual_doses(self):
        p = render_fixture()
        p['design_context']['strength_waves'] = [{'unit_id': 'bodyweight_squat', 'first_week': 1, 'last_week': 1, 'rationale': '同一主力两种重复区间'}]
        p['sessions'][0]['modules'][0]['items'][0]['wave_role'] = 'capacity'
        heavy = p['sessions'][1]['modules'][0]['items'][0]
        heavy['wave_role'] = 'heavy'
        heavy['dose']['reps'] = 5
        heavy['dose']['load']['target_rpe'] = 8
        heavy['dose']['load']['execution_target'] = '较大负重完成后约余2次'
        p['weeks'][0]['variation'] = '容量与较重分日，跑步保持轻松'
        body = render(p, 'week', week=1)
        section = body.split('本周主力波动：', 1)[1].split('计划周总量：', 1)[0]
        self.assertIn('| 自重深蹲 | S1 | 容量型 | 3×8 |', section)
        self.assertIn('| 自重深蹲 | S2 | 控制型 | 3×5 |', section)
        p['sessions'][0]['modules'][0]['items'][0]['dose']['reps'] = 9
        self.assertIn('| 自重深蹲 | S1 | 容量型 | 3×9 |', render(p, 'week', week=1))
        self.assertNotIn('本周主力波动：', render(render_fixture(), 'week', week=1))

    def test_missing_run_classification_is_not_inferred_from_health_intensity(self):
        p = render_fixture()
        entry = p['sessions'][2]['modules'][0]['items'][0]
        entry.pop('run_intensity')
        entry['aerobic_intensity'] = 'moderate'
        entry['aerobic_minutes'] = 20
        body = render(p, 'week', week=1)
        self.assertIn('轻松0分钟（占比未核定）', body)
        self.assertIn('未分类20分钟（占比未核定）', body)
        self.assertNotIn('轻松20分钟（100%）', body)

    def test_estimated_run_distance_is_labelled_estimate(self):
        p = render_fixture()
        p['sessions'][2]['modules'][0]['items'][0]['dose']['distance_estimate_m'] = 3000
        p['sessions'][2]['modules'][0]['items'][0]['dose']['distance_estimate_basis'] = '近期同等轻松努力20分钟约跑3公里'
        body = render(p, 'session', session='S3')
        self.assertIn('总跑动20分钟；预计总跑量3公里', body)
        self.assertNotIn('距离未估算', body)

    def test_swim_total_includes_warmup_main_and_cooldown(self):
        p = render_fixture()
        session = p['sessions'][2]
        session['kind'] = 'swim'
        p['weeks'][0]['module_summary'] = '力量2次，泳1次'
        entries = []
        for sets, distance in [(1, 100), (2, 200), (1, 100)]:
            entry = item('swim_easy', sets=sets, reps=None, work=distance * 1.2, allocated=sets * distance / 50)
            entry['dose']['distance_m'] = distance
            entry['dose']['rest_seconds'] = 0
            entry['dose']['load']['target_rpe'] = None
            entry['dose']['load']['description'] = '舒适持续游，保持划水和呼吸'
            entry['dose']['load']['execution_target'] = '舒适持续游，保持划水和呼吸'
            entry['endurance_role'] = 'swim'
            entries.append(entry)
        session['modules'][0]['items'] = entries
        session['duration_minutes'] = session['modules'][0]['duration_minutes'] = 12
        p['profile']['pool'] = {'length_m': 25}
        body = render(p, 'week', week=1)
        self.assertIn('总泳距600米', body)
        self.assertIn('计划周总量：总泳距600米', body)


if __name__ == '__main__':
    unittest.main()
