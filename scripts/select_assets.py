"""Read a small, relevant slice of the library instead of loading the full catalogue."""
import argparse
import json
import sys
from common import ROOT, read_json, library


def select(ids=None, domain=None, family=None, query=None, details=False):
    catalogue = read_json(ROOT / 'references/training-library/assets-v3.json')
    assets = library()
    if ids:
        missing = [uid for uid in ids if uid not in assets]
        if missing:
            raise ValueError('未注册动作编号：' + '、'.join(missing))
        return [assets[uid] for uid in ids]
    if not any((domain, family, query)):
        return catalogue['domains']
    families = {f['id']: f for f in catalogue['families']}
    rows = []
    for asset in catalogue['assets']:
        if domain and asset['domain_id'] != domain:
            continue
        group = families[asset['family_id']]
        if family and family not in (group['id'], group['name']):
            continue
        runtime = assets[asset['id']]
        haystack = ' '.join((runtime['id'], runtime['name'], runtime.get('english_name', ''), group['name'])).casefold()
        if query and query.casefold() not in haystack:
            continue
        rows.append(runtime if details else {
            'id': runtime['id'], 'name': runtime['name'], 'domain_id': runtime['domain_id'],
            'family': group['name'], 'level': runtime['level'],
            'training_allowed': runtime['training_allowed'],
            'equipment_options': runtime['equipment_options'],
            'selection_conditions': runtime['selection_conditions']})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', action='append')
    parser.add_argument('--domain')
    parser.add_argument('--family')
    parser.add_argument('--query')
    parser.add_argument('--details', action='store_true')
    args = parser.parse_args()
    try:
        result = select(args.id, args.domain, args.family, args.query, args.details)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
