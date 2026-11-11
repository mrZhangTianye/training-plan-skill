"""Check library interfaces and references; do not certify exercise suitability."""
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_KEYS = {'src', 'source', 'sources', 'source_id', 'source_notes', 'origin',
                  'book_level', 'book_context', 'original_term', 'original_english',
                  'grade_is_from_book', 'number_is_from_book', 'number_source'}
LEGACY_IDS = set('goblet_squat bodyweight_squat front_squat rdl hip_hinge_drill single_leg_rdl split_squat push_up incline_push_up db_row pull_up carry side_plank kb_swing landing low_jump medball_throw bench_press military_press single_arm_cable_row pallof_press copenhagen_short copenhagen_long hip_airplane spanish_squat calf_raise jump_shrug hang_high_pull hang_power_clean dead_bug band_row standing_db_press db_bench_press incline_db_bench_press reactive_low_hops rotational_medball_throw bent_knee_calf_raise band_external_rotation lateral_lunge hip_90_90 half_kneeling_hip_flexor_stretch adductor_rock spiderman_step quadruped_tspine_rotation leg_lower supine_floor_slide knee_hug_single_leg_bridge mini_band_walk mini_band_squat half_kneeling_ankle_mobility bear_crawl inchworm knee_hug_walk leg_cradle_walk high_knee_march straight_leg_walk lateral_march lateral_shuffle scapular_wall_slide shoulder_circles ankle_active_flexion_extension front_plank warmup easy_run run_walk strides swim_technique swim_easy mobility cooldown controlled_hard_run foam_roll static_stretch controlled_hard_swim brisk_walk'.split())


def load_bundle(root=ROOT):
    base = Path(root) / 'references' / 'training-library'
    bundle = {name: json.loads((base / (name + '.json')).read_text()) for name in
              ('assets-v3', 'exercises', 'training-units', 'catalog', 'coverage', 'capabilities')}
    bundle['evidence_registry'] = json.loads((Path(root) / 'references/swim-technique-evidence.json').read_text())
    return bundle


def validate_bundle(bundle):
    errors = []
    def fail(code, location, detail):
        errors.append(f'{code}: {location}: {detail}')
    def scan(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_KEYS: fail('source_metadata', path, key)
                scan(child, path + '.' + key)
        elif isinstance(value, list):
            for i, child in enumerate(value): scan(child, f'{path}[{i}]')
        elif isinstance(value, str) and any(s in value for s in ('原书', '原教材', '五模型', 'https://')):
            fail('source_text', path, 'research attribution belongs outside the package')
    for name, value in bundle.items():
        if name != 'evidence_registry': scan(value, name)
    model = bundle['assets-v3']
    assets = model['assets']
    operational = bundle['exercises'] + bundle['training-units']
    def unique(rows, location):
        counts = Counter(x['id'] for x in rows)
        for uid, n in counts.items():
            if n != 1: fail('duplicate_id', location, uid)
        return {x['id']: x for x in rows}
    canonical = unique(assets, 'assets-v3')
    runtime = unique(operational, 'runtime')
    domains = unique(model['domains'], 'domains')
    families = unique(model['families'], 'families')
    catalog = unique(bundle['catalog']['entries'], 'catalog')
    caps = set(bundle['capabilities'])
    if set(catalog) != set(canonical): fail('catalog_ids', 'catalog', 'must preserve all canonical IDs')
    if len(canonical) != 336: fail('canonical_count', 'assets-v3', '0.3.25 has 336 directory entries')
    if not LEGACY_IDS <= set(runtime): fail('legacy_ids', 'runtime', str(sorted(LEGACY_IDS - set(runtime))))
    membership = Counter()
    for fid, family in families.items():
        if family['domain_id'] not in domains: fail('family_domain', fid, 'unknown domain')
        for uid in family['entry_ids']:
            membership[uid] += 1
            if uid not in canonical or canonical[uid]['family_id'] != fid:
                fail('family_membership', fid, uid)
        for chain in family.get('phase_sequences', []):
            if len(chain) != len(set(chain)): fail('phase_sequence', fid, 'repeated phase ID')
            for number, uid in enumerate(chain, 1):
                a = canonical.get(uid, {})
                if a.get('family_id') != fid or a.get('level', {}).get('kind') != 'phase' or a.get('level', {}).get('number') != number:
                    fail('phase_sequence', fid, f'{uid} must be phase {number} within this family')
    evidence = {x['id']: x for x in bundle['evidence_registry']['entries']}
    for uid, a in canonical.items():
        if a.get('swim_task_mode'):
            if not a.get('evidence_refs') or not a.get('task_requirements') or not a.get('observation'):
                fail('swim_contract', uid, 'needs evidence, task prerequisites and observation')
            for ref in a.get('evidence_refs', []):
                if ref not in evidence or evidence[ref]['unit_id'] != uid:
                    fail('evidence_reference', uid, ref)
            if a['swim_task_mode'] == 'reference_only' and a['training_allowed']:
                fail('reference_only', uid, 'must not be prescribed')
        if membership[uid] != 1: fail('family_membership', uid, 'must belong to exactly one family')
        f = families.get(a['family_id'])
        if not f or f['domain_id'] != a['domain_id']: fail('asset_domain', uid, 'family/domain mismatch')
        if a['entry_form'] not in ('exercise', 'training_unit', 'session_component'):
            fail('entry_form', uid, 'unknown form')
        if not a['capability_ids'] or not set(a['capability_ids']) <= caps:
            fail('capability_id', uid, 'unknown or empty capability')
        supported = {x['capability_id'] for x in a.get('capability_support', [])}
        if supported != set(a['capability_ids']) or any(not x.get('scope') or not x.get('condition') for x in a.get('capability_support', [])):
            fail('support_scope', uid, 'each capability needs conditional support scope')
        if a['training_allowed']:
            for key in ('exercise_definition', 'prerequisite', 'selection_conditions', 'cue', 'stop_condition', 'default_dose', 'dose_domain'):
                if not a.get(key): fail('execution_field', uid, key)
            if a['definition_status'] != 'defined': fail('execution_status', uid, 'training requires complete definition')
        elif a.get('default_dose') is not None:
            fail('blocked_dose', uid, 'directory-only entry must not carry training prescription')
        if uid not in runtime: fail('runtime_id', uid, 'missing runtime interface')
        elif runtime[uid].get('training_allowed') != a['training_allowed']:
            fail('runtime_permission', uid, 'runtime and canonical training permission differ')
        rel = a.get('relation')
        if rel:
            parent = canonical.get(rel.get('base_id'))
            if not parent: fail('relation_id', uid, 'unknown base_id')
            elif rel['kind'] in ('progression', 'regression', 'phase_progression'):
                if parent['family_id'] != a['family_id'] or not rel.get('preserves_task', True):
                    fail('graded_relation', uid, 'graded relation must preserve comparable within-family task')
            elif rel['kind'] == 'task_or_equipment_branch' and a['level']['kind'] in ('progression', 'regression'):
                fail('branch_level', uid, 'task branch must not imply automatic grade')
        if a['entry_form'] == 'training_unit':
            if not a.get('intensity_zone', {}).get('code') or not a.get('frequency_role'):
                fail('unit_interface', uid, 'missing intensity/frequency role')
        if a['entry_form'] == 'session_component':
            component = a.get('component_spec', {})
            if not component.get('trigger') or not component.get('profiles') or not component.get('linkage'):
                fail('component_interface', uid, 'missing trigger/profiles/linkage')
        domain = a.get('dose_domain', {})
        for key, spec in domain.get('fields', {}).items():
            lo, hi = spec.get('minimum'), spec.get('maximum')
            if lo is not None and hi is not None and lo > hi: fail('parameter_domain', uid, key)
            if spec.get('machine_check') and not spec.get('plan_field'):
                fail('parameter_interface', uid, key)
            dose = a.get('default_dose') or {}
            value = dose.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if lo is not None and value < lo or hi is not None and value > hi:
                    fail('default_outside_domain', uid, key)
                if spec.get('integer') and value != int(value): fail('integer_parameter', uid, key)
        if a.get('endurance_role') == 'mixed' and not a.get('requires_segment_expansion'):
            fail('mixed_segments', uid, 'must require actual-segment expansion')
    for uid, a in runtime.items():
        for key in ('category', 'capabilities', 'equipment_options', 'selection_conditions', 'cue', 'stop_condition', 'regressions', 'progressions'):
            if key not in a: fail('runtime_field', uid, key)
        if not isinstance(a.get('requires_mastery'), bool): fail('mastery_type', uid, 'requires_mastery must be boolean')
        if not a.get('equipment_options') or any(not isinstance(c, list) or any(not isinstance(t, str) or not t for t in c) for c in a.get('equipment_options', [])):
            fail('equipment_interface', uid, 'needs OR of AND token lists; empty combination means no equipment')
        if not set(a.get('capabilities', [])) <= caps: fail('runtime_capability', uid, 'unknown capability')
        target = a.get('canonical_id')
        if target and target not in canonical: fail('canonical_alias', uid, 'unknown canonical target')
        if target is None and not a.get('alias_policy'): fail('legacy_adapter', uid, 'unresolved generic needs explicit adapter policy')
        for key in ('regressions', 'progressions', 'alternatives', 'canonical_options'):
            for link in a.get(key, []):
                if link not in runtime: fail('runtime_relation', uid, link)
        if a.get('endurance_role') not in (None, 'run', 'swim', 'walk', 'other', 'mixed'):
            fail('endurance_role', uid, 'unknown physical role')
    # Progression edges are a partial order, so cycles indicate contradictory grades.
    graph = {uid: a['progressions'] for uid, a in canonical.items()}
    visiting, done = set(), set()
    def visit(uid):
        if uid in visiting:
            fail('grade_cycle', uid, 'cyclic progression'); return
        if uid in done: return
        visiting.add(uid)
        for child in graph.get(uid, []): visit(child)
        visiting.remove(uid); done.add(uid)
    for uid in graph: visit(uid)
    for cap in bundle['coverage']['capabilities']:
        if cap['id'] not in caps: fail('coverage_capability', 'coverage', cap['id'])
        expected = {a['id'] for a in assets if cap['id'] in a['capability_ids'] and a['training_allowed']}
        if set(cap['operational_assets']) != expected:
            fail('coverage_ids', cap['id'], 'coverage does not match defined allowed assets')
    if canonical.get('run_time_trial', {}).get('training_allowed') is not False:
        fail('test_permission', 'run_time_trial', 'must be directory-only')
    return {'errors': list(dict.fromkeys(errors)), 'canonical_count': len(canonical), 'runtime_count': len(runtime),
            'legacy_id_count': len(LEGACY_IDS & set(runtime)),
            'catalog_only': [a['id'] for a in assets if not a['training_allowed']],
            'structurally_valid': not errors,
            'limitation': '只检查字段、数值接口及引用一致性；动作技术、掌握、暴露和实际剂量适宜性仍需逐项判断。'}


def validate(root=ROOT):
    return validate_bundle(load_bundle(root))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = validate(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
