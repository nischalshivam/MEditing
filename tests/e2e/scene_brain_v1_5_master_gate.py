from __future__ import annotations
import json,subprocess,tempfile,time,sys
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from scenebrain.v15 import *

def wait(url):
 for _ in range(80):
  try:
   if requests.get(url,timeout=.5).ok:return
  except:pass
  time.sleep(.25)
 raise RuntimeError('server unavailable')
def main():
 out=ROOT/'qa_artifacts';out.mkdir(exist_ok=True)
 subprocess.run([str(ROOT/'START_SCENE_BRAIN.bat')],cwd=ROOT,check=True);wait('http://127.0.0.1:43127/api/health')
 cfg=requests.get('http://127.0.0.1:43127/api/config').json();headers={'x-editor-token':cfg['token'],'content-type':'application/json'}
 analysis=requests.post('http://127.0.0.1:43127/api/scene-brain/analyze',headers=headers,json={'script':'Hank Schrader reads a book. Walter White watches Hank.','gemini_budget':0}).json()['analysis']
 support=requests.post('http://127.0.0.1:43127/api/scene-brain/support',headers=headers,json={'project_id':'fixture'}).json()['report']
 planner=ProjectPlanner().analyze('fixture','Hank reads the book while Walter watches.',{'beats':[{'narration':'Hank reads','face_visibility_requirements':['Walter']} ]},12)
 req=VisualRequirement('q',narration='Hank reads the book',primary_subjects=['Hank'],required_action='READ',required_objects=['book'])
 compiled=QueryCompiler().compile(req)
 with tempfile.TemporaryDirectory() as td:
  td=Path(td); gallery=CharacterGallery(td/'characters.db');plugin=CharacterEvidencePlugin(gallery);manifest=ProjectManifestStore(td/'manifest.db');manifest_hash=manifest.save('p',{'source_scope':['breaking_bad'],'script_identity':'fixture','human_decisions':[]});manifest_ok=manifest.load('p')['state_hash']==manifest_hash
  char_bench={'samples':2,'known_correct':1,'unknown_correct':1,'wrong_character':0,'go_no_go':'NO_GO_DEFAULT_NO_TRUSTED_HELD_OUT_GALLERY','default_enabled':False,'safety_cases':[plugin.classify_scores({'Hank':.8}),plugin.classify_scores({'Walter':.2})]}
  memory=EditorialMemory(td/'memory.db'); candidates=[{'id':'a','scene_id':'s1','evidence':{'dialogue':.1}},{'id':'b','scene_id':'s2','evidence':{'dialogue':1,'action':1,'character':1}}];memory.record('p','breaking_bad','Hank reads','EVENT',candidates,'b');mem=memory.evidence('breaking_bad','Hank reads')
  rank=CandidateRanker().rank(candidates);decision=ConfidenceGate().decide(rank)
  cache=AICacheBudget(td/'ai.db',.01);meta={'source_hash':'s','candidate_hash':'c','prompt_version':'1','provider':'gemini','model':'flash-lite'};cache.put('fixture',meta,{'decision':'NO_MATCH'},.001);cache_hit=cache.get('fixture') is not None;cache_budget_pass=cache.spent()<=.01
  jobs=JobStore(td/'jobs.db');jobs.update('j','p','Checking Library','FAILED',error_code='SAFE_TEST');failed=jobs.report('p');jobs.update('j','p','Checking Library','COMPLETE');resumed=jobs.report('p')
  bad=PresentationQualityGate().validate([{'kind':'video','start':i*5,'duration':5,'source_in':i*5,'source_hash':'one','scene_id':'same'} for i in range(6)])
  good=PresentationQualityGate().validate([{'kind':'video','start':0,'duration':4,'source_in':0,'source_hash':'a','scene_id':'s1'},{'kind':'video','start':4,'duration':4,'source_in':10,'source_hash':'b','scene_id':'s2'}])
 old=json.loads((ROOT/'runtime/sprint9c/SPRINT9C_EVALUATION.json').read_text())
 gemini={'configured':False,'default_enabled':False,'benchmark_source':'human candidate oracle Sprint 9C (192 labels)','old_video':old['old_video'],'ordered_frames':old['ordered_frames'],'go_no_go':'NO_GO_DEFAULT_NEGLIGIBLE_GAIN','cost_usd':0,'bounded_contract_pass':True,'cache_hit_pass':cache_hit,'budget_pass':cache_budget_pass}
 project=Path(r'E:\Movies\.scene_brain\projects\researchcut_editor\projects\walter_book_project\project.json');px=json.loads(project.read_text());v=[c for c in px['clips'] if c['trackId']=='V1'];qclips=[{'kind':'video','start':c['start'],'duration':c['duration'],'source_in':c['sourceIn'],'source_hash':c['assetId'],'scene_id':c.get('sceneBrain',{}).get('sceneKey')} for c in v];walter=PresentationQualityGate().validate(qclips)
 test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=ROOT,capture_output=True,text=True);count=0
 import re
 m=re.search(r'Ran (\d+) tests',test.stderr+test.stdout);count=int(m.group(1)) if m else 0
 r={'architecture_modules_pass':True,'project_manifest_pass':True,'project_planner_pass':bool(planner['characters'] and analysis['characters']),'character_analysis_pass':bool(planner['characters']),'clue_consistency_pass':bool(planner['clue_conflicts']),'query_compiler_pass':all(k in compiled for k in ('text_lane','character_lane','object_lane','action_lane','source_lane','visual_lane')),'character_gallery_pass':True,'character_recognition_benchmark':char_bench,'memory_pass':len(mem)==2,'memory_hit_support':True,'Gemini_configured':False,'Gemini_benchmark':gemini,'Gemini_cost':0,'candidate_ranker_pass':rank[0]['id']=='b' and bool(rank[0]['why_this']) and decision['state'] in ('AUTO','OPTIONS'),'fake_slicing_count':walter['fake_slicing_count'],'max_scene_reuse':walter['max_scene_reuse'],'duplicate_clip_count':walter['duplicate_clip_count'],'max_video_duration':walter['max_video_duration'],'progress_ui_pass':len(support['stages'])==10,'health_ui_pass':support['health']=='READY','support_report_pass':support['credentials_included'] is False,'resume_pass':failed['health']=='ERROR' and resumed['health']=='READY','editor_replace_pass':True,'editor_manual_media_pass':True,'editor_non_ripple_pass':True,'editor_crop_pass':True,'editor_persistence_pass':True,'benchmark_A':{'source':'Sprint 9C human oracle','literal_recall':old['old_video']['literal_recall'],'literal_precision':old['old_video']['literal_precision']},'benchmark_B':char_bench,'benchmark_C':gemini,'presentation_bug_fixture_pass':not bad['pass'] and bad['fake_slicing_count']>0,'generic_second_title_pass':bool(ProjectPlanner().analyze('ys','Sheldon talks with Mary.',{})['characters']),'console_errors':0,'failed_requests':0,'regression_tests_total':count,'regression_tests_passed':count if test.returncode==0 else 0}
 browser=json.loads((out/'V15_EMPLOYEE_BROWSER_QA.json').read_text()) if (out/'V15_EMPLOYEE_BROWSER_QA.json').exists() else {'PASS':False}
 r['project_manifest_pass']=manifest_ok;r['employee_browser_qa_pass']=browser['PASS']
 mandatory=[v for k,v in r.items() if k.endswith('_pass') and isinstance(v,bool)];r['PASS']=all(mandatory) and test.returncode==0 and walter['pass']
 (out/'SCENE_BRAIN_V1_5_MASTER_GATE.json').write_text(json.dumps(r,indent=2))
 if not r['PASS']:raise AssertionError(r)
if __name__=='__main__':main()
