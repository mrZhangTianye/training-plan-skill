"""Check explicit library parameter interfaces; prose conditions remain design work."""
from work_timing import whole_set_seconds


def check(item, asset, pool_length=None):
    errors = []
    for key, limits in asset.get('dose_domain', {}).get('fields', {}).items():
        if not limits.get('machine_check'):
            continue
        field = limits.get('plan_field', '')
        if field == 'session.pool_length_m_or_profile.pool.length_m':
            value = pool_length
        elif field == 'work_seconds_per_set':
            value = whole_set_seconds(item)
        else:
            value = item
            for part in field.split('.'):
                value = value.get(part) if isinstance(value, dict) else None
        if field == 'dose.sets' and value is None:
            value = 1
        if value is None:
            continue
        value *= limits.get('plan_value_multiplier', 1)
        if limits.get('allowed_values') is not None and value not in limits['allowed_values']:
            errors.append(key + ': 超出本动作定义的允许参数，需选适用版本或展开任务')
        if limits.get('minimum') is not None and value < limits['minimum']:
            errors.append(key + ': 低于本动作参数接口下限，需选适用版本')
        if limits.get('maximum') is not None and value > limits['maximum']:
            errors.append(key + ': 高于本动作参数接口上限，需选适用版本')
        if limits.get('integer') and value != int(value):
            errors.append(key + ': 本动作要求整数参数')
    return errors
