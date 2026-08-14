from __future__ import annotations

import json, shutil
from pathlib import Path
from .hashing import fingerprint

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sprint 9C Human Candidate Oracle</title>
<style>
:root{color-scheme:dark}body{font:16px system-ui;margin:0;background:#0b0e13;color:#edf2f7}.wrap{max-width:1250px;margin:auto;padding:22px}.status,.card{background:#151a23;border:1px solid #303949;border-radius:12px;padding:16px;margin:12px 0}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.muted{color:#aab6c6}.frames{width:100%;display:block;border-radius:8px;background:#000}.buttons{display:flex;gap:12px;flex-wrap:wrap}button{font-size:17px;padding:12px 20px;border-radius:8px;border:1px solid #526078;background:#242d3d;color:white;cursor:pointer}button.active{outline:3px solid #62d6a7}button:disabled{opacity:.4;cursor:not-allowed}.literal{background:#155c43}.partial{background:#73520d}.nomatch{background:#702c34}.error{background:#641f28;white-space:pre-wrap}.ok{color:#6ee7b7}kbd{background:#273142;padding:3px 7px;border-radius:4px}@media(max-width:700px){.stats{grid-template-columns:1fr 1fr}}
</style></head><body><main class="wrap"><h1>Human Candidate Oracle</h1>
<section id="diagnostics" class="status">Initializing…</section><section id="failure" class="status error" hidden></section>
<section id="app" hidden><div class="stats status"><div><b id="overall"></b></div><div><b id="requestProgress"></b></div><div><b id="candidateProgress"></b></div><div><b id="saved"></b></div></div>
<article class="card"><div class="muted">Query</div><h2 id="query"></h2><p><b>Category:</b> <span id="category"></span></p><div><b>Required visible facts:</b><ul id="facts"></ul></div><div><b>Not sufficient:</b><ul id="insufficient"></ul></div><p><b>Candidate ID:</b> <span id="candidateId"></span></p><img id="frames" class="frames" alt="Ordered F01-F15 frame strip"><p id="assetState" class="muted"></p></article>
<div class="buttons"><button id="literal" class="literal">1 — LITERAL</button><button id="partial" class="partial">2 — PARTIAL</button><button id="nomatch" class="nomatch">3 — NO MATCH</button></div>
<div class="buttons"><button id="previous">← Previous</button><button id="next">Next →</button><button id="export" disabled>Export SPRINT9C_HUMAN_ORACLE.jsonl</button></div><p>Keyboard: <kbd>1</kbd> / <kbd>2</kbd> / <kbd>3</kbd> · Arrow keys navigate</p></section></main>
<script src="./oracle_review.js"></script></body></html>'''

JS = r'''"use strict";
const STORAGE_KEY="sprint9c-human-oracle-v1";let items=[],index=0,labels={};
const $=id=>document.getElementById(id);
function fail(stage,error){console.error("ORACLE HARNESS FAILED",stage,error);$("failure").hidden=false;$("failure").textContent=`ORACLE HARNESS FAILED\n\nStage: ${stage}\n\nError: ${error?.message||error}`;}
function diagnostics(manifest,verified=0){const requests=new Set((manifest?.items||[]).map(x=>x.request_id)).size;$("diagnostics").innerHTML=`Manifest loaded: <b>${manifest?"YES":"NO"}</b><br>Requests loaded: <b>${requests} / 8</b><br>Candidates loaded: <b>${manifest?.items?.length||0} / 192</b><br>Frame assets verified: <b>${verified} / ${manifest?.items?.length||192}</b>`;}
function requestPosition(){const ids=[...new Set(items.map(x=>x.request_id))];return [ids.indexOf(items[index].request_id)+1,ids.length,items.filter(x=>x.request_id===items[index].request_id).indexOf(items[index])+1];}
function key(x){return `${x.request_id}|${x.candidate_id}`;}
function render(){const x=items[index],[rp,rc,cp]=requestPosition(),done=Object.keys(labels).length;$("overall").textContent=`Overall: ${done} / ${items.length}`;$("requestProgress").textContent=`Request: ${rp} / ${rc}`;$("candidateProgress").textContent=`Candidate: ${cp} / 24`;$("saved").textContent="Saved locally: YES";$("query").textContent=x.query;$("category").textContent=x.category;$("candidateId").textContent=x.candidate_id;$("facts").innerHTML=x.required_visible_facts.map(v=>`<li>${escapeHtml(v)}</li>`).join("");$("insufficient").innerHTML=x.not_sufficient_facts.map(v=>`<li>${escapeHtml(v)}</li>`).join("");$("frames").src=x.frame_strip_url;$("assetState").textContent=`Ordered frames: ${x.frame_ids.join(", ")}`;for(const [id,val] of [["literal","LITERAL"],["partial","PARTIAL"],["nomatch","NO_MATCH"]])$(id).classList.toggle("active",labels[key(x)]?.human_label===val);$("previous").disabled=index===0;$("next").disabled=index===items.length-1;$("export").disabled=done!==items.length;}
function escapeHtml(v){const d=document.createElement("div");d.textContent=v;return d.innerHTML;}
function setLabel(value){const x=items[index];labels[key(x)]={request_id:x.request_id,candidate_id:x.candidate_id,human_label:value,required_facts_supported:[],optional_note:"",reviewed_at:new Date().toISOString(),source_fingerprint:x.source_fingerprint,candidate_fingerprint:x.candidate_fingerprint};localStorage.setItem(STORAGE_KEY,JSON.stringify(labels));if(index<items.length-1)index++;render();}
function nav(delta){index=Math.max(0,Math.min(items.length-1,index+delta));render();}
function exportLabels(){if(Object.keys(labels).length!==items.length)return;const text=items.map(x=>JSON.stringify(labels[key(x)])).join("\n")+"\n";const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type:"application/jsonl"}));a.download="SPRINT9C_HUMAN_ORACLE.jsonl";a.click();URL.revokeObjectURL(a.href);}
async function init(){try{diagnostics(null);const response=await fetch("./oracle_manifest.json",{cache:"no-store"});if(!response.ok)throw new Error(`HTTP ${response.status}`);const manifest=await response.json();if(!Array.isArray(manifest.items)||manifest.items.length!==192)throw new Error(`Expected 192 candidates, got ${manifest.items?.length}`);items=manifest.items;labels=JSON.parse(localStorage.getItem(STORAGE_KEY)||"{}");let verified=0;await Promise.all(items.map(x=>new Promise(resolve=>{const im=new Image();im.onload=()=>{verified++;resolve()};im.onerror=()=>resolve();im.src=x.frame_strip_url})));diagnostics(manifest,verified);if(verified!==192)throw new Error(`${192-verified} frame strips failed preflight`);$("app").hidden=false;render();console.info("Oracle initialized",{requests:new Set(items.map(x=>x.request_id)).size,candidates:items.length,assets:verified});}catch(error){fail("manifest load / asset verification / initialization",error);}}
$("literal").onclick=()=>setLabel("LITERAL");$("partial").onclick=()=>setLabel("PARTIAL");$("nomatch").onclick=()=>setLabel("NO_MATCH");$("previous").onclick=()=>nav(-1);$("next").onclick=()=>nav(1);$("export").onclick=exportLabels;window.addEventListener("keydown",e=>{if(e.key==="1")setLabel("LITERAL");else if(e.key==="2")setLabel("PARTIAL");else if(e.key==="3")setLabel("NO_MATCH");else if(e.key==="ArrowLeft")nav(-1);else if(e.key==="ArrowRight")nav(1)});window.addEventListener("DOMContentLoaded",init);
'''

def _not_sufficient(query:str)->list[str]:
    q=query.lower();out=["Static presence without the requested action is not sufficient."]
    if any(x in q for x in ("enter","leave","walk","approach","arrive")):out.append("Standing at the destination without visible movement or transition is not sufficient.")
    if any(x in q for x in ("eat","hand","put","pick","pour","cut","mop","hold")):out.append("The object being visible without the requested interaction is not sufficient.")
    if "react" in q:out.append("The trigger alone without the requested subject reacting is not sufficient.")
    return out

def build_harness(source_manifest:Path,root:Path)->dict:
    raw=json.loads(source_manifest.read_text(encoding="utf8"));items=[];assets=root/"oracle_assets"
    if assets.exists():shutil.rmtree(assets)
    for row in raw["items"]:
        rid=row["request_id"];cid=row["candidate"]["candidate_id"];folder=assets/rid;folder.mkdir(parents=True,exist_ok=True);target=folder/f"{cid}.jpg";shutil.copy2(row["strip_path"],target)
        facts=row["required_visible_facts"] or [f"Requested event must be visibly present: {row['query']}"]
        items.append({"request_id":rid,"query":row["query"],"category":row["category"],"required_visible_facts":facts,"not_sufficient_facts":_not_sufficient(row["query"]),"candidate_id":cid,"candidate_fingerprint":row["candidate_fingerprint"],"source_fingerprint":row["source_fingerprint"],"frame_strip_url":f"./oracle_assets/{rid}/{cid}.jpg","frame_ids":[x["frame_id"] for x in row["frame_manifest"]["frames"]]})
    manifest={"version":"oracle-web-manifest/2.0","items":items};(root/"oracle_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8");(root/"ORACLE_REVIEW.html").write_text(HTML,encoding="utf8");(root/"oracle_review.js").write_text(JS,encoding="utf8");return validate_harness(root)

def validate_harness(root:Path)->dict:
    manifest=json.loads((root/"oracle_manifest.json").read_text(encoding="utf8"));items=manifest.get("items",[]);errors=[];groups={}
    for x in items:groups.setdefault(x.get("request_id"),[]).append(x)
    if len(groups)!=8:errors.append(f"expected 8 requests, got {len(groups)}")
    if len(items)!=192:errors.append(f"expected 192 candidates, got {len(items)}")
    for rid,xs in groups.items():
        if len(xs)!=24:errors.append(f"{rid}: expected 24 candidates, got {len(xs)}")
    keys=[(x.get("request_id"),x.get("candidate_id")) for x in items]
    if len(set(keys))!=len(keys):errors.append("duplicate request/candidate ID")
    for x in items:
        if not x.get("required_visible_facts"):errors.append(f"{x.get('request_id')}/{x.get('candidate_id')}: missing facts")
        ids=x.get("frame_ids",[])
        if not ids or ids!=[f"F{i:02d}" for i in range(1,len(ids)+1)]:errors.append(f"{x.get('request_id')}/{x.get('candidate_id')}: invalid frame IDs")
        p=(root/x["frame_strip_url"].removeprefix("./")).resolve()
        if not p.is_file() or root.resolve() not in p.parents:errors.append(f"missing/broken asset: {x.get('frame_strip_url')}")
    if errors:raise ValueError("\n".join(errors))
    return {"requests":len(groups),"candidates":len(items),"assets":sum((root/x["frame_strip_url"].removeprefix("./")).is_file() for x in items),"fingerprint":fingerprint(json.dumps(manifest,sort_keys=True))}

def freeze_labels(path:Path,receipt:Path,expected:int=192):
    rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    if len(rows)!=expected or len({(x['request_id'],x['candidate_id']) for x in rows})!=expected:raise ValueError('human oracle incomplete')
    payload={'version':'human-candidate-oracle/1.0','items':expected,'labels_fingerprint':fingerprint(json.dumps(rows,sort_keys=True))};receipt.write_text(json.dumps(payload,indent=2));return payload
