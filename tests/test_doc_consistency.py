# -*- coding: utf-8 -*-
"""文档—脚本数字一致性：同一事实在多处出现时，数字必须一致。

前几轮的漂移（30%/35%/40% 分叉、13/14 段、SKILL 说会查脚本没查）都出在
「同一规则写在多个文件」。这个文件不合并副本，只锁住副本之间的数字。
"""
import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


class DocConsistencyTest(unittest.TestCase):

    def test_long_run_ratio_matches_code(self):
        """跑量分档：文档三处必须与 design_checks.py 的分档一致。"""
        src = read('scripts/design_checks.py')
        m = re.search(r'cap = \{(\d+): ([\d.]+), (\d+): ([\d.]+), (\d+): ([\d.]+)\}', src)
        self.assertIsNotNone(m, 'design_checks.py 里找不到分档常量')
        caps = {int(m.group(1)): int(round(float(m.group(2)) * 100)),
                int(m.group(3)): int(round(float(m.group(4)) * 100)),
                int(m.group(5)): int(round(float(m.group(6)) * 100))}
        m2 = re.search(r'cap = min\(cap, ([\d.]+)\)', src)
        self.assertIsNotNone(m2, '找不到距离上限')
        cap_abs = int(round(float(m2.group(1)) * 100))

        for rel in ('SKILL.md', 'references/run-programming.md'):
            text = read(rel)
            for runs, pct in caps.items():
                pat = str(runs) + r'\s*[＋+]?\s*次[^%\n]{0,40}?' + str(pct) + '%'
                self.assertRegex(text, pat,
                                 rel + ' 缺「' + str(runs) + ' 次 → ' + str(pct) + '%」')
            self.assertIn(str(cap_abs) + '%', text, rel + ' 缺距离上限 ' + str(cap_abs) + '%')

    def test_skeleton_segment_count_consistent(self):
        """11 段骨架：凡声明骨架总数的地方必须是 11，且不能出现超过骨架的段数。

        只拦「>11」会漏掉把 11 写成 10 这一类——少一段同样是把骨架排坏。
        序数引用（第 7 段／第 9 段）合法，所以按「骨架总数」的措辞精确匹配，
        不拿全文所有「N 段」一起比。
        """
        SKELETON = 11
        # 「段序固定 N 段」「N 段固定骨架」「N 段骨架」
        TOTAL = re.compile(r'(?:段序固定\s*(\d+)\s*段|(\d+)\s*段固定骨架|(\d+)\s*段骨架)')
        declared = []
        for rel in ('SKILL.md', 'references/two-day-structure.md', 'references/planning.md'):
            text = read(rel)
            for m in TOTAL.finditer(text):
                n = int(next(g for g in m.groups() if g))
                declared.append((rel, n))
            stray = {int(x) for x in re.findall(r'(\d+)\s*段', text)} - set(range(1, SKELETON + 1))
            self.assertFalse(stray, rel + ' 出现超过骨架的段数：' + str(stray))
        self.assertTrue(declared, '一处骨架总数都没找到，匹配式可能失效')
        wrong = [(rel, n) for rel, n in declared if n != SKELETON]
        self.assertFalse(wrong, '骨架总数写错：' + str(wrong))

    def test_supported_lengths_match_validator(self):
        """支持的计划长度：SKILL 声明、代码白名单、报错文案三处集合相等（双向）。

        只断言「代码有 → 文档里出现过这个字符」会被同行的其它数字蒙过去
        （「8周＝两个完整阶段」里的 8 永远在），必须切出长度清单再比集合。
        """
        src = read('scripts/validate_plan.py')
        block = re.search(r'STANDARD_SPANS\s*=\s*\{(.*?)\n    \}', src, re.S)
        self.assertIsNotNone(block, '找不到 STANDARD_SPANS')
        lengths = {int(x) for x in re.findall(r'^\s*(\d+):', block.group(1), re.M)}

        skill = read('SKILL.md')
        m = re.search(r'支持的计划长度只有([^周]*)周', skill)
        self.assertIsNotNone(m, 'SKILL 里找不到「支持的计划长度只有 … 周」')
        doc = {int(x) for x in re.findall(r'\d+', m.group(1))}
        self.assertEqual(doc, lengths,
                         'SKILL 列出的长度 ' + str(sorted(doc)) + ' 与白名单 ' + str(sorted(lengths)) + ' 不一致')

        err = re.search(r'周不在支持的计划长度内（([^）]+)）', src)
        self.assertIsNotNone(err, '找不到非标准长度的报错文案')
        msg = {int(x) for x in re.findall(r'\d+', err.group(1))}
        self.assertEqual(lengths, msg, '报错文案 ' + str(sorted(msg)) + ' 与白名单不一致')

    def test_cross_file_links_and_anchors_resolve(self):
        """跨文件链接连锚点一起查：改标题忘改链接会静默失效，只查文件在不在抓不到。"""
        import check_links
        total, errors = check_links.check()
        self.assertGreater(total, 0, '一条链接都没扫到，检查逻辑可能失效')
        self.assertEqual(errors, [], '\n'.join(errors))

    def test_progression_paths_carry_the_same_gate(self):
        """加重/加量入口必须挂同一道闸门，且闸门本身四个要素齐全。

        闸门是顺序不是条件集合：安全条件（≤3/10、次晨回落）回答能不能加，
        项目标准（RPE、划数、配速）回答该不该加，后者不得单独放行。
        缺任一要素，受限的人都能在某个出口绕过去。
        """
        lim = read('references/limitations.md')
        for token, why in (
            ('触发式', '闸门必须由症状触发，不能只在登记了限制时生效'),
            ('加密组', '密度类加量（压缩休息/加密组）必须算作加量'),
            ('不得单独放行', '项目标准不能替代安全条件'),
            ('出口', '闸门必须有恢复与止损出口，否则退化成一直不加'),
            ('技术段', '闸门打开期间技术/纠正/激活不减'),
        ):
            self.assertIn(token, lim, '§六 闸门缺要素：' + why)

        prog = read('references/programming.md')
        self.assertIn('六疼痛与负荷的判定310', prog,
                      'programming.md 没引用 §六 闸门')
        self.assertRegex(prog, r'所有[^\n]{0,20}(?:加重|进阶)[^\n]{0,40}(?:先过|为准)',
                         '缺覆盖全文件的加量总闸门')
        bare = []
        for line in prog.split('\n'):
            if not re.search(r'(?:可|允许|就)加重|加重一次|加重并把', line):
                continue
            if any(k in line for k in ('不单独生效', '不加负', '不设', '闸门')):
                continue
            if '3/10' not in line and '六疼痛与负荷的判定310' not in line:
                bare.append(line[:60])
        self.assertEqual(bare, [], '这些加重路径没挂闸门：' + str(bare))

    def test_run_and_swim_progression_reference_the_gate(self):
        """跑与泳的加量入口也要引用同一道闸门。

        跑不许加配速、泳看划数稳，这两条是各项目的合格标准，不是安全条件：
        「划数没涨」不等于「疼 ≤3/10 且次晨回落」。
        """
        gate = '六疼痛与负荷的判定310'
        self.assertIn(gate, read('references/run-programming.md'),
                      'run-programming 的跨阶段抬档没引用闸门')
        self.assertIn(gate, read('references/swim-programming.md'),
                      'swim-programming 的加量入口没引用闸门')
    def test_phase4_holds_volume_but_allows_heavy(self):
        """第 4 阶段：容量课持平、较重课可加，两件事必须分开写。

        合成一句会自相矛盾——同一格既让加又不让加，执行者读不出该不该动重量。
        合格标准还必须区分真适应与保护性抑制：RPE 降而幅度悄悄变小，
        读数一模一样，只看 RPE 会被骗。
        """
        text = read('references/programming.md')
        # 只看阶段表本体；后面的「原书四阶段剂量对照」也有一行 |第4阶段|，
        # 那是原表数据，不是本包的排课规则。
        body = text.split('#### 原书四阶段剂量对照')[0]
        rows = [l for l in body.split('\n') if l.startswith('| 第4阶段 |')]
        self.assertEqual(len(rows), 1, '找不到第 4 阶段那一行')
        row = rows[0]
        self.assertIn('三周持平', row, '容量课没写持平')
        self.assertIn('较重课不受此限', row, '没写较重课的例外')
        self.assertIn('动作质量不降且无新不适', row, '合格标准丢了「质量不降」这一条')
        self.assertIn('不要求三周内 RPE 一定下降', row,
                      '又把 RPE 下降写成合格要求了——巩固段 RPE 不降本来就该算合格')
        self.assertNotIn('是保护性抑制不是适应', row,
                         '又把观察写成诊断了：输出变了给不出病因，本包不下这类结论')
        self.assertNotIn('RPE 自然下降，按「RPE 没到就加重」', row,
                         '容量课那格又写回「RPE 降就加重」了')


if __name__ == '__main__':
    unittest.main()
