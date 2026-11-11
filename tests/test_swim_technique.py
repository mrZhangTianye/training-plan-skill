import copy
import unittest
from test_workflows import fixture
from common import ROOT, library, read_json, schema_errors
from validate_plan import validate
from swim_contract import check, feedback_errors
from endurance_stats import calculate, check as check_distance
from session_summary import swim_mini_goal
from render_plan import session_body
from validate_library import load_bundle, validate_bundle

PREFIX = 'swim_breaststroke_'

def plan(short='controlled', pool=25):
    p = fixture(); p['weeks'][0]['module_summary']='力量2次，泳1次'; uid = PREFIX + short; a = library()[uid]
    s = p['sessions'][2]; s['kind'] = 'swim'; s['title'] = '虚构蛙泳技术测试'
    s['purpose'] = '巩固已会技术'; s['mini_goal'] = '保持伸展'
    s['swim_focus'] = {'unit_id':uid, 'goal':a['primary_task'], 'observation':a['observation']}
    p['objectives'][1]['capability']='coordination'
    p['objectives'][1]['capability_ids']=['coordination']
    for c in p['design_context']['coverage']:
        if c['capability_id']=='endurance': c['mode']='unassessed'
        if c['capability_id']=='coordination': c['mode']='develop'
    p['profile']['pool']['length_m'] = pool
    p['profile']['equipment'] += a['equipment_options'][0]
    p['profile']['mastery'][uid] = 'unknown' if a['swim_task_mode'] == 'stationary' else 'independent'
    p['profile']['swim_task_readiness'] = {uid:{'status':'ready','basis':'虚构测试中的具体任务自述，不是医学许可','continuous_distance_m':pool}}
    x = s['modules'][0]['items'][0]; x['unit_id'] = uid; x['endurance_role'] = 'swim'; x.pop('run_intensity')
    x['dose']['load']['target_rpe'] = None; x['dose']['load']['description'] = '轻松，正常呼吸'
    x['dose'].update(sets=2,reps=None,duration_minutes=0.5 if a['swim_task_mode']=='stationary' else None,distance_m=None if a['swim_task_mode']=='stationary' else pool,rest_seconds=30)
    x['work_seconds_per_set'] = 30 if a['swim_task_mode']=='stationary' else 60
    s['mini_goal'] = swim_mini_goal(s, pool)
    return p

class SwimTechnique(unittest.TestCase):
    def test_all_six_supported_tasks_pass_new_contract(self):
        for short in ('kick_deck','pull_standing','kick_supine','breathe_kick_slide','controlled','two_kicks_one_pull'):
            with self.subTest(short=short):
                p=plan(short); self.assertEqual(check(p, library()), ([], []))
                self.assertEqual(validate(p)['errors'], [])
                self.assertEqual(validate(p)['insufficient_basis'], [])
    def test_repeated_id_cannot_hide_oversized_earlier_segment(self):
        p=plan(); items=p['sessions'][2]['modules'][0]['items']; original=items[0]
        original['dose']['distance_m']=50; later=copy.deepcopy(original); later['dose']['distance_m']=25; items.append(later)
        self.assertTrue(any('exceeds' in x for x in check(p,library())[0]))
    def test_nested_repetitions_not_ambiguous(self):
        p=plan(); p['sessions'][2]['modules'][0]['items'][0]['dose']['reps']=2
        self.assertTrue(any('nested reps' in x for x in check(p,library())[0]))
    def test_50m_pool_with_specific_ability(self):
        p=plan(pool=50); self.assertEqual(check(p,library()),([],[]))
        self.assertEqual(calculate(p,library())['sessions']['S3']['swim_distance_m'],100)
    def test_unknown_task_not_promoted(self):
        p=plan(); before=copy.deepcopy(p['profile']); p['profile']['swim_task_readiness'][PREFIX+'controlled']['status']='unknown'
        self.assertTrue(check(p,library())[1]); self.assertEqual(p['profile']['mastery'],before['mastery'])
    def test_missing_task_distance_is_not_inferred_from_other_stroke(self):
        p=plan(); del p['profile']['swim_task_readiness'][PREFIX+'controlled']['continuous_distance_m']
        self.assertTrue(any('continuous distance' in x for x in check(p,library())[1]))
    def test_distance_above_specific_ability_rejected(self):
        p=plan(pool=50); p['profile']['swim_task_readiness'][PREFIX+'controlled']['continuous_distance_m']=25
        self.assertTrue(any('exceeds' in x for x in check(p,library())[0]))
    def test_unknown_mastery_blocks_moving_task(self):
        p=plan(); p['profile']['mastery'][PREFIX+'controlled']='unknown'
        self.assertTrue(any('independent skill' in x for x in validate(p)['errors']))
    def test_stationary_does_not_promote_mastery_or_add_distance(self):
        p=plan('kick_deck'); uid=PREFIX+'kick_deck'; self.assertEqual(p['profile']['mastery'][uid],'unknown')
        self.assertEqual(calculate(p,library())['sessions']['S3']['swim_distance_m'],0)
        self.assertEqual(check_distance(p,library()),([],[]))
    def test_stationary_invented_distance_rejected(self):
        p=plan('pull_standing'); p['sessions'][2]['modules'][0]['items'][0]['dose']['distance_m']=25
        self.assertTrue(any('stationary' in x for x in check(p,library())[0]))
    def test_stationary_not_aerobic_credit(self):
        p=plan('kick_deck'); p['sessions'][2]['modules'][0]['items'][0]['aerobic_minutes']=1
        self.assertTrue(check(p,library())[0])
    def test_stationary_requires_task_confirmation(self):
        p=plan('kick_deck'); p['profile'].pop('swim_task_readiness')
        self.assertTrue(check(p,library())[1])
    def test_missing_board_rejected(self):
        p=plan('breathe_kick_slide'); p['profile']['equipment'].remove('kickboard')
        self.assertTrue(any('equipment unavailable' in x for x in validate(p)['errors']))
    def test_banned_task_not_overridden_by_ready(self):
        p=plan(); p['profile']['banned_units']=[PREFIX+'controlled']
        self.assertTrue(any('prohibited unit' in x for x in validate(p)['errors']))
    def test_reference_only_tasks_rejected(self):
        for short in ('kick_streamline','slide_stroke_slide'):
            p=plan(short); self.assertTrue(any('reference-only' in x for x in check(p,library())[0]))
    def test_focus_must_be_selected(self):
        p=plan(); p['sessions'][2]['swim_focus']['unit_id']=PREFIX+'kick_supine'
        self.assertTrue(check(p,library())[0])
    def test_focus_required(self):
        p=plan(); del p['sessions'][2]['swim_focus']; self.assertTrue(check(p,library())[1])
    def test_feedback_is_optional_for_plan(self):
        p=plan(); self.assertNotIn('feedback',p); self.assertEqual(check(p,library()),([],[]))
    def test_feedback_valid_and_unknown_is_explicit(self):
        p=plan(); value={'session_id':'S3','unit_id':PREFIX+'controlled','completion':'partial','difficulty':'hard','focus_result':'not_observed','symptoms':'not_reported'}
        self.assertEqual(feedback_errors(value,p,library()),[])
        value['focus_result']='passed'; self.assertTrue(feedback_errors(value,p,library()))
    def test_feedback_wrong_session_and_stationary_distance(self):
        p=plan('kick_deck'); value={'session_id':'missing','unit_id':PREFIX+'kick_deck','completion':'done','difficulty':'easy','focus_result':'maintained','distance_m':25}
        self.assertEqual(len(feedback_errors(value,p,library())),2)
    def test_render_uses_breaststroke_and_focus(self):
        p=plan(); s=p['sessions'][2]; self.assertIn('蛙泳50米',swim_mini_goal(s,25)); self.assertNotIn('自由泳',swim_mini_goal(s,25))
        self.assertIn('今天只关注',session_body(s,library()))
    def test_evidence_registry_and_canonical_ids(self):
        bundle=load_bundle(); self.assertEqual(validate_bundle(bundle)['errors'],[])
        refs=bundle['evidence_registry']['entries']; self.assertEqual(len(refs),8)
        self.assertEqual({x['drill_number'] for x in refs},{18,19,20,66,70,71,72,73})
        self.assertEqual(bundle['evidence_registry']['works'][0]['year'],2007)
    def test_broken_evidence_reference_rejected(self):
        bundle=load_bundle(); a=next(x for x in bundle['assets-v3']['assets'] if x['id']==PREFIX+'controlled'); a['evidence_refs']=['missing']
        self.assertTrue(any('evidence_reference' in x for x in validate_bundle(bundle)['errors']))
    def test_readiness_schema_rejects_fake_status(self):
        p=plan(); p['profile']['swim_task_readiness'][PREFIX+'controlled']['status']='certified'
        self.assertTrue(schema_errors(p,read_json(ROOT/'schemas/plan.schema.json')))
    def test_documents_do_not_restore_fixed_week_gates(self):
        doc=(ROOT/'references/swim-programming.md').read_text()
        for old in ('C 档四周后才加','第 3 次**这一课加入','一律按「只能重复50米」','W4 的量'):
            self.assertNotIn(old,doc)
        self.assertIn('预设正常递进',doc)

if __name__ == '__main__': unittest.main()
