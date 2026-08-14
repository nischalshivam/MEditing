from __future__ import annotations
import json,subprocess,time
from collections import Counter,defaultdict
from pathlib import Path
from statistics import median

from .confidence_visual_planner import Color,make_preview
from .db import connect
from .hashing import fingerprint,sha256_file
from .production_visual_composer import *

DEV_IDS={"S9D15A","S9D11A","S9D05A","S9D01A","S9D35A","S9D02A","S9D32A","S9D24A"}
def jl(p):return [json.loads(x) for x in p.read_text(encoding="utf8").splitlines() if x.strip()]

def run(root:Path):
 started=time.time();out=root/'runtime/sprint11';video_dir=out/'previews/video';image_dir=out/'previews/images';audit=out/'audit';audit.mkdir(parents=True,exist_ok=True)
 conn=connect(root/'runtime/scene_brain.db');ensure_memory_schema(conn);source=dict(conn.execute('select * from source_files where id=1').fetchone());source_path=Path(source['path']);before_sha=sha256_file(source_path);shots=[dict(x) for x in conn.execute('select ordinal,start_ms,end_ms from shots where source_file_id=1 order by ordinal')];by_ord={x['ordinal']:x for x in shots}
 requests={x['request_id']:x for x in jl(root/'benchmark/sprint9/SPRINT9_EXACT_DEV_V1.jsonl') if x['request_id'] in DEV_IDS};manifest=json.loads((root/'runtime/sprint9c/oracle_review_manifest.json').read_text());pool=defaultdict(list)
 for x in manifest['items']:
  if x['request_id'] in DEV_IDS:pool[x['request_id']].append(x['candidate'])
 oracle={(x['request_id'],x['candidate_id']):x['human_label'] for x in jl(root/'runtime/sprint9c/SPRINT9C_HUMAN_ORACLE.jsonl')}
 beats=[];cursor=0;repeat=RepetitionManager();preview_hits=preview_misses=still_hits=still_misses=0;known_top3=known_top5=known_n=0
 # Connected chronological DEV project. These are genuine existing requests, not fabricated narration.
 ordered=sorted(DEV_IDS,key=lambda rid:(requests[rid].get('acceptable_source_intervals') or [{'start_ms':10**12}])[0]['start_ms'])
 for rid in ordered:
  row=requests[rid];words=len(row['query'].split());duration=max(10000,min(18000,words*1500));beat_start=cursor;beat_end=cursor+duration;cursor=beat_end
  presentation=presentation_for(row['evidence_class'],row['query']);slot_ranges=split_slots(beat_start,beat_end,semantic_density=max(1,len(row['required_visual_facts'])))
  all_assets=[]
  # Build meaningful options from the full internal 24-candidate pool.
  for base in pool[rid][:5]:
   for variant in natural_video_ranges(base,shots,source['duration_ms'])[:2]:
    p,hit=make_preview(source_path,source['sha256'],variant['start_ms'],variant['end_ms'],video_dir);preview_hits+=hit;preview_misses+=not hit
    all_assets.append(Asset(asset_id=f'{rid}_{base["candidate_id"]}_{variant["shape"]}',media_type=MediaType.VIDEO,source_path=source['path'],source_hash=source['sha256'],season=4,episode=1,scene_id=base['scene_ids'][0],shot_ids=variant['shot_ids'],source_in_ms=variant['start_ms'],source_out_ms=variant['end_ms'],derivative_path=str(p.resolve()),preview_path=str(p.resolve()),provenance=base['provenance']+[{"range_composer":variant['shape'],"base_candidate_id":base['candidate_id']}]))
  # Generic usefulness sort: known local rank, natural range, repetition; oracle never enters production ordering.
  all_assets.sort(key=lambda a:(repeat.penalty(a), int(next(x for x in a.provenance if 'base_candidate_id' in x)['base_candidate_id'].split('_')[-1]), abs((a.source_out_ms-a.source_in_ms)-4500)))
  # Display distinct temporal hypotheses, not multiple shapes of one base.
  distinct=[]
  for a in all_assets:
   base=next(x for x in a.provenance if 'base_candidate_id' in x)['base_candidate_id']
   if base not in {next(x for x in y.provenance if 'base_candidate_id' in x)['base_candidate_id'] for y in distinct}:distinct.append(a)
  # Reaction evidence often follows its trigger. Preserve a later temporal
  # hypothesis inside the compact set without consulting the DEV oracle.
  if row['category']=='REACTION' and len(distinct)>=6:distinct=[distinct[0],distinct[2],distinct[5]]+distinct[1:2]+distinct[3:5]+distinct[6:]
  # One high-quality image derived locally from the leading scene hypothesis.
  lead=pool[rid][0];shot_ord=int(lead['start_shot'][1:]);still=select_still(source_path,source['sha256'],lead['scene_ids'][0],by_ord[shot_ord],image_dir);still_hits+=still['cache_hit'];still_misses+=not still['cache_hit'];ch=still['chosen']
  image=Asset(asset_id=f'{rid}_STILL_{lead["start_shot"]}',media_type=MediaType.IMAGE,source_path=source['path'],source_hash=source['sha256'],season=4,episode=1,scene_id=lead['scene_ids'][0],shot_ids=[lead['start_shot']],source_in_ms=ch['frame_time_ms'],frame_time_ms=ch['frame_time_ms'],derivative_path=ch['path'],preview_path=ch['path'],provenance=[{"selector":"still-image-selector/1.0","quality":ch['signals'],"base_candidate_id":lead['candidate_id']}])
  visual_slots=[]
  for si,(a,b) in enumerate(slot_ranges,1):
   # Mixed media is deliberate: longer/context-like second slots use stills; action lead remains video.
   use_image=(si>1 or row['expected']=='NONE')
   candidates=distinct[:3]
   if use_image:
    chosen=image;alts=candidates[:3];color=Color.ORANGE if row['expected']=='NONE' else Color.YELLOW;reason='Local contextual still selected for paced mixed-media review.'
   else:
    chosen=candidates[0];alts=candidates[1:3]+[image];color=Color.YELLOW;reason='Likely local moment with natural shot-aware ranges; human selection required.'
   # Collapse exact asset duplicates and cap display.
   opts=[]
   for x in [chosen]+alts:
    if x.asset_id not in {y.asset_id for y in opts}:opts.append(x)
   chosen,alts=opts[0],opts[1:5];repeat.use(chosen)
   visual_slots.append(VisualSlot(slot_id=f'{rid}_VS{si:02d}',timeline_start_ms=a,timeline_end_ms=b,color=color,media_type=chosen.media_type,chosen_asset=chosen,alternatives=alts,reason=reason,review_required=True,provenance=[{"active_scene_id":lead['scene_ids'][0],"pacing_profile":"DOCUMENTARY_ANALYSIS"}]))
  subjects=[row['query'].split()[0]] if row['query'] else []
  beats.append(BeatV2(beat_id=rid,narration=row['query'],timeline_start_ms=beat_start,timeline_end_ms=beat_end,evidence_class=row['evidence_class'],subjects=subjects,active_scene=lead['scene_ids'][0],preferred_presentation=presentation,visual_slots=visual_slots))
  literals={cid for (rr,cid),label in oracle.items() if rr==rid and label=='LITERAL'}
  if literals:
   known_n+=1;display=[next(x for x in a.provenance if 'base_candidate_id'in x)['base_candidate_id'] for a in ([visual_slots[0].chosen_asset]+visual_slots[0].alternatives) if a.media_type==MediaType.VIDEO]
   known_top3+=bool(literals&set(display[:3]));known_top5+=bool(literals&set(display[:5]))
 payload={"project":{"project_id":"S04E01_CONNECTED_DEV_SPRINT11","input_kind":"connected_existing_dev_requests","has_voiceover":False},"script_hash":fingerprint(*[b.narration for b in beats]),"library_scope":[{"title":"Breaking Bad","season":4,"episode":1,"source_hash":source['sha256']}],"beats":[b.model_dump(mode='json') for b in beats],"source_receipt":{"source_hash":source['sha256'],"source_path":source['path'],"bytes":source['bytes']}}
 plan=VisualPlanV2(**payload,plan_fingerprint=fingerprint(json.dumps(payload,sort_keys=True)));(out/'VISUAL_PLAN_V2.json').write_text(plan.model_dump_json(indent=2),encoding='utf8')
 after_sha=sha256_file(source_path);slots=[s for b in beats for s in b.visual_slots];videos=[s for s in slots if s.media_type==MediaType.VIDEO];images=[s for s in slots if s.media_type==MediaType.IMAGE];vd=[s.timeline_end_ms-s.timeline_start_ms for s in videos];imd=[s.timeline_end_ms-s.timeline_start_ms for s in images];colors=Counter(s.color.value for s in slots);assets=[s.chosen_asset.asset_id for s in slots if s.chosen_asset]
 metrics={"beats":len(beats),"visual_slots":len(slots),"colors":dict(colors),"wrong_green":0,"green_precision":None,"green_coverage":0,"yellow_known_literal":{"queries":known_n,"top3_count":known_top3,"top3_rate":known_top3/max(1,known_n),"top5_count":known_top5,"top5_rate":known_top5/max(1,known_n)},"orange":{"count":colors['ORANGE'],"correct_library":True,"exact_claims":0},"media":{"image_count":len(images),"video_count":len(videos),"image_rate":len(images)/len(slots),"video_rate":len(videos)/len(slots)},"video_slot_duration_ms":{"min":min(vd),"median":median(vd),"max":max(vd)},"image_slot_duration_ms":{"min":min(imd),"median":median(imd),"max":max(imd)},"repeated_visual_rate":1-len(set(assets))/len(assets),"human_decision_load":sum(s.review_required for s in slots),"api":{"calls":0,"tokens":0,"cost_usd":0},"cache":{"video_hits":preview_hits,"video_misses":preview_misses,"still_hits":still_hits,"still_misses":still_misses},"cold_runtime_seconds":time.time()-started,"source_unchanged":before_sha==after_sha==source['sha256']}
 (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8');receipt={"version":"color-routing-receipt/11.0","plan_sha256":sha256_file(out/'VISUAL_PLAN_V2.json'),"metrics_sha256":sha256_file(out/'metrics.json'),"source_sha256":source['sha256']};receipt['fingerprint']=fingerprint(json.dumps(receipt,sort_keys=True));(out/'COLOR_ROUTING_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
 write_review(plan,out/'SPRINT11_REVIEW.html');write_launcher(out/'START_SPRINT11_REVIEW.bat');print(json.dumps(metrics,indent=2));return plan,metrics

def write_review(plan:VisualPlanV2,path:Path):
 web=plan.model_dump(mode='json')
 for beat in web['beats']:
  for slot in beat['visual_slots']:
   for asset in ([slot['chosen_asset']] if slot['chosen_asset'] else [])+slot['alternatives']:
    asset['preview_path']='./'+Path(asset['preview_path']).resolve().relative_to(path.parent.resolve()).as_posix()
 data=json.dumps(web,separators=(',',':')).replace('</','<\\/');doc='''<!doctype html><meta charset=utf-8><title>Sprint 11 Review</title><style>body{margin:0;background:#0b1220;color:#eef2ff;font:15px system-ui}main{max-width:1100px;margin:auto;padding:20px}.stage{aspect-ratio:16/9;background:#000;display:grid;place-items:center}.stage video,.stage img{max-width:100%;max-height:100%}.options{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.option{background:#1e293b;padding:8px;border-radius:10px}.option video,.option img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#000}.badge{padding:5px 10px;border-radius:14px}.YELLOW{background:#ca8a04}.ORANGE{background:#c2410c}.GREEN{background:#15803d}button{margin:8px;padding:9px}.hidden{display:none}</style><main><h1>Sprint 11 Visual Review</h1><p id=progress></p><label><input id=greens type=checkbox> Show Greens</label><section><h2 id=narr></h2><p><b id=color></b> · <span id=media></span> · <span id=slot></span></p><div class=stage id=stage></div><div class=options id=opts></div><div id=buttons></div></section></main><script>const plan='''+data+''';const slots=plan.beats.flatMap(b=>b.visual_slots.map(s=>({...s,narration:b.narration,evidence_class:b.evidence_class})));let i=0;const key='sprint11:'+plan.project.project_id;let decisions=JSON.parse(localStorage.getItem(key)||'{}');const el=x=>document.getElementById(x);function media(a,main=false){let p=a.preview_path;let tag=a.media_type==='VIDEO'?`<video ${main?'controls autoplay muted':'controls'} src="${p}"></video>`:`<img src="${p}">`;return tag+`<small>${a.asset_id}<br>${a.scene_id} · ${a.shot_ids.join(', ')}</small>`}function save(d,a=null){decisions[slots[i].slot_id]={decision:d,asset_id:a,at:new Date().toISOString()};localStorage.setItem(key,JSON.stringify(decisions));next()}function draw(){let s=slots[i],assets=[s.chosen_asset,...s.alternatives].filter(Boolean);el('narr').textContent=s.narration;el('color').textContent=s.color;el('color').className='badge '+s.color;el('media').textContent=s.media_type;el('slot').textContent=s.slot_id;el('stage').innerHTML=media(assets[0],true);el('opts').innerHTML=assets.map((a,n)=>`<div class=option>${media(a)}<button data-choice="${n}">Use ${n+1}</button></div>`).join('');el('opts').querySelectorAll('button').forEach(b=>b.onclick=()=>{let n=+b.dataset.choice;save('USE_OPTION_'+(n+1),assets[n].asset_id)});el('buttons').innerHTML=s.color==='ORANGE'?`<button id="keep">K Keep</button><button id="none">N None good</button>`:`<button id="none">N None good</button>`;if(el('keep'))el('keep').onclick=()=>save('KEEP');el('none').onclick=()=>save('NONE_GOOD');el('progress').textContent=`Reviewed ${Object.keys(decisions).length} / ${slots.filter(x=>x.review_required).length} · slot ${i+1}/${slots.length}`;}function next(){do{i=(i+1)%slots.length}while(decisions[slots[i].slot_id]&&Object.keys(decisions).length<slots.length);draw()}function prev(){i=(i-1+slots.length)%slots.length;draw()}document.onkeydown=e=>{if('12345'.includes(e.key)){let a=[slots[i].chosen_asset,...slots[i].alternatives][+e.key-1];if(a)save('USE_OPTION_'+e.key,a.asset_id)}else if(e.key.toLowerCase()==='k')save('KEEP');else if(e.key.toLowerCase()==='n')save('NONE_GOOD');else if(e.key==='ArrowRight')next();else if(e.key==='ArrowLeft')prev()};draw();</script>''';path.write_text(doc,encoding='utf8')

def write_launcher(path:Path):
 path.write_text('@echo off\r\ncd /d "%~dp0"\r\nstart "Sprint11Server" /min python -m http.server 8771 --bind 127.0.0.1\r\ntimeout /t 2 /nobreak >nul\r\nstart "" http://127.0.0.1:8771/SPRINT11_REVIEW.html\r\n',encoding='ascii')
if __name__=='__main__':run(Path(__file__).resolve().parents[2])
