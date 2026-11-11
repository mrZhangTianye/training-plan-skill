# -*- coding: utf-8 -*-
"""周文档版式回归：热身五段合并成行、配对／超级组字母序号、要点不复述技术提示。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import library
from render_weekly_log import name_of, session_rows
from test_workflows import fixture


class WeeklyLayoutTest(unittest.TestCase):
    def setUp(self):
        self.plan = fixture()
        self.assets = library()
        self.session = self.plan['sessions'][0]

    def module(self):
        return self.session['modules'][0]

    def test_group_rows_share_number_with_letters(self):
        rows = session_rows(self.session, self.assets)
        self.assertEqual([r[0] for r in rows], ['1-A', '1-B'])

    def test_merge_sections_collapse_to_one_row(self):
        m = self.module()
        m['title'] = '激活'
        m.pop('group_label', None)
        m['duration_minutes'] = 6
        rows = session_rows(self.session, self.assets)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], '1')
        self.assertEqual(rows[0][2], '6分钟')
        self.assertEqual(rows[0][3], '激活')
        self.assertEqual(len(rows[0][1].split('｜')), 2)
        self.assertNotIn(' · ', rows[0][1])

    def test_merged_row_merges_feedback_by_name(self):
        m = self.module()
        m['title'] = '拉伸循环'
        m.pop('group_label', None)
        first = name_of(m['items'][0], self.assets)
        second = name_of(m['items'][1], self.assets)
        feedback = {(self.session['id'], first): '完成',
                    (self.session['id'], second): '忘了 跳过了'}
        rows = session_rows(self.session, self.assets, feedback)
        self.assertEqual(rows[0][4], '完成；%s：忘了 跳过了' % second)

    def test_group_points_keep_rest_only(self):
        m = self.module()
        m['title'] = '力量配对'
        m['items'][0]['dose']['rest_seconds'] = 150
        m['items'][1]['dose']['rest_seconds'] = 0
        rows = session_rows(self.session, self.assets)
        self.assertNotIn('轮内转项', rows[0][3])
        self.assertIn('同动作恢复2.5分', rows[0][3])
        self.assertNotIn('同动作恢复', rows[1][3])  # 转项行 rest=0：不写恢复，不是抹平成 2.5 分

    def test_plyo_points_keep_venue_and_rest_only(self):
        m = self.module()
        m['title'] = '增强式'
        m.pop('group_label', None)
        m['items'][0]['dose']['notes'] = '平台20厘米；每次落地停稳2秒；走回与走上平台是行进接触，单独计，不混入6次目标落地'
        m['items'][0]['dose']['rest_seconds'] = 120
        rows = session_rows(self.session, self.assets)
        self.assertIn('平台20厘米', rows[0][3])
        self.assertIn('组间2分', rows[0][3])
        self.assertNotIn('行进接触', rows[0][3])


if __name__ == '__main__':
    unittest.main()
