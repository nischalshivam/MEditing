from __future__ import annotations
import json,re,shutil,subprocess
from difflib import SequenceMatcher
from pathlib import Path
from .hashing import sha256_file

WORD=re.compile(r"[A-Za-z0-9']+")
def norm(s):return [x.lower() for x in WORD.findall(s)]
def atomic(p,o):p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.building.json');q.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf8');q.replace(p)

def import_and_align(root:Path,media:Path,supplied:Path):
 project=media/'.scene_brain/projects/walter_book_project';managed=project/'voiceover'/supplied.name;managed.parent.mkdir(parents=True,exist_ok=True)
 if not managed.exists() or sha256_file(managed)!=sha256_file(supplied):shutil.copy2(supplied,managed)
 probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,sample_rate,channels','-of','json',str(managed)],capture_output=True,text=True,check=True).stdout);duration=round(float(probe['format']['duration'])*1000)
 cache=project/'voiceover/ASR_WORDS.json'
 if cache.exists():words=json.loads(cache.read_text())['words']
 else:
  from faster_whisper import WhisperModel
  snapshots=Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots';available=next((x for x in snapshots.glob('*') if (x/'model.bin').exists() and (x/'tokenizer.json').exists()),None)
  model=WhisperModel(str(available) if available else 'base.en',device='cpu',compute_type='int8',local_files_only=bool(available));segments,_=model.transcribe(str(managed),language='en',word_timestamps=True,vad_filter=True)
  words=[{'token':w.word.strip(),'start_ms':round(w.start*1000),'end_ms':round(w.end*1000),'probability':w.probability} for s in segments for w in (s.words or []) if w.word.strip()]
  atomic(cache,{'version':'walter-asr-words/1.0','voiceover_sha256':sha256_file(managed),'words':words})
 clue=json.loads((root/'runtime/new_project_book_test/VALIDATED_CLUE_SCRIPT.json').read_text());clean=[];spans=[]
 for b in clue['beats']:
  start=len(clean);clean+=norm(b['exact_narration']);spans.append((b['beat_id'],start,len(clean),b['exact_narration']))
 aw=[];aw_to_word=[]
 for wi,w in enumerate(words):
  for token in norm(w['token']):aw.append(token);aw_to_word.append(wi)
 mapping={};sm=SequenceMatcher(None,clean,aw,autojunk=False)
 for block in sm.get_matching_blocks():
  for k in range(block.size):mapping[block.a+k]=aw_to_word[block.b+k]
 anchors=sorted(mapping);aligned=[]
 for beat_id,a,b,text in spans:
  direct=[mapping[i] for i in range(a,b) if i in mapping]
  if direct:start=words[min(direct)]['start_ms'];end=words[max(direct)]['end_ms']
  else:
   lo=max((i for i in anchors if i<a),default=None);hi=min((i for i in anchors if i>=b),default=None)
   if lo is None or hi is None:raise RuntimeError(f'unaligned beat {beat_id}')
   start=words[mapping[lo]]['end_ms'];end=words[mapping[hi]]['start_ms']
  aligned.append({'beat_id':beat_id,'exact_narration':text,'voice_start_ms':start,'voice_end_ms':end,'direct_words':len(direct),'expected_words':b-a,'confidence':len(direct)/max(1,b-a)})
 aligned[0]['voice_start_ms']=0
 for i in range(len(aligned)-1):aligned[i]['voice_end_ms']=aligned[i+1]['voice_start_ms']
 aligned[-1]['voice_end_ms']=duration
 state_path=project/'EDITOR_PROJECT.json';state=json.loads(state_path.read_text());bybeat={x['beat_id']:[] for x in aligned}
 for slot in state['timeline']:bybeat.setdefault(slot['beat_id'],[]).append(slot)
 for beat in aligned:
  slots=bybeat[beat['beat_id']];start,end=beat['voice_start_ms'],beat['voice_end_ms'];weights=[max(1,x['timeline_end_ms']-x['timeline_start_ms']) for x in slots];total=sum(weights);cursor=start
  for i,(slot,w) in enumerate(zip(slots,weights)):
   nxt=end if i==len(slots)-1 else cursor+round((end-start)*w/total);slot['timeline_start_ms']=cursor;slot['timeline_end_ms']=nxt;slot['timing_authority']='FINAL_VOICEOVER_ALIGNED';cursor=nxt
 state.update({'voiceover_path':str(managed),'voiceover_sha256':sha256_file(managed),'voiceover_duration_ms':duration,'voiceover_metadata':probe,'beat_alignment_path':str(project/'voiceover/BEAT_ALIGNMENT.json'),'timing_status':'FINAL_VOICEOVER_ALIGNED'})
 atomic(project/'voiceover/BEAT_ALIGNMENT.json',{'version':'walter-beat-alignment/1.0','voiceover_sha256':sha256_file(managed),'duration_ms':duration,'beats':aligned});atomic(state_path,state)
 atomic(project/'voiceover/VOICEOVER_IMPORT_RECEIPT.json',{'version':'walter-voiceover-import/1.0','supplied_path':str(supplied),'managed_path':str(managed),'voiceover_sha256':sha256_file(managed),'duration_ms':duration,'beats_aligned':len(aligned),'slots_timed':len(state['timeline']),'retrieval_reruns':0,'rich_builds':0,'cloud_cost_usd':0})
 return state,aligned
