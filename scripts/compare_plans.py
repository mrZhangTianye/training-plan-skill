# -*- coding: utf-8 -*-
"""Compare snapshots by stable IDs; never silently rewrite training history."""
import argparse
import json
import sys
from common import ROOT, read_json, write_json, fingerprint, schema_errors
from validate_plan import validate
from ball_constraints import replacement_errors

def keyed(items):
    if not items or not all(isinstance(v,dict) for v in items):return None
    for key in ('id','number'):
        if all(key in v for v in items) and len({v[key] for v in items})==len(items):return {str(v[key]):v for v in items}
    return None

def difference(a,b,path=''):
    if a==b:return []
    if isinstance(a,list) and isinstance(b,list):
        ka,kb=keyed(a),keyed(b)
        if ka is not None and kb is not None:return difference(ka,kb,path)
    if isinstance(a,dict) and isinstance(b,dict):
        rows=[]
        for k in sorted(set(a)|set(b)):
            address=path+'/'+str(k).replace('~','~0').replace('/','~1')
            if k not in a:rows.append({'path':address,'operation':'add','before':None,'after':b[k]})
            elif k not in b:rows.append({'path':address,'operation':'remove','before':a[k],'after':None})
            else:rows+=difference(a[k],b[k],address)
        return rows
    return [{'path':path or '/','operation':'replace','before':a,'after':b}]

def compare(a,b,reason,evidence_ids,association,allow_history=False,ball_replacements=None):
    for p in (a,b):
        errors=validate(p)['errors']
        if errors:raise ValueError('; '.join(errors))
    if a['id']!=b['id'] or b['version']!=a['version']+1:raise ValueError('same plan id and exactly next version required')
    current={s['id']:s for s in b['sessions']}
    execution=[e for e in a.get('evidence',[]) if e.get('source_type')=='performance' or e.get('actual_sets')]
    protected={e.get('session_id') for e in execution}
    for e in execution:
        if e not in b.get('evidence',[]):raise ValueError('execution evidence must remain unchanged: '+e['id'])
    for session in a['sessions']:
        if session['id'] in protected and current.get(session['id'])!=session:
            raise ValueError('execution-backed history must remain unchanged: '+session['id'])
        if session['status']=='completed' and session['id'] not in current:
            raise ValueError('completed history cannot be deleted: '+session['id'])
    removed={session['id'] for session in a['sessions']}-set(current)
    if ball_replacements is not None or (removed and b.get('ball_days') != a.get('ball_days')):
        if ball_replacements is None:raise ValueError('ball replacement requires explicit --ball-replacements review')
        problems=replacement_errors(a,b,ball_replacements)
        if problems:raise ValueError('; '.join(problems))
    for s in a['sessions']:
        if s['status']=='completed' and current.get(s['id'])!=s and not allow_history:raise ValueError('completed history changed: '+s['id'])
    known={e['id'] for e in b['evidence']}
    if not set(evidence_ids)<=known:raise ValueError('unknown evidence id')
    changes=difference(a,b)
    affected=sorted({c['path'].split('/')[2] for c in changes if c['path'].startswith(('/sessions/','/weeks/','/blocks/','/objectives/')) and len(c['path'].split('/'))>2})
    result={'schema_version':b['schema_version'],'plan_id':a['id'],'before_version':a['version'],'after_version':b['version'],'before_hash':fingerprint(a),'after_hash':fingerprint(b),'changes':changes,'affected_entities':affected,'reason':reason,'evidence_ids':evidence_ids,'association_review':association}
    errors=schema_errors(result,read_json(ROOT/'schemas/change-set.schema.json'))
    if errors:raise ValueError('; '.join(errors))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');p.add_argument('--output',required=True);p.add_argument('--reason',required=True);p.add_argument('--association-review',required=True);p.add_argument('--evidence',action='append',default=[]);p.add_argument('--allow-history-correction',action='store_true');p.add_argument('--ball-replacements',help='JSON array of explicit session_id/ball_day_id/source proposals');a=p.parse_args()
    try:
        replacements=read_json(a.ball_replacements) if a.ball_replacements else None
        if replacements is not None and not isinstance(replacements,list):raise ValueError('ball replacements must be an array')
        if replacements is not None and a.allow_history_correction:raise ValueError('ball replacement cannot use history correction override')
        result=compare(read_json(a.before),read_json(a.after),a.reason,a.evidence,a.association_review,a.allow_history_correction,replacements)
        write_json(a.output,result);print(a.output);return 0
    except (ValueError,OSError,KeyError) as e:print(str(e),file=sys.stderr);return 1


def compare_ball_replacement(before, after, replacements, reason, evidence_ids, association):
    """Ball replacement never uses the separate manual history-correction exception."""
    errors = replacement_errors(before, after, replacements)
    if errors: raise ValueError('; '.join(errors))
    return compare(before, after, reason, evidence_ids, association, allow_history=False,ball_replacements=replacements)

if __name__=='__main__':sys.exit(main())
