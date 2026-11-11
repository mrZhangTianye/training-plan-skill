import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_workflows import fixture
from validate_plan import validate
from render_plan import render
from render_weekly_log import week_doc
from export_plan import export
from common import library

def one_day():
    p=copy.deepcopy(fixture());p['scope']={'window':'day','dates':[p['start_date']]}
    p['sessions']=p['sessions'][:1];p['weeks'][0].update(session_ids=['S1'],rest_days=[],module_summary='力量1次')
    p['objectives']=p['objectives'][:1];p['objectives'][0]['progression_plan'][0]['session_frequency']=1
    p['blocks'][0]['goal_ids']=['G1'];p['status']='executable'
    for c in p['design_context']['coverage']:
        if c['capability_id']=='endurance': c['mode']='defer'
    for x in p['design_review']:x['checked_ids']=['TEST','G1','B1','S1']
    return p
class Windows(unittest.TestCase):
    def test_day_valid_and_render_export(self):
        p=one_day();v=validate(p);self.assertEqual(v['errors'],[]);self.assertTrue(v['ready_to_render_executable'])
        for view,kw in [('overall',{}),('week',{'week':1}),('block',{'block':'B1'}),('session',{'session':'S1'})]:
            doc=render(p,view,**kw);self.assertIn('2026-10-05',doc);self.assertNotIn('共1周',doc);self.assertNotIn('2026-10-11',doc)
            if view == 'overall': self.assertIn('共1天',doc)
        doc=week_doc(p,1,library());self.assertIn('单日训练计划',doc);self.assertIn('当日共',doc);self.assertNotIn('一天一个项目，不叠',doc)
        with tempfile.TemporaryDirectory() as d:
            names=export(p,d);self.assertEqual(names,['2026-10-05单日训练计划.md']);self.assertIn('单日训练计划',(Path(d)/names[0]).read_text())
    def test_bad_scope(self):
        for dates in [[],['2026-10-06'],['2026-10-05','2026-10-05']]:
            p=one_day();p['scope']['dates']=dates;self.assertTrue(validate(p)['errors'])
    def test_outside_and_missing(self):
        p=one_day();p['sessions'][0]['date']='2026-10-06';self.assertTrue(validate(p)['errors'])
        p=one_day();p['weeks'][0]['rest_days']=['2026-10-06'];self.assertTrue(validate(p)['errors'])
        p=one_day();p['sessions']=[];p['weeks'][0]['session_ids']=[];self.assertTrue(validate(p)['errors'])
    def test_safety_retained(self):
        p=one_day();p['profile']['available_minutes']['0']=1;self.assertTrue(validate(p)['errors'])
        p=one_day();p['profile']['mastery']['push_up']='unknown';self.assertTrue(validate(p)['insufficient_basis'])
        p=one_day();p['status']='draft';self.assertFalse(validate(p)['ready_to_render_executable'])
    def test_week_default_and_explicit(self):
        import datetime as dt
        p=fixture();self.assertEqual(validate(p)['errors'],[])
        p['scope']={'window':'week','dates':[(dt.date(2026,10,5)+dt.timedelta(days=i)).isoformat() for i in range(7)]}
        self.assertEqual(validate(p)['errors'],[]);p['scope']['dates'].pop();self.assertTrue(validate(p)['errors'])
    def test_scope_cannot_shorten_multiweek(self):
        p=one_day();p['duration_weeks']=3;self.assertTrue(validate(p)['errors'])
if __name__=='__main__':unittest.main()
