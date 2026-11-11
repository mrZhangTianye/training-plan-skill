"""Transparent prescribed-work estimates, with optional independent dose derivation."""


def derived_estimates(item):
    dose = item['dose']
    sides = 2 if dose['per_side'] else 1
    values = {}
    if dose['duration_minutes'] is not None:
        values['duration'] = dose['duration_minutes'] * 60 * sides
    if item.get('tempo_seconds_per_rep') is not None and dose['reps'] is not None:
        values['repetitions'] = dose['reps'] * item['tempo_seconds_per_rep'] * sides
    if item.get('swim_pace_seconds_per_100m') is not None and dose['distance_m'] is not None:
        values['swim_pace'] = dose['distance_m'] / 100 * item['swim_pace_seconds_per_100m'] * sides
    return values


def whole_set_seconds(item):
    values = derived_estimates(item)
    if values:
        return next(iter(values.values()))
    return item.get('work_seconds_per_set')


def check(item):
    errors = []
    dose = item['dose']
    if item.get('tempo_seconds_per_rep') is not None and dose['reps'] is None:
        errors.append('每次节奏估算需要明确重复次数')
    if item.get('swim_pace_seconds_per_100m') is not None and dose['distance_m'] is None:
        errors.append('游速估算需要明确每组距离')
    values = derived_estimates(item)
    declared = item.get('work_seconds_per_set')
    if declared is not None:
        values['declared'] = declared
    if values and max(values.values()) - min(values.values()) > 1:
        errors.append('whole-set work estimate contradicts prescribed timed work: 组工作时间与次数节奏或泳速推导不一致')
    return errors


def summary(p):
    counts = {'derived_items': 0, 'estimated_items': 0, 'missing_items': 0}
    for session in p['sessions']:
        for module in session['modules']:
            for item in module['items']:
                key = 'derived_items' if derived_estimates(item) else 'estimated_items' if item.get('work_seconds_per_set') is not None else 'missing_items'
                counts[key] += 1
    return {**counts, 'estimates_only': True,
            'limitation': '节奏与游速也是计划依据；检查推导和预算一致性，不认证个人实际完成时间。'}
