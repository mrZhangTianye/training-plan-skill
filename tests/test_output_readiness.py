"""出表就绪与跑量核算的验收测试（F1／F2／F5）。

三条边界写死在这里：
1. 设计前提缺失（动作能不能做、时间够不够）按周拦出表；执行反馈缺失（次晨反应、本周 RPE、
   实际完成量）不拦——这些只有课跑完才存在。
2. 纯时长跑课不许因为没给距离就整段跳过：距离口径标未核定，另按时长口径核算同一占比。
3. 整包导出的周课表与 render_weekly_log 的周文档同源，含表现/反馈列。
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from validate_plan import validate, week_scope  # noqa: E402
from export_plan import export  # noqa: E402
from render_weekly_log import week_doc  # noqa: E402

EXAMPLE = os.path.join(ROOT, 'assets', 'examples', 'plan.json')


def example():
    return json.load(io.open(EXAMPLE, encoding='utf-8'))


def run_render(plan_path, out_dir, week=1, draft=False):
    cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'render_weekly_log.py'),
           plan_path, '--week', str(week), '--output-dir', out_dir]
    if draft:
        cmd.append('--draft')
    return subprocess.run(cmd, capture_output=True, text=True)


class WeekScopeTest(unittest.TestCase):
    """缺口要能定位到周；定位不到的才算计划层面。"""

    def setUp(self):
        p = example()
        self.date_week = {s['date']: s['week_number'] for s in p['sessions']}
        self.sessions = {s['id']: s for s in p['sessions']}

    def test_session_id_prefix_scopes_to_its_week(self):
        self.assertEqual(9, week_scope('W09-F1/rdl: mastery unknown', self.date_week, self.sessions))

    def test_date_prefix_scopes_to_containing_week(self):
        date = sorted(self.date_week)[0]
        self.assertEqual(self.date_week[date],
                         week_scope(date + ': available daily time unknown', self.date_week, self.sessions))

    def test_plan_level_gap_has_no_week(self):
        self.assertIsNone(week_scope('缺少对应训练刺激：有氧基础', self.date_week, self.sessions))


class DesignGapBlocksTest(unittest.TestCase):
    """设计前提没定 → 拦住出表；换成条件充分的替代动作则不拦。"""

    def test_unknown_mastery_blocks_weeks_and_weekly_doc(self):
        p = example()
        p['intended_use'] = 'actual'
        p['status'] = 'draft'
        p['profile']['mastery']['split_squat'] = 'unknown'
        for w in p['weeks']:
            w['detail_status'] = 'scheduled'
        result = validate(p)
        self.assertEqual([], result['errors'])
        self.assertTrue(result['blocked_weeks'], '掌握状态未知必须落到具体周')
        self.assertEqual([], result['ready_weeks'], '有设计缺口的周不能算就绪')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'plan.json')
            json.dump(p, io.open(path, 'w', encoding='utf-8'), ensure_ascii=False)
            out = os.path.join(d, 'out')
            proc = run_render(path, out)
            self.assertNotEqual(0, proc.returncode, '设计前提未定不能出正式周文档')
            self.assertIn('设计前提还没定', proc.stderr)
            self.assertFalse(os.path.exists(os.path.join(out, '第1周训练计划.md')))
            proc = run_render(path, out, draft=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            body = io.open(os.path.join(out, '第1周训练计划.md'), encoding='utf-8').read()
            self.assertTrue(body.startswith('> **草案**'), '草案要在成品文件里可辨识')

    def test_future_week_gap_does_not_seal_current_week(self):
        """只有 W09 的动作没定，W01 仍可出表。"""
        p = example()
        p['intended_use'] = 'actual'
        p['status'] = 'draft'
        for w in p['weeks']:
            w['detail_status'] = 'scheduled'
        target = next(s for s in p['sessions'] if s['id'] == 'W09-F1')
        for m in target['modules']:
            for item in m['items']:
                if item['unit_id'] == 'pallof_press':
                    item['dose']['load']['target_rpe'] = None
                    item['dose']['load'].pop('execution_target', None)
        result = validate(p)
        self.assertEqual([], result['errors'])
        self.assertIn(9, result['blocked_weeks'])
        self.assertNotIn(1, result['blocked_weeks'], '未来周的缺口不应封住当前周')
        self.assertIn(1, result['ready_weeks'])

    def test_execution_feedback_absence_does_not_block(self):
        """没有任何次晨反应／本周 RPE／实际完成量，不影响出表。"""
        p = example()
        p['intended_use'] = 'actual'
        p['status'] = 'draft'
        p['evidence'] = [e for e in p.get('evidence', []) if e.get('source_type') != 'performance']
        for w in p['weeks']:
            w['detail_status'] = 'scheduled'
        result = validate(p)
        self.assertEqual([], result['blocked_weeks'])
        self.assertEqual([], result['global_gaps'])
        self.assertEqual(list(range(1, 13)), result['ready_weeks'])


class TimeOnlyRunCheckTest(unittest.TestCase):
    """纯时长处方照样要核算，不能静默跳过。"""

    def test_example_reports_distance_basis_unverified(self):
        result = validate(example())
        self.assertEqual([], result['errors'])
        self.assertTrue([r for r in result['review_items'] if '未核定' in r and '时长' in r],
                        '只给时长的跑课要标距离口径未核定，不能当成已通过')

    def test_overtop_run_is_caught_by_minutes(self):
        p = example()
        session = next(s for s in p['sessions'] if s['id'] == 'W05-R1')
        main = next(m for m in session['modules'] if m['title'] == '主跑')
        item = main['items'][0]
        item['duration_minutes'] = 120
        item['dose']['duration_minutes'] = 120
        item['aerobic_minutes'] = 120
        main['duration_minutes'] = 120
        session['duration_minutes'] = 90 + 120
        p['profile']['available_minutes']['4'] = 300
        result = validate(p)
        hits = [e for e in result['errors'] if '单次最长跑' in e and '时长口径' in e]
        self.assertTrue(hits, '只给时长的周也要按最长跑占比拦，实际：%s' % result['errors'])


class ExportParityTest(unittest.TestCase):
    """整包导出的周课表就是记录式周文档，含表现列。"""

    def test_exported_week_matches_weekly_log(self):
        with tempfile.TemporaryDirectory() as d:
            names = export(example(), os.path.join(d, 'exp'), draft=True)
            self.assertIn('第3周训练计划.md', names)
            self.assertFalse([n for n in names if n.endswith('周课表.md')], '不应再产出另一形态的周课表')
            exported = io.open(os.path.join(d, 'exp', '第3周训练计划.md'), encoding='utf-8').read()
            self.assertIn('表现', exported)
            proc = run_render(EXAMPLE, os.path.join(d, 'week'), week=3)
            self.assertEqual(0, proc.returncode, proc.stderr)
            single = io.open(os.path.join(d, 'week', '第3周训练计划.md'), encoding='utf-8').read()
            self.assertTrue(exported.endswith(single), '整包与单独导出的周文档必须同源同内容')


class ExampleExecutableTest(unittest.TestCase):
    """完整示例要真的能照排：整课耗时等于各模块之和，且不超过当日可用时间。"""

    def test_session_minutes_add_up_and_fit_budget(self):
        import datetime as dt
        p = example()
        for s in p['sessions']:
            total = sum(m['duration_minutes'] for m in s['modules'])
            # 时长由剂量算出并保留两位小数，二进制浮点求和会带 1e-14 级噪声，不比字面相等
            self.assertAlmostEqual(s['duration_minutes'], total, delta=0.011,
                                   msg='%s 整课耗时与模块之和不一致' % s['id'])
            budget = p['profile']['available_minutes'][str(dt.date.fromisoformat(s['date']).weekday())]
            self.assertLessEqual(s['duration_minutes'], budget,
                                 '%s 超出当日可用时间 %s 分钟' % (s['id'], budget))


if __name__ == '__main__':
    unittest.main()
