from __future__ import annotations

import json,math,re,subprocess
from pathlib import Path

from .hashing import fingerprint
from .moment_resolver_v2 import generate_v2
from .resolver import terms,vector,cosine
from .retrieval_contract_v3 import StructuredVisualRequest,normalize_request,region_discovery_allowed,SYNONYMS
from .shot_models import ShotRange,ShotRequest
from .recovery_v7 import recovery_candidates

VERSION='candidate-reranker/3.0'
WEIGHTS={'entity':.16,'action':.25,'object':.12,'relation':.08,'temporal':.12,'evidence':.12,'dialogue':.05,'motion':.04,'semantic':.06}

def _candidate_text(c):return ' '.join(str(p.get('text') or p.get('trigger') or '') for p in c.provenance)
def _support(text,needle):return 0 if not needle else min(1,len(terms(text)&terms(needle))/max(1,len(terms(needle))))
def _action_score(text,s):
    if not s.action_family:return 0
    variants=SYNONYMS.get(s.action_family,{s.action_family});return 1.0 if any(re.search(r'\b'+re.escape(x)+r'\b',text.lower()) for x in variants|{s.action_family}) else _support(text,s.action_family)*.5
def _temporal(c,s):
    lane=c.provenance[0].get('lane');score=.7 if s.action_family in {'leave','enter','transfer','pickup','putdown','turn','react'} and lane in {'ENTER_LEAVE','REACTION','ACTION','OBJECT_ACTION'} else .25
    if s.temporal_relation and lane=='REACTION':score=1
    return score
def _motion(source,c):
    # Inexpensive bounded signal: mean scene-cut/motion activity from 4 grayscale samples.
    try:
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{c.start_ms/1000:.3f}','-i',source,'-t',f'{(c.end_ms-c.start_ms)/1000:.3f}','-vf','fps=2,scale=64:36,format=gray','-f','rawvideo','-']
        b=subprocess.run(cmd,capture_output=True,check=True,timeout=8).stdout;size=64*36;frames=[b[i:i+size] for i in range(0,len(b),size) if len(b[i:i+size])==size]
        if len(frames)<2:return 0
        return min(1,sum(sum(abs(a-b) for a,b in zip(frames[i-1],frames[i]))/size/255 for i in range(1,len(frames)))/(len(frames)-1)*5)
    except Exception:return 0

def rerank_v3(conn,req:ShotRequest,with_motion=False,include_recovery=False):
    if not region_discovery_allowed(req):return [],normalize_request(req)
    s=normalize_request(req);base=generate_v2(conn,req);recovered,recovery_counts=recovery_candidates(conn,req) if include_recovery else ([],{}) ;candidates=[];seen=set()
    for c in [*base,*recovered]:
        key=(c.start_ms,c.end_ms)
        if key not in seen:candidates.append(c);seen.add(key)
    source=conn.execute('select path from source_files where id=1').fetchone()[0];q=' '.join(s.normalized_terms);ranked=[]
    for c in candidates:
        text=_candidate_text(c);prov=c.provenance;lane=prov[0].get('lane');entities=' '.join(x for x in [s.required_subject,s.secondary_subject,s.reaction_subject] if x)
        scores={'entity':_support(text,entities),'action':_action_score(text,s),'object':_support(text,s.object),'relation':min(_support(text,s.secondary_subject)+_support(text,s.object),1),'temporal':_temporal(c,s),'evidence':min(1,.35+.15*sum(bool(p.get('evidence_shots')) for p in prov)+.2*(lane!='COVERAGE')),'dialogue':1 if lane=='DIALOGUE' else 0,'motion':_motion(source,c) if with_motion else (.55 if lane in {'ACTION','ENTER_LEAVE','REACTION','OBJECT_ACTION'} else .2),'semantic':cosine(vector(q),vector(text)) if text else 0}
        score=sum(WEIGHTS[k]*scores[k] for k in WEIGHTS)+.05*c.local_score
        ranked.append((score,c,scores))
    ranked.sort(key=lambda x:(-x[0],x[1].start_ms))
    # Diversity: max two strongly-overlapping hypotheses; fill to 24.
    out=[]
    for score,c,scores in ranked:
        overlaps=sum(max(0,min(c.end_ms,x.end_ms)-max(c.start_ms,x.start_ms))/max(1,min(c.end_ms-c.start_ms,x.end_ms-x.start_ms))>.65 for x in out)
        if overlaps>=2:continue
        c.local_score=round(score,6);c.provenance.insert(0,{'lane':'V3_RERANK','component_scores':scores,'structured_request':s.model_dump(),'recovery_counts':recovery_counts});out.append(c)
        if len(out)>=24:break
    for i,c in enumerate(out,1):c.candidate_id=f'V3_{i:02d}'
    return out,s
