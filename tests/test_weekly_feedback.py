# -*- coding: utf-8 -*-
"""「表现」回填合并：必须按课次匹配，且重渲染不得把用户手写记录清空。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import library
from render_weekly_log import load_feedback, name_of, week_doc
from test_workflows import fixture


class WeeklyFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.plan = fixture()
        self.assets = library()
        self.week = self.plan['weeks'][0]['number']
        self.first = self.plan['sessions'][0]
        self.second = self.plan['sessions'][1]
        self.name = name_of(self.first['modules'][0]['items'][0], self.assets)

    def test_fills_target_row(self):
        doc = week_doc(self.plan, self.week, self.assets,
                       feedback={(self.first['id'], self.name): 'SENTINEL-A'})
        self.assertIn('SENTINEL-A', doc)

    def test_no_cross_session_leak(self):
        # 两课有同名动作行：只给第一课填，文档里必须只出现一次
        doc = week_doc(self.plan, self.week, self.assets,
                       feedback={(self.first['id'], self.name): 'SENTINEL-B'})
        self.assertEqual(doc.count('| ' + self.name + ' |'), 2)
        self.assertEqual(doc.count('SENTINEL-B'), 1)

    def test_blank_render_is_default(self):
        doc = week_doc(self.plan, self.week, self.assets)
        self.assertIn('| 表现 |', doc.replace('  |', ' |'))

    def test_entry_without_session_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / '表现回填.json'
            path.write_text(json.dumps({'entries': [
                {'当前动作名': self.name, '表现': 'NO-SESSION'},
                {'课': self.first['id'], '当前动作名': self.name, '表现': 'WITH-SESSION'},
            ]}, ensure_ascii=False), encoding='utf-8')
            fb, _ = load_feedback('plan.json', str(path))
        self.assertNotIn((None, self.name), fb)
        self.assertEqual(fb[(self.first['id'], self.name)], 'WITH-SESSION')

    def test_missing_file_returns_empty(self):
        fb, path = load_feedback('/nonexistent/plan.json')
        self.assertEqual(fb, {})
        self.assertTrue(path.endswith('表现回填.json'))


if __name__ == '__main__':
    unittest.main()
