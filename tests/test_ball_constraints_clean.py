import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_workflows import fixture
from test_short_window_clean import one_day
from validate_plan import validate
from ball_constraints import check,replacement_errors

def ball(**kw):
    d={'id':'BALL1','date':'2026-10-05','sport':'其他','source':'合成用户安排'};d.update(kw);return d
class BallTests(unittest.TestCase):
    def test_other_no_ball_and_date_scope(self):
        p=fixture();self.assertEqual(check(p)['errors'],[])
        p['ball_days']=[ball(date='2026-10-06')];self.assertTrue(check(p)['errors']) # declared rest
        p=one_day();p['ball_days']=[ball(date='2026-10-06')];self.assertTrue(check(p)['errors'])
        p['ball_days']=[ball(date='2026-11-01')];self.assertTrue(check(p)['errors'])
    def test_unknown_duration_and_clock_not_faked(self):
        p=fixture();p['ball_days']=[ball(start_time='18:00')];r=validate(p)
        self.assertEqual(r['errors'],[]);self.assertTrue(r['ball_check']['unverified']);self.assertFalse(r['ready_to_render_executable'])
        self.assertIn(1,r['blocked_weeks'])
    def test_overlap_and_nonoverlap_review(self):
        p=fixture();p['status']='executable';p['ball_days']=[ball(start_time='09:05',duration_minutes=30)]
        self.assertTrue(check(p)['errors'])
        p['ball_days'][0]['start_time']='09:20';r=validate(p);self.assertFalse(r['ready_to_render_executable'])
        review=next(r for r in p['design_review'] if r['topic']=='load_recovery');review['checked_ids']+=['BALL1'];review['reason']='合成测试：已审查两个安排的强度、顺序与恢复，不宣称机器认证安全'
        r=validate(p);self.assertEqual(r['errors'],[]);self.assertFalse(r['ball_check']['unverified']);self.assertTrue(r['ready_to_render_executable'])
    def test_fixed_ball_pair_and_near_day_reminders(self):
        p=fixture();p['ball_days']=[ball(start_time='12:00',duration_minutes=60),ball(id='BALL2',start_time='12:30',duration_minutes=60)]
        self.assertTrue(check(p)['errors']);self.assertTrue(check(p)['reminders'])
    def test_schema_and_source(self):
        for kw in [{'start_time':'25:90'},{'duration_minutes':-1},{'source':'  '},{'sport':'  '}]:
            p=fixture();p['ball_days']=[ball(**kw)];self.assertTrue(validate(p)['errors'],kw)
        p=fixture();p['ball_days']=[ball(),ball()];self.assertTrue(validate(p)['errors'])
    def test_visible_in_outputs_and_unique_identity(self):
        from render_plan import render
        from render_weekly_log import week_doc
        from common import library
        p=fixture();p['ball_days']=[ball(start_time='18:00')]
        self.assertIn('固定球类安排',render(p,'week',week=1,allow_gaps=True))
        self.assertIn('未核定',week_doc(p,1,library()))
        p['ball_days'][0]['id']='S1';self.assertTrue(validate(p)['errors'])
    def test_replacement_protection(self):
        a=fixture();b=copy.deepcopy(a);b['sessions']=b['sessions'][1:];b['ball_days']=[ball()]
        proposal=[{'session_id':'S1','ball_day_id':'BALL1','source':'合成替换请求'}]
        self.assertEqual(replacement_errors(a,b,proposal),[])
        a['sessions'][0]['status']='completed';self.assertTrue(replacement_errors(a,b,proposal))
        a=fixture();a['evidence']=[{'id':'E','source_type':'performance','session_id':'S1'}];self.assertTrue(replacement_errors(a,b,proposal))
        a=fixture();self.assertTrue(replacement_errors(a,b,[]));b['ball_days'][0]['date']='2026-10-06';self.assertTrue(replacement_errors(a,b,proposal))
    def test_real_compare_replacement_and_immutable_history(self):
        from compare_plans import compare_ball_replacement
        a=fixture(); b=copy.deepcopy(a); b['version']+=1
        b['sessions']=[s for s in b['sessions'] if s['id']!='S1']
        b['weeks'][0]['session_ids']=['S2','S3'];b['weeks'][0]['module_summary']='力量1次，跑1次'
        b['objectives'][0]['progression_plan'][0]['session_frequency']=1
        b['ball_days']=[ball()]
        for row in b['design_review']:
            row['checked_ids']=[x for x in row['checked_ids'] if x!='S1']+['BALL1']
        proposal=[{'session_id':'S1','ball_day_id':'BALL1','source':'合成用户替换'}]
        original=copy.deepcopy(a);candidate=copy.deepcopy(b)
        self.assertEqual(validate(a)['errors'],[])
        self.assertEqual(validate(b)['errors'],[])
        change=compare_ball_replacement(a,b,proposal,'合成替换',[],'检查固定球日及减少的力量频次')
        self.assertEqual(change['before_version'],1);self.assertEqual(change['after_version'],2)
        self.assertTrue(any(x['path']=='/sessions/S1' and x['operation']=='remove' for x in change['changes']))
        self.assertEqual(a,original);self.assertEqual(b,candidate)
        a['sessions'][0]['status']='completed'
        with self.assertRaisesRegex(ValueError,'executed history'):compare_ball_replacement(a,b,proposal,'替换',[],'审核')
        a=copy.deepcopy(original)
        a['evidence']=[{'id':'E1','date':'2026-10-05','source_type':'constraint','session_id':'S1',
                       'raw':'合成实际组数','observations':[],'interpretations':[],
                       'actual_sets':[{'unit_id':'push_up','set_number':1,'weight_kg':None,'reps':8,'actual_rpe':6}]}]
        self.assertEqual(validate(a)['errors'],[])
        with self.assertRaisesRegex(ValueError,'executed history'):compare_ball_replacement(a,b,proposal,'替换',[],'审核')
        # Even without a replacement, deleting mislabeled actual sets is forbidden.
        preserved=copy.deepcopy(a);preserved['version']+=1;preserved['evidence']=[]
        with self.assertRaisesRegex(ValueError,'evidence must be retained'):compare_ball_replacement(a,preserved,[],'改标',[],'审核')
    def test_real_cli_replacement_routes_and_history(self):
        import json,subprocess,tempfile,os
        a=fixture();b=copy.deepcopy(a);b['version']+=1
        b['sessions']=b['sessions'][1:];b['weeks'][0]['session_ids']=['S2','S3'];b['weeks'][0]['module_summary']='力量1次，跑1次'
        b['objectives'][0]['progression_plan'][0]['session_frequency']=1;b['ball_days']=[ball()]
        for row in b['design_review']:row['checked_ids']=[x for x in row['checked_ids'] if x!='S1']+['BALL1']
        proposal=[{'session_id':'S1','ball_day_id':'BALL1','source':'合成请求'}]
        script=Path(__file__).resolve().parents[1]/'scripts/compare_plans.py'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def run(before,after,flags=()):
                for name,value in [('a.json',before),('b.json',after),('proposals.json',proposal)]: (root/name).write_text(json.dumps(value))
                output=root/'changes.json'
                if output.exists():output.unlink()
                original=(root/'a.json').read_bytes()
                cp=subprocess.run([sys.executable,str(script),str(root/'a.json'),str(root/'b.json'),'--output',str(output),'--reason','synthetic','--association-review','synthetic review']+list(flags),capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                self.assertEqual(original,(root/'a.json').read_bytes())
                self.assertEqual(output.exists(),cp.returncode==0)
                return cp
            self.assertNotEqual(run(a,b).returncode,0)
            flags=['--ball-replacements',str(root/'proposals.json')]
            self.assertEqual(run(a,b,flags).returncode,0)
            self.assertNotEqual(run(a,b,flags+['--allow-history-correction']).returncode,0)
            completed=copy.deepcopy(a);completed['sessions'][0]['status']='completed'
            self.assertNotEqual(run(completed,b,flags).returncode,0)
            evidence=copy.deepcopy(a);evidence['evidence']=[{'id':'E1','date':'2026-10-05','source_type':'constraint','session_id':'S1','raw':'synthetic actual sets','observations':[],'interpretations':[],'actual_sets':[{'unit_id':'push_up','set_number':1,'weight_kg':None,'reps':8,'actual_rpe':6}]}]
            removed=copy.deepcopy(evidence);removed['version']+=1;removed['evidence']=[]
            for extra in [[],['--allow-history-correction']]:
                cp=run(evidence,removed,extra);self.assertNotEqual(cp.returncode,0);self.assertIn('execution evidence',cp.stderr)
if __name__=='__main__':unittest.main()
