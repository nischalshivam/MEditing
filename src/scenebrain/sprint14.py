from __future__ import annotations
import json,re,subprocess,time,statistics
from difflib import SequenceMatcher
from pathlib import Path
from .hashing import sha256_file,fingerprint

WORD=re.compile(r"[A-Za-z0-9']+")
def norm(s): return [x.lower().replace("’","'") for x in WORD.findall(s)]
def write(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf8')

def align(root:Path,wav:Path,script:Path):
 out=root/'runtime/sprint14_voiceover';asr=json.loads((out/'ASR_WORDS_RAW.json').read_text());clean=script.read_text(encoding='utf-8-sig');cw=norm(clean);aw=[norm(x['token'])[0] for x in asr['words'] if norm(x['token'])]
 sm=SequenceMatcher(None,cw,aw,autojunk=False);mapping={}
 for b in sm.get_matching_blocks():
  for k in range(b.size):mapping[b.a+k]=b.b+k
 anchors=sorted(mapping);times=[]
 for i in range(len(cw)):
  if i in mapping:
   w=asr['words'][mapping[i]];times.append({'word_index':i,'word':cw[i],'start_ms':w['start_ms'],'end_ms':w['end_ms'],'support':'DIRECT'})
  else:
   lo=max((x for x in anchors if x<i),default=None);hi=min((x for x in anchors if x>i),default=None)
   if lo is not None and hi is not None and hi-lo<=12:
    a=asr['words'][mapping[lo]]['end_ms'];b=asr['words'][mapping[hi]]['start_ms'];f=(i-lo)/(hi-lo);t=round(a+(b-a)*f);times.append({'word_index':i,'word':cw[i],'start_ms':t,'end_ms':t+max(20,(b-a)//max(1,hi-lo)),'support':'LOCAL_INTERPOLATION'})
   else:times.append({'word_index':i,'word':cw[i],'start_ms':None,'end_ms':None,'support':'UNALIGNED'})
 final=json.loads((root/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json').read_text());bybeat={x['beat_id']:x for x in final['slots']};manual=json.loads((root/'runtime/final_project/MANUAL_REPLACEMENT_QUEUE.json').read_text());manualids={x['beat_id'] for x in manual['items']}
 clue=json.loads((Path.home()/'Downloads/Skyler/SKYLER_MONEY_CLUE_SCRIPT_V1.json').read_text(encoding='utf-8-sig'))
 cursor=0;beats=[]
 for b in clue['beats']:
  n=len(norm(b['exact_narration']));seg=times[cursor:cursor+n];valid=[x for x in seg if x['start_ms'] is not None];direct=sum(x['support']=='DIRECT' for x in seg);conf=direct/max(1,n)
  start=valid[0]['start_ms'] if valid else None;end=valid[-1]['end_ms'] if valid else None;status='ALIGNED_HIGH' if conf>=.9 else ('ALIGNED_MEDIUM' if conf>=.75 else ('REVIEW_ALIGNMENT' if valid else 'UNALIGNED'))
  beats.append({'beat_id':b['beat_id'],'exact_narration':b['exact_narration'],'voice_start_ms':start,'voice_end_ms':end,'alignment_confidence':conf,'aligned_word_count':len(valid),'expected_word_count':n,'direct_word_count':direct,'alignment_status':status,'manual':b['beat_id'] in manualids});cursor+=n
 word={'version':'voiceover-alignment-v1','clean_script_sha256':sha256_file(script),'voiceover_sha256':sha256_file(wav),'clean_script_words':len(cw),'asr_words':len(aw),'matched_direct':len(mapping),'mapped_total':sum(x['start_ms'] is not None for x in times),'words':times};write(out/'WORD_ALIGNMENT.json',word);write(out/'BEAT_ALIGNMENT.json',{'version':'beat-alignment-v1','beats':beats})
 return word,beats,final,bybeat

def compose(root:Path,wav:Path,script:Path):
 t=time.time();out=root/'runtime/sprint14_voiceover';word,beats,final,locked=align(root,wav,script);out.joinpath('images').mkdir(exist_ok=True);slots=[];variants=[]
 for bi,b in enumerate(beats):
  start=0 if bi==0 else b['voice_start_ms'];end=(beats[bi+1]['voice_start_ms'] if bi+1<len(beats) and beats[bi+1]['voice_start_ms'] is not None else 887300)
  if start is None or end is None or end<=start:continue
  if b['manual']:
   slots.append({'presentation_slot_id':f"{b['beat_id']}_P01",'beat_id':b['beat_id'],'timeline_start_ms':start,'timeline_end_ms':end,'exact_narration':b['exact_narration'],'source_lock_slot_id':b['beat_id']+'_VS01','locked_asset_id':None,'presentation_type':'MANUAL_PLACEHOLDER','source_path':None,'source_hash':None,'source_in_ms':None,'source_out_ms':None,'frame_time_ms':None,'derived_asset_path':None,'approval_state':'MANUAL_FIX','provenance':['MANUAL_REPLACEMENT_REQUIRED']});continue
  x=locked[b['beat_id']];a=x['chosen_asset'];dur=end-start
  natural=max(0,(a.get('source_out_ms') or 0)-(a.get('source_in_ms') or 0))
  video_ms=min(natural,max(2500,round(dur*.60))) if a['media_type']=='VIDEO' else 0
  parts=[]
  if video_ms: parts.append(('VIDEO',start,start+video_ms))
  if start+video_ms<end: parts.append(('IMAGE',start+video_ms,end))
  if not parts:parts=[('IMAGE',start,end)]
  for pi,(typ,ts,te) in enumerate(parts,1):
   frame=a.get('frame_time_ms') or ((a.get('source_in_ms') or 0)+(a.get('source_out_ms') or 0))//2;derived=None
   if typ=='IMAGE':
    derived=out/'images'/f"{a['asset_id']}_{frame}.jpg"
    if not derived.exists():subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',f'{frame/1000:.3f}','-i',a['source_path'],'-frames:v','1','-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2','-q:v','2','-y',str(derived)],check=True)
   row={'presentation_slot_id':f"{b['beat_id']}_P{pi:02d}",'beat_id':b['beat_id'],'timeline_start_ms':ts,'timeline_end_ms':te,'exact_narration':b['exact_narration'],'source_lock_slot_id':x['slot_id'],'locked_asset_id':a['asset_id'],'presentation_type':typ,'source_path':a['source_path'],'source_hash':a['source_hash'],'source_in_ms':a.get('source_in_ms'),'source_out_ms':a.get('source_out_ms'),'frame_time_ms':frame if typ=='IMAGE' else None,'derived_asset_path':str(derived.resolve()) if derived else None,'approval_state':'APPROVED','provenance':['PROJECT_SLOT_APPROVAL',f'DERIVED_FROM_LOCKED_ASSET:{a["asset_id"]}']};slots.append(row);variants.append(row)
 timeline={'version':'timeline-plan/1.0','voiceover_path':str(wav),'voiceover_sha256':sha256_file(wav),'duration_ms':887300,'presentation_slots':slots,'manual_slots':['B002_VS01','B022_VS01'],'frozen_retrieval_plan_sha256':sha256_file(root/'runtime/final_project/FINAL_LOCKED_VISUAL_PLAN.json')};timeline['fingerprint']=fingerprint(json.dumps(timeline,sort_keys=True));write(out/'TIMELINE_PLAN.json',timeline);write(out/'PRESENTATION_VARIANTS.json',{'version':'presentation-variants/1.0','variants':variants})
 return word,beats,timeline,time.time()-t
