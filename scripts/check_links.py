# -*- coding: utf-8 -*-
"""跨文件链接与锚点检查。

现有检查只查文件在不在，抓不到「标题改名、链接静默失效」这一类。
这里连锚点一起查：`foo.md#某标题` 必须在目标文件里存在同名标题。

行内代码与围栏代码块里的链接写法是示例，不是真链接，先剥掉再查。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FENCE = re.compile(r'```.*?```', re.S)
INLINE = re.compile(r'`[^`\n]+`')
LINK = re.compile(r'\]\(([^)\s]+)\)')


def _norm(heading):
    """GitHub 风格锚点：去标点、空格转连字符。"""
    return re.sub(r'[^\w\u4e00-\u9fff\- ]', '', heading).strip().replace(' ', '-')


def _headings(path):
    text = io.open(path, encoding='utf-8').read()
    return {_norm(h.strip()) for h in re.findall(r'^#{1,6}\s+(.+)$', text, re.M)}


def check(root=ROOT):
    errors, total = [], 0
    for dirpath, _, files in os.walk(root):
        for name in files:
            if not name.endswith('.md'):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            text = INLINE.sub('', FENCE.sub('', io.open(path, encoding='utf-8').read()))
            for target in LINK.findall(text):
                if target.startswith(('http://', 'https://', 'mailto:')):
                    continue
                total += 1
                file_part, _, anchor = target.partition('#')
                if not file_part:
                    continue
                dest = os.path.normpath(os.path.join(dirpath, file_part))
                if not os.path.exists(dest):
                    errors.append(rel + ' → ' + target + '：目标文件不存在')
                elif anchor and anchor not in _headings(dest):
                    errors.append(rel + ' → ' + target + '：目标文件里没有这个标题')
    return total, errors


if __name__ == '__main__':
    total, errors = check()
    print('检查链接 %d 条，问题 %d 条' % (total, len(errors)))
    for e in errors:
        print('  ✗ ' + e)
    sys.exit(1 if errors else 0)
