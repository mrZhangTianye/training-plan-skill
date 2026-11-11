"""Fixed ball activities constrain the calendar; they are not training prescriptions."""
import datetime as dt

def _minutes(clock):
    if clock is None: return None
    h,m=map(int,clock.split(':'));return 60*h+m

def check(plan):
    errors,reminders,unverified=[],[],[]
    balls=plan.get('ball_days',[]);start=dt.date.fromisoformat(plan['start_date'])
    scope=plan.get('scope',{}).get('dates')
    allowed=set(scope) if scope else {(start+dt.timedelta(days=i)).isoformat() for i in range(7*plan['duration_weeks'])}
    ids=[b['id'] for b in balls]
    if len(set(ids))!=len(ids):errors.append('ball_days: duplicate id')
    existing={s['id'] for s in plan['sessions']} | {g['id'] for g in plan['objectives']} | {b['id'] for b in plan['blocks']} | {plan['id'],plan['profile']['id']}
    if set(ids) & existing:errors.append('ball_days: ID collides with an existing plan entity')
    rests={d for w in plan['weeks'] for d in w['rest_days']}
    for b in balls:
        if b.get('duration_minutes') is not None and b['duration_minutes'] <= 0: errors.append(b['id']+': ball duration must be positive when supplied')
        if not b['sport'].strip() or not b['source'].strip():errors.append(b['id']+': ball sport/source must not be blank')
        try:date=dt.date.fromisoformat(b['date'])
        except ValueError:errors.append(b['id']+': invalid ball date');continue
        week=(date-start).days//7+1
        prefix='week '+str(week)+': '+b['id']
        if b['date'] not in allowed:errors.append(prefix+': ball date outside plan scope')
        if b['date'] in rests:errors.append(prefix+': fixed ball date conflicts with rest day')
        if b.get('start_time') is not None and b.get('duration_minutes') is not None and _minutes(b['start_time'])+b['duration_minutes']>1440:
            errors.append(prefix+': cross-midnight ball activity requires explicit split dates; not supported as a single-day interval')
        if b.get('duration_minutes') is None:reminders.append(prefix+': ball duration unknown; total activity minutes unverified, do not invent or require duration')
        for s in plan['sessions']:
            delta=(dt.date.fromisoformat(s['date'])-date).days
            if delta in (-2,-1,1):
                reminders.append(prefix+'/'+s['id']+': near ball day; review existing before-48h/after-24h recovery guidance using actual times and load; calendar dates alone do not prove exact hours')
            if delta:continue
            a,z=_minutes(b.get('start_time')),_minutes(s.get('start_time'))
            duration=b.get('duration_minutes')
            if a is None or z is None or duration is None:
                unverified.append(prefix+'/'+s['id']+': same-day timing/recovery unverified; missing ball timing is not an invitation to fabricate duration')
            elif max(a,z)<min(a+duration,z+s['duration_minutes']):
                errors.append(prefix+'/'+s['id']+': explicit time overlap')
            else:
                reminders.append(prefix+'/'+s['id']+': same-day non-overlap only; review load, order and recovery, no universal 2h/6h threshold or safety certification')
                reviewed = any(r.get('topic')=='load_recovery' and r.get('outcome') in ('pass','tradeoff') and {b['id'],s['id']} <= set(r.get('checked_ids',[])) and str(r.get('reason','')).strip() for r in plan.get('design_review',[]))
                if not reviewed: unverified.append(prefix+'/'+s['id']+': same-day load/recovery design review must explicitly cover both activity IDs; non-overlap alone is not readiness')
    # Two fixed activities cannot silently overlap either.
    for i,a in enumerate(balls):
        for b in balls[i+1:]:
            if a['date']!=b['date']:continue
            x,y=_minutes(a.get('start_time')),_minutes(b.get('start_time'))
            if x is not None and y is not None and a.get('duration_minutes') is not None and b.get('duration_minutes') is not None:
                if max(x,y)<min(x+a['duration_minutes'],y+b['duration_minutes']):errors.append(a['id']+'/'+b['id']+': fixed ball activities overlap')
            else:
                week=(dt.date.fromisoformat(a['date'])-start).days//7+1
                unverified.append('week '+str(week)+': '+a['id']+'/'+b['id']+': fixed ball timing unverified')
    return {'errors':errors,'reminders':reminders,'unverified':unverified,'dates':sorted({b['date'] for b in balls})}

def replacement_errors(before,after,replacements):
    """Review explicit {session_id,ball_day_id,source} proposals; never mutate either snapshot."""
    errors=[];old={s['id']:s for s in before['sessions']};new={s['id']:s for s in after['sessions']};balls={b['id']:b for b in after.get('ball_days',[])}
    protected={e.get('session_id') for e in before.get('evidence',[]) if e.get('source_type')=='performance' or bool(e.get('actual_sets'))}
    for s in before['sessions']:
        if s.get('status')=='completed' or s['id'] in protected:
            if new.get(s['id'])!=s:errors.append(s['id']+': executed history must remain unchanged')
    for e in before.get('evidence',[]):
        if (e.get('source_type')=='performance' or bool(e.get('actual_sets'))) and e not in after.get('evidence',[]):errors.append(e['id']+': performance evidence must be retained')
    seen=set()
    for r in replacements:
        sid=r.get('session_id');bid=r.get('ball_day_id');s=old.get(sid);b=balls.get(bid)
        if sid in seen:errors.append(str(sid)+': duplicate replacement')
        seen.add(sid)
        if not s or not b or not str(r.get('source','')).strip():errors.append(str(sid)+': replacement requires existing session, ball activity and source');continue
        if s.get('status')!='planned' or sid in protected:errors.append(sid+': only unperformed planned session may be replaced')
        if s['date']!=b['date']:errors.append(sid+': replacement ball date differs')
        if sid in new:errors.append(sid+': replaced session remains in candidate; retain original snapshot, do not hide with displaced_by')
    removed=set(old)-set(new)
    if removed-seen:errors.append('removed sessions need explicit replacement review: '+','.join(sorted(removed-seen)))
    return errors
