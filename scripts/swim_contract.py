"""Task-specific swimming checks; never infer skill or medical clearance."""
from common import ROOT, read_json, schema_errors


def check(plan, assets):
    errors, missing = [], []
    profile = plan.get('profile', {})
    ready = profile.get('swim_task_readiness', {})
    for session in plan.get('sessions', []):
        items = [x for m in session['modules'] for x in m['items']]
        selected = {x['unit_id'] for x in items}
        scoped = [(x['unit_id'], x) for x in items if assets.get(x['unit_id'], {}).get('swim_task_mode')]
        focus = session.get('swim_focus')
        if focus and focus['unit_id'] not in selected:
            errors.append(session['id'] + ': swim_focus must refer to a selected task')
        elif focus and assets.get(focus['unit_id'], {}).get('category') != 'swim':
            errors.append(session['id'] + ': swim_focus must refer to a swimming task')
        if scoped and not focus:
            missing.append(session['id'] + ': swimming task needs one explicit swim_focus goal and observation')
        for uid, item in scoped:
            address = session['id'] + '/' + uid
            asset, dose = assets[uid], item['dose']
            mode = asset['swim_task_mode']
            if mode == 'reference_only':
                errors.append(address + ': reference-only drill has no supported prescription interface')
                continue
            state = ready.get(uid, {})
            if state.get('status') != 'ready' or not state.get('basis', '').strip():
                missing.append(address + ': confirm exact task prerequisites; unknown is not ready')
            if mode == 'stationary':
                if dose.get('distance_m') is not None:
                    errors.append(address + ': stationary practice must not invent swimming distance')
                if not dose.get('duration_minutes'):
                    errors.append(address + ': stationary practice needs positive practice time per set')
                if dose.get('recovery_type') == 'sendoff':
                    errors.append(address + ': stationary practice uses rest, not pool sendoff')
                if item.get('aerobic_minutes', 0) > 0 or item.get('aerobic_intensity') in ('moderate', 'vigorous'):
                    errors.append(address + ': stationary technique practice is not aerobic swimming work')
            else:
                distance = dose.get('distance_m')
                if dose.get('reps') is not None:
                    errors.append(address + ': use sets for swim repetitions, not ambiguous nested reps')
                maximum = state.get('continuous_distance_m')
                if maximum is None or maximum <= 0:
                    missing.append(address + ': needs known continuous distance for this exact task')
                elif distance is not None and distance > maximum:
                    errors.append(address + ': prescribed distance exceeds this task continuous ability')
                if not distance:
                    errors.append(address + ': moving drill needs positive measured prescription distance')
    return errors, list(dict.fromkeys(missing))


def feedback_errors(value, plan=None, assets=None):
    errors = schema_errors(value, read_json(ROOT / 'schemas/swim-feedback.schema.json'))
    if errors:
        return errors
    if assets is not None:
        asset = assets.get(value['unit_id'], {})
        if asset.get('category') != 'swim':
            errors.append('feedback unit must be a registered swimming task')
        if asset.get('swim_task_mode') == 'stationary' and value.get('distance_m') is not None:
            errors.append('stationary feedback must not invent swimming distance')
    if plan is not None:
        session = next((s for s in plan.get('sessions', []) if s['id'] == value['session_id']), None)
        if session is None:
            errors.append('feedback session not found')
        elif value['unit_id'] not in {x['unit_id'] for m in session['modules'] for x in m['items']}:
            errors.append('feedback task was not prescribed in this session')
    return errors
