"""Export one overview and weekly sheets from a validated snapshot.

周课表只有一个形态：与 render_weekly_log.py 的周文档同源（记录式，含表现/反馈列）。
整包导出不再另走一份没有表现列的简表，避免同一份"周课表"两种内容。
"""
import argparse
import sys
from pathlib import Path
from common import read_json, library
from validate_plan import validate
from render_plan import render
from render_weekly_log import week_doc, load_feedback

DRAFT_NOTE = '> **草案**：本文件含未定项（未排期或设计前提未确认），不是正式课表，不要照此执行。\n\n'

def export(p, out, draft=False, plan_path=None):
    check=validate(p)
    if check['errors']: raise ValueError('; '.join(check['errors']))
    if not draft and (not check['ready_to_render_executable'] or any(w['detail_status']!='scheduled' for w in p['weeks'])):
        raise ValueError('Complete executable export requires every week to be expanded; otherwise use --draft')
    assets=library(); feedback=load_feedback(plan_path)[0] if plan_path else {}
    contents={}
    if p['duration_weeks']>1:
        name='阶段总览.md' if p['duration_weeks']==4 else '计划总览.md'
        contents[name]=render(p,'overall',allow_gaps=draft)
    for w in sorted(p['weeks'],key=lambda x:x['number']):
        doc=week_doc(p,w['number'],assets,feedback=feedback)
        if doc is None:
            continue
        name = (p['start_date'] + '单日训练计划.md') if p.get('scope', {}).get('window') == 'day' else f'第{w["number"]}周训练计划.md'
        contents[name]=(DRAFT_NOTE if draft else '')+doc
    out=Path(out)
    for name in contents:
        if (out/name).exists(): raise ValueError(f'Output already exists: {out/name}; choose a new version directory')
    out.mkdir(parents=True,exist_ok=True)
    for name,content in contents.items(): (out/name).write_text(content,encoding='utf-8')
    return list(contents)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('plan');parser.add_argument('--output-dir',required=True);parser.add_argument('--draft',action='store_true');args=parser.parse_args()
    try:
        names=export(read_json(args.plan),args.output_dir,args.draft,plan_path=args.plan)
        print(f'Exported {len(names)} Markdown files');return 0
    except (ValueError,OSError,KeyError) as e: print(str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
