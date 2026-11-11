import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_library import load_bundle, validate_bundle, LEGACY_IDS


class LibraryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_bundle()

    def test_package_contract_and_legacy_ids(self):
        result = validate_bundle(self.bundle)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['canonical_count'], 336)
        self.assertEqual(result['legacy_id_count'], len(LEGACY_IDS))
        self.assertEqual(set(result['catalog_only']), {'run_time_trial', 'swim_breaststroke_kick_streamline', 'swim_breaststroke_slide_stroke_slide'})

    def mutate_asset(self, uid, change):
        bundle = copy.deepcopy(self.bundle)
        change(next(x for x in bundle['assets-v3']['assets'] if x['id'] == uid))
        return validate_bundle(bundle)['errors']

    def test_missing_new_definition_is_rejected(self):
        errors = self.mutate_asset('swim_50m_fast_repeats', lambda a: a.pop('default_dose'))
        self.assertTrue(any('execution_field' in e for e in errors))

    def test_cross_family_grade_is_rejected(self):
        def change(a):
            a['relation'] = {'base_id': 'goblet_squat', 'kind': 'progression', 'preserves_task': True}
        self.assertTrue(any('graded_relation' in e for e in self.mutate_asset('barbell_conventional_deadlift', change)))

    def test_source_metadata_cannot_leak(self):
        errors = self.mutate_asset('snatch_balance', lambda a: a.update(src='external review'))
        self.assertTrue(any('source_metadata' in e for e in errors))

    def test_directory_test_cannot_be_enabled(self):
        errors = self.mutate_asset('run_time_trial', lambda a: a.update(training_allowed=True))
        self.assertTrue(any('test_permission' in e for e in errors))

    def test_wrong_phase_sequence_is_rejected(self):
        errors = self.mutate_asset('continuous_hurdle_jump', lambda a: a['level'].update(number=2))
        self.assertTrue(any('phase_sequence' in e for e in errors))

    def test_out_of_domain_default_is_rejected(self):
        errors = self.mutate_asset('depth_jump', lambda a: a['default_dose'].update(platform_height_cm=40))
        self.assertTrue(any('default_outside_domain' in e for e in errors))

    def test_running_and_walking_are_separate_physical_roles(self):
        runtime = {a['id']: a for a in self.bundle['exercises'] + self.bundle['training-units']}
        self.assertEqual(runtime['brisk_walk']['endurance_role'], 'walk')
        for uid in ('run_walk', 'run_walk_progression', 'run_warmup', 'run_cooldown'):
            self.assertEqual(runtime[uid]['endurance_role'], 'mixed')
            self.assertTrue(runtime[uid]['requires_segment_expansion'])
        for uid in ('warmup', 'cooldown', 'mobility'):
            self.assertNotIn('endurance_role', runtime[uid])

    def test_pool_specific_short_speed_and_long_pool_option(self):
        assets = {a['id']: a for a in self.bundle['assets-v3']['assets']}
        self.assertEqual(assets['freestyle_fast_25']['default_dose']['pool_lengths_m'], [25])
        self.assertEqual(assets['swim_50m_fast_repeats']['default_dose']['pool_lengths_m'], [25, 50])
        self.assertEqual(assets['swim_50m_fast_repeats']['default_dose']['rest_seconds'], 60)

    def test_task_distinct_ids_and_technique_are_preserved(self):
        assets = {a['id']: a for a in self.bundle['assets-v3']['assets']}
        self.assertIn('box_jump_stick', assets)
        self.assertIn('hurdle_jump_stick', assets)
        self.assertEqual(assets['snatch_balance']['power_variant']['receiving_position'], 'overhead_full_squat')
        self.assertIn('驱动', assets['snatch_balance']['exercise_definition'])
        self.assertEqual(assets['sprint_30m']['primary_task'], '静止起跑后的短直线加速与快速跑')


if __name__ == '__main__':
    unittest.main()
