"""Scene Brain V1.5 production intelligence contracts.

All optional intelligence returns evidence; only ``CandidateRanker`` and
``ConfidenceGate`` make project decisions.  The module is deliberately local,
source-bound and project-independent.
"""
from __future__ import annotations
import hashlib, json, re, sqlite3, time
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VERSIONS={"project_planner_version":"1.5.0","clue_compiler_version":"4.0.0","character_index_version":"1.0.0","scene_atlas_version":"2.0","candidate_ranker_version":"1.5.0","gemini_verifier_version":"bounded-1.0","presentation_planner_version":"1.5.0","editor_version":"researchcut-2.1"}
FEATURE_FLAGS={"character_recognition":False,"gemini_visual_reranker":False,"editorial_memory":True,"presentation_auto_fill":"CONSERVATIVE"}

def digest(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

class ProjectManifestStore:
 """Canonical SQLite project truth; JSON remains export/receipt only."""
 def __init__(self,db:Path):self.db=db;self.db.parent.mkdir(parents=True,exist_ok=True);self._init()
 def _con(self):c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
 def _init(self):
  with closing(self._con()) as c,c:c.execute("create table if not exists project_manifest(project_id text primary key,state_json text not null,state_hash text not null,updated_at real not null)")
 def save(self,project_id:str,state:dict):
  payload=json.dumps(state,sort_keys=True);h=hashlib.sha256(payload.encode()).hexdigest()
  with closing(self._con()) as c,c:c.execute("insert into project_manifest values(?,?,?,?) on conflict(project_id) do update set state_json=excluded.state_json,state_hash=excluded.state_hash,updated_at=excluded.updated_at",(project_id,payload,h,time.time()))
  return h
 def load(self,project_id):
  with closing(self._con()) as c,c:r=c.execute("select * from project_manifest where project_id=?",(project_id,)).fetchone()
  return {"state":json.loads(r['state_json']),"state_hash":r['state_hash']} if r else None

@dataclass
class VisualRequirement:
 id:str; evidence_class:str="EDITORIAL_CONTEXT"; narration:str=""; canonical_event_id:str|None=None
 primary_subjects:list[str]=field(default_factory=list);secondary_subjects:list[str]=field(default_factory=list)
 character_presence_requirements:dict[str,str]=field(default_factory=dict);face_visibility_requirements:list[str]=field(default_factory=list)
 required_action:str|None=None;required_objects:list[str]=field(default_factory=list);location_requirement:str|None=None
 dialogue_requirement:str|None=None;required_visible_facts:list[str]=field(default_factory=list);negative_visible_facts:list[str]=field(default_factory=list)
 media_preference:str="EITHER";safe_context_fallback:bool=True;episode_hint:str|None=None

class ProjectPlanner:
 """Cheap preflight: never starts retrieval, Rich builds or AI."""
 def analyze(self,name:str,script:str,clue:dict|None=None,voiceover_seconds:float|None=None)->dict:
  clue=clue or {}; words=re.findall(r"[A-Za-z][A-Za-z'-]*",script)
  # Proper names are candidate evidence, not cast truth.
  names=[]
  for x in re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",script):
   if x not in names and x.lower() not in {"the","this","that","when","if","but","and"}:names.append(x)
  counts={n:len(re.findall(rf"\b{re.escape(n)}\b",script,re.I)) for n in names}
  chars=[]
  for i,(n,c) in enumerate(sorted(counts.items(),key=lambda x:-x[1])):
   chars.append({"character":n,"role_in_video":"PRIMARY" if i==0 else "SUPPORT","mention_density":c/max(1,len(words)),"visual_importance":"CHARACTER_PREFERRED","gallery_readiness":"MISSING_NON_BLOCKING"})
  requirements=clue.get("visual_requirements") or clue.get("beats") or []
  conflicts=[]
  for r in requirements:
   hard=set(r.get("face_visibility_requirements",[])); inferred={n for n in names if n.lower() in str(r.get("narration",r.get("text",""))).lower()}
   for n in hard-inferred: conflicts.append({"type":"CLUE_SCRIPT_CONFLICT","clue_constraint":f"FACE_REQUIRED:{n}","script_inference":"not supported","final_constraint":"CHARACTER_PREFERRED","resolution_reason":"hard face constraint lacks independent script support"})
  return {"project_name":name,"word_count":len(words),"voiceover_duration":voiceover_seconds,"estimated_semantic_beats":max(1,round(len(words)/35)),"estimated_canonical_events":len({r.get('canonical_event_id') for r in requirements if r.get('canonical_event_id')}),"estimated_visual_opportunities":max(1,round(len(words)/24)),"characters":chars,"clue_conflicts":conflicts,"versions":VERSIONS,"analysis_hash":digest([script,clue,voiceover_seconds])}

class QueryCompiler:
 def compile(self,r:VisualRequirement)->dict:
  return {"requirement_id":r.id,"text_lane":{"dialogue":r.dialogue_requirement,"terms":re.findall(r"\w+",r.narration.lower())},"character_lane":{"required":[x for x,v in r.character_presence_requirements.items() if v in ('FACE_REQUIRED','CHARACTER_REQUIRED')],"preferred":r.primary_subjects+r.secondary_subjects,"excluded":[x for x,v in r.character_presence_requirements.items() if v=='CHARACTER_EXCLUDED']},"object_lane":r.required_objects,"action_lane":r.required_action,"source_lane":{"episode_hint":r.episode_hint,"canonical_event":r.canonical_event_id},"visual_lane":{"class":r.evidence_class,"media":r.media_preference,"facts":r.required_visible_facts,"negative":r.negative_visible_facts}}

class CharacterGallery:
 def __init__(self,db:Path):
  self.db=db; self._init()
 def _con(self):c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
 def _init(self):
  self.db.parent.mkdir(parents=True,exist_ok=True)
  with closing(self._con()) as c, c:c.executescript("create table if not exists character_references(title_id text,character_id text,path text,hash text,trusted integer,provenance text,primary key(title_id,character_id,hash));create table if not exists character_observations(source_hash text,frame_id text,shot_id text,scene_id text,character_id text,score real,status text,plugin_version text,primary key(source_hash,frame_id,character_id));")
 def add_reference(self,title_id,character_id,path:Path,trusted=False,provenance="HUMAN"):
  h=hashlib.sha256(path.read_bytes()).hexdigest()
  with closing(self._con()) as c, c:c.execute("insert or ignore into character_references values(?,?,?,?,?,?)",(title_id,character_id,str(path),h,int(trusted),provenance))
 def readiness(self,title_id,character_id):
  with closing(self._con()) as c, c:n=c.execute("select count(*) from character_references where title_id=? and character_id=? and trusted=1",(title_id,character_id)).fetchone()[0]
  return {"references":n,"status":"READY" if n>=10 else "PARTIAL" if n else "MISSING","blocking":False}
 def available(self):
  try:import cv2;return all(hasattr(cv2,x) for x in ('FaceDetectorYN_create','FaceRecognizerSF_create'))
  except Exception:return False

class CharacterEvidencePlugin:
 """Optional YuNet/SFace adapter. It never forces nearest-neighbour identity."""
 def __init__(self,gallery:CharacterGallery,detector_model:Path|None=None,recognizer_model:Path|None=None,threshold:float=.55):
  self.gallery=gallery;self.detector_model=detector_model;self.recognizer_model=recognizer_model;self.threshold=threshold
 def readiness(self):return {"enabled":bool(self.detector_model and self.recognizer_model and self.gallery.available() and self.detector_model.exists() and self.recognizer_model.exists()),"fallback":"UNKNOWN"}
 def classify_scores(self,scores:dict[str,float]):
  if not scores:return {"status":"UNKNOWN","character_id":None,"score":0.0}
  who,score=max(scores.items(),key=lambda x:x[1])
  if score<self.threshold:return {"status":"UNKNOWN","character_id":None,"score":score}
  return {"status":"KNOWN_CHARACTER","character_id":who,"score":score}

class EditorialMemory:
 def __init__(self,db:Path):self.db=db;self._init()
 def _con(self):c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
 def _init(self):
  self.db.parent.mkdir(parents=True,exist_ok=True)
  with closing(self._con()) as c, c:c.executescript("create table if not exists editorial_decisions(id integer primary key,project_id text,title_id text,query_hash text,event_id text,candidate_id text,scene_id text,shot_ids text,decision text,approval_type text,features text,created_at real);create index if not exists idx_memory_query on editorial_decisions(title_id,query_hash,decision);")
 def record(self,project_id,title_id,query,event_id,candidates,accepted_id,approval_type="PROJECT_SLOT_APPROVAL"):
  q=digest(query)
  with closing(self._con()) as c, c:
   for x in candidates:
    c.execute("insert into editorial_decisions(project_id,title_id,query_hash,event_id,candidate_id,scene_id,shot_ids,decision,approval_type,features,created_at) values(?,?,?,?,?,?,?,?,?,?,?)",(project_id,title_id,q,event_id,x['id'],x.get('scene_id'),json.dumps(x.get('shot_ids',[])),"ACCEPTED" if x['id']==accepted_id else "REJECTED",approval_type,json.dumps(x.get('evidence',{}),sort_keys=True),time.time()))
 def evidence(self,title_id,query):
  with closing(self._con()) as c, c:rows=c.execute("select * from editorial_decisions where title_id=? and query_hash=? order by created_at desc",(title_id,digest(query))).fetchall()
  return [{**dict(r),"source":"HISTORICAL_HUMAN_EVIDENCE"} for r in rows]
 def metrics(self,title_id):
  with closing(self._con()) as c, c:
   n=c.execute("select count(*) from editorial_decisions where title_id=?",(title_id,)).fetchone()[0];a=c.execute("select count(*) from editorial_decisions where title_id=? and decision='ACCEPTED'",(title_id,)).fetchone()[0]
  return {"decisions":n,"accepted":a}

class AICacheBudget:
 def __init__(self,db:Path,budget_usd:float):self.db=db;self.budget=budget_usd;self._init()
 def _con(self):c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
 def _init(self):
  self.db.parent.mkdir(parents=True,exist_ok=True)
  with closing(self._con()) as c, c:c.execute("create table if not exists ai_cache(input_hash text primary key,source_hash text,candidate_hash text,prompt_version text,provider text,model text,input_tokens integer,output_tokens integer,cost real,result_json text,result_hash text,created_at real)")
 def spent(self):
  with closing(self._con()) as c, c:return float(c.execute("select coalesce(sum(cost),0) from ai_cache").fetchone()[0])
 def get(self,key):
  with closing(self._con()) as c, c:r=c.execute("select result_json from ai_cache where input_hash=?",(key,)).fetchone()
  return json.loads(r[0]) if r else None
 def put(self,key,meta,result,cost):
  if self.spent()+cost>self.budget:raise RuntimeError("AI_BUDGET_REACHED")
  with closing(self._con()) as c, c:c.execute("insert or replace into ai_cache values(?,?,?,?,?,?,?,?,?,?,?,?)",(key,meta['source_hash'],meta['candidate_hash'],meta['prompt_version'],meta['provider'],meta['model'],meta.get('input_tokens',0),meta.get('output_tokens',0),cost,json.dumps(result),digest(result),time.time()))

class CandidateRanker:
 DEFAULT={"memory":3.0,"dialogue":2.4,"character":2.0,"object":1.7,"action":2.2,"scene_semantic":1.4,"gemini":2.5,"reuse_penalty":-2.0}
 def __init__(self,weights=None):self.weights={**self.DEFAULT,**(weights or {})}
 def rank(self,candidates):
  for x in candidates:
   e=x.setdefault('evidence',{});x['rank_score']=sum(self.weights.get(k,0)*float(e.get(k,0)) for k in self.weights);x['why_this']=[f"{k}: {e.get(k)}" for k in self.weights if e.get(k)]
  return sorted(candidates,key=lambda x:(-x['rank_score'],x['id']))

class ConfidenceGate:
 def decide(self,ranked):
  if not ranked:return {"state":"MANUAL_REQUIRED","reason":"no grounded candidates"}
  top=ranked[0];score=top['rank_score'];sep=score-(ranked[1]['rank_score'] if len(ranked)>1 else 0)
  if score>=6 and sep>=1:return {"state":"AUTO","candidate_id":top['id']}
  if score>=2:return {"state":"OPTIONS","candidate_ids":[x['id'] for x in ranked[:3]]}
  return {"state":"MANUAL_REQUIRED","reason":"weak or ambiguous evidence"}

class PresentationQualityGate:
 def validate(self,clips):
  scenes={};ranges=set();dupes=0;fake=0
  ordered=sorted([c for c in clips if c.get('kind','video')=='video'],key=lambda x:x['start'])
  for c in ordered:
   scene=c.get('scene_id');scenes[scene]=scenes.get(scene,0)+1 if scene else 0
   key=(c.get('source_hash'),round(c.get('source_in',0),1),round(c.get('source_in',0)+c['duration'],1));dupes+=key in ranges;ranges.add(key)
  for a,b in zip(ordered,ordered[1:]):
   if a.get('source_hash')==b.get('source_hash') and a.get('scene_id')==b.get('scene_id') and abs(a.get('source_in',0)+a['duration']-b.get('source_in',0))<.05:fake+=1
  failures=[]
  if any(c['duration']>10 for c in ordered):failures.append('VIDEO_OVER_10_SECONDS')
  if max(scenes.values(),default=0)>2:failures.append('SCENE_USED_OVER_TWICE')
  if dupes:failures.append('DUPLICATE_SOURCE_RANGE')
  if fake:failures.append('FAKE_SEQUENTIAL_SLICING')
  return {"pass":not failures,"failures":failures,"fake_slicing_count":fake,"duplicate_clip_count":dupes,"max_scene_reuse":max(scenes.values(),default=0),"max_video_duration":max([c['duration'] for c in ordered],default=0)}

class JobStore:
 def __init__(self,db:Path):self.db=db;self._init()
 def _con(self):c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
 def _init(self):
  self.db.parent.mkdir(parents=True,exist_ok=True)
  with closing(self._con()) as c, c:c.execute("create table if not exists jobs(job_id text primary key,project_id text,stage text,substage text,work_item text,status text,error_code text,started real,finished real)")
 def update(self,job_id,project_id,stage,status,substage='',work_item='',error_code=None):
  now=time.time()
  with closing(self._con()) as c, c:c.execute("insert into jobs values(?,?,?,?,?,?,?,?,?) on conflict(job_id) do update set stage=excluded.stage,substage=excluded.substage,work_item=excluded.work_item,status=excluded.status,error_code=excluded.error_code,finished=excluded.finished",(job_id,project_id,stage,substage,work_item,status,error_code,now,now if status in ('COMPLETE','FAILED') else None))
 def report(self,project_id):
  with closing(self._con()) as c, c:rows=[dict(x) for x in c.execute("select * from jobs where project_id=? order by started",(project_id,))]
  return {"project_id":project_id,"jobs":rows,"health":"ERROR" if any(x['status']=='FAILED' for x in rows) else "READY" if rows and all(x['status']=='COMPLETE' for x in rows) else "PREPARING"}
