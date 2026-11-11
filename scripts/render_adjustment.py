# -*- coding: utf-8 -*-
"""Render a change report only when its hashes and changes match the snapshots."""
import argparse
import json
import sys
from pathlib import Path
from string import Template
from common import ROOT, read_json, schema_errors, fingerprint
from compare_plans import difference
from render_plan import text, table, session_body
from validate_plan import validate
from common import library

def render(before,after,changes):
    errors=schema_errors(changes,read_json(ROOT/'schemas/change-set.schema.json'))
    if errors:raise ValueError('; '.join(errors))
    if changes['before_hash']!=fingerprint(before) or changes['after_hash']!=fingerprint(after):raise ValueError('change report hashes do not match snapshots')
    if changes['changes']!=difference(before,after):raise ValueError('change report does not match actual changes')
    if changes['plan_id']!=before['id'] or before['id']!=after['id'] or changes['before_version']!=before['version'] or changes['after_version']!=after['version'] or after['version']!=before['version']+1:raise ValueError('change report identity/version mismatch')
    for p in [before,after]:
        if validate(p)['errors']:raise ValueError('invalid plan snapshot')
    previous={s['id']:s for s in before['sessions']};changed=[s for s in after['sessions'] if previous.get(s['id'])!=s]
    body='调整依据：'+text(changes['reason'])+'\n\n关联分析：'+text(changes['association_review'])+'\n\n'
    body+='实际发生变化的实体：'+text('、'.join(changes['affected_entities']) or '无训练实体变化')+'。\n\n'
    rows=[]
    for s in changed:
        old=previous.get(s['id']);rows.append([s['id'],s['title'],'新建' if old is None else f'{old["duration_minutes"]:g}分钟',f'{s["duration_minutes"]:g}分钟',s['purpose']])
    if rows:body+=table(['课表','训练','原用时','新用时','调整后的目的'],rows)
    body+='\n## 用户提供的内容\n\n'
    records={e['id']:e for e in after['evidence']}
    for eid in changes['evidence_ids']:
        if eid not in records:raise ValueError('unknown evidence id')
        body+='- '+text(records[eid]['raw'])+'\n'
    if not changes['evidence_ids']:body+='未关联结构化证据；直接修改要求见调整依据。\n'
    body+='\n## 更新后的训练\n\n'
    for s in changed:body+='### '+text(s['title'])+'\n\n'+session_body(s,library())+'\n\n'
    removed=[s for s in before['sessions'] if s['id'] not in {v['id'] for v in after['sessions']}]
    for s in removed:body+='已取消：'+text(s['title'])+'（'+s['date']+'）。\n\n'
    body+='\n完整字段差异保存在对应changes.json，包含上层结构、证据及版本字段。报告不替代完整差异文件。\n'
    fields={'title':'训练调整结果','status':'展示样稿，虚构用户，非正式处方' if after['intended_use']=='demo' else '执行版' if after['status']=='executable' else '草案','version':f'{before["version"]} → {after["version"]}','body':body}
    return Template((ROOT/'assets/templates/adjustment.md').read_text()).substitute(fields)

def main():
    p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');p.add_argument('changes');p.add_argument('--output',required=True);a=p.parse_args()
    try:
        content=render(read_json(a.before),read_json(a.after),read_json(a.changes));out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(content);print(out);return 0
    except (ValueError,OSError,KeyError) as e:print(str(e),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
