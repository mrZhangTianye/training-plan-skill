# -*- coding: utf-8 -*-
"""Expand declared set order and honor each task's own between-set recovery."""
from collections import Counter
import math
from work_timing import whole_set_seconds


def sequence(module):
    items = module['items']
    sets = [x['dose']['sets'] for x in items]
    if len(items) not in (2, 3) or None in sets:
        raise ValueError('group requires two or three items with explicit set counts')
    declared = module.get('set_sequence')
    if declared is None:
        if len(set(sets)) != 1:
            raise ValueError('unequal group set counts require an explicit set_sequence')
        declared = list(range(1, len(items) + 1)) * sets[0]
    if any(i < 1 or i > len(items) for i in declared):
        raise ValueError('set_sequence refers to an item outside this group')
    counts = Counter(declared)
    if any(counts[i + 1] != count for i, count in enumerate(sets)):
        raise ValueError('set_sequence counts must match each item set prescription')
    return declared


def schedule(module):
    """Practical order with waits rounded up to 30s; transitions need allocation."""
    order = sequence(module)
    work = [whole_set_seconds(x) for x in module['items']]
    if any(v is None for v in work):
        raise ValueError('group timing needs whole-set work estimates')
    cursor, last_end, result = 0, {}, []
    for index in order:
        item = module['items'][index - 1]
        wait = max(0, last_end.get(index, -item['dose']['rest_seconds']) + item['dose']['rest_seconds'] - cursor)
        start = cursor + math.ceil(wait / 30) * 30
        end = start + work[index - 1]
        result.append({'item': index, 'start': start, 'end': end, 'wait': start - cursor})
        cursor, last_end[index] = end, end
    return result
