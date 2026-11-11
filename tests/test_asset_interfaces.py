import copy
import unittest
from unittest.mock import patch
from test_workflows import fixture
from common import library
from validate_plan import validate
from select_assets import select


class AssetInterfaces(unittest.TestCase):
    def test_library_query_returns_only_the_selected_family(self):
        rows = select(domain='F', family='短段速度')
        self.assertEqual({r['id'] for r in rows}, {'freestyle_fast_25', 'swim_50m_fast_repeats', 'swim_100m_speed_endurance'})
        self.assertTrue(all('exercise_definition' not in r for r in rows))

    def test_library_id_returns_complete_definition_and_rejects_unknown_id(self):
        row = select(ids=['kb_swing'])[0]
        self.assertTrue(row['exercise_definition'])
        self.assertTrue(row['default_dose'])
        with self.assertRaisesRegex(ValueError, '未注册动作编号'):
            select(ids=['unknown-asset'])

    def test_defined_pool_interface_is_checked_beyond_distance_multiple(self):
        p = fixture(); s = p['sessions'][2]; x = s['modules'][0]['items'][0]
        x['unit_id'] = 'freestyle_fast_25'; x['endurance_role'] = 'swim'
        x.pop('run_intensity', None); x['dose']['distance_m'] = 50
        p['profile']['pool']['length_m'] = 50
        p['profile']['mastery']['freestyle_fast_25'] = 'independent'
        result = validate(p)
        self.assertTrue(any('freestyle_fast_25: pool_length_m' in e for e in result['errors']))

    def test_numeric_interface_comes_from_asset_definition(self):
        p = fixture(); assets = copy.deepcopy(library())
        assets['bodyweight_squat']['dose_domain']['fields']['reps']['maximum'] = 7
        with patch('validate_plan.library', return_value=assets):
            result = validate(p)
        self.assertTrue(any('bodyweight_squat: reps: 高于' in e for e in result['errors']))

    def test_mixed_walk_run_recipe_cannot_be_counted_as_a_whole_run(self):
        p = fixture(); x = p['sessions'][2]['modules'][0]['items'][0]
        x['unit_id'] = 'run_walk'; x.pop('endurance_role'); x.pop('run_intensity')
        p['profile']['mastery']['run_walk'] = 'independent'
        assets = copy.deepcopy(library()); assets['run_walk']['endurance_role'] = 'mixed'
        with patch('validate_plan.library', return_value=assets):
            result = validate(p)
        self.assertTrue(any('混合训练单元需拆' in e for e in result['insufficient_basis']))
        self.assertFalse(result['endurance_summary']['sessions']['S3']['has_run'])


if __name__ == '__main__':
    unittest.main()
