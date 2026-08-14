from __future__ import annotations
import json, shutil
from pathlib import Path
from .hashing import sha256_file

def write_review(runtime: Path) -> None:
    runtime=runtime.resolve()
    plan=json.loads((runtime/"REPAIRED_VISUAL_PLAN.json").read_text(encoding="utf-8"))
    for item in plan["items"]:
        for a in item["options"]:
            source=Path(a["preview_path"]).resolve()
            try: rel=source.relative_to(runtime)
            except ValueError:
                rel=Path("previews/context")/(sha256_file(source)+source.suffix.lower()); target=runtime/rel
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists(): shutil.copy2(source,target)
            a["preview_path"]="./"+rel.as_posix()
    data=json.dumps(plan,separators=(",",":"),ensure_ascii=False).replace("</","<\\/")
    html="""<!doctype html><html><head><meta charset=utf-8><title>Sprint 13 Repair Review</title><style>
body{background:#09111f;color:#eef2ff;font:15px system-ui;margin:auto;max-width:1250px;padding:18px}button,select{padding:10px;margin:5px;background:#26354d;color:white;border:1px solid #64748b;border-radius:6px}.nav{display:flex;justify-content:space-between}.facts{background:#142036;padding:10px}.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.opt{background:#17243a;padding:9px;border:2px solid transparent}.selected{border-color:#22c55e}video,img{width:100%;max-height:260px;object-fit:contain;background:#000}.ORANGE{color:#fb923c}.YELLOW{color:#facc15}#save{color:#86efac}kbd{background:#334155;padding:2px 5px}</style></head><body>
<h1>Sprint 13 — 18 Item Repair Review</h1><div id=summary></div><label>Filter <select id=filter><option value=ALL>ALL</option><option value=YELLOW>YELLOW</option><option value=ORANGE>ORANGE</option></select></label><div class=nav><button id=prev>← PREVIOUS</button><button id=next>NEXT →</button></div><h2 id=title></h2><h3 id=status></h3><p id=narration></p><div class=facts><b>Required visible facts</b><ul id=req></ul><b>Not sufficient</b><ul id=no></ul></div><div class=opts id=opts></div><button id=none>NONE GOOD (N)</button><p>Keys: <kbd>1</kbd>–<kbd>5</kbd> choose · <kbd>N</kbd> none · <kbd>←</kbd>/<kbd>→</kbd> navigate</p><p id=save>Disk authority: ready</p>
<script>const plan=__DATA__,key='s13-review:'+plan.fingerprint;let all=plan.items,shown=all,i=0,d=JSON.parse(localStorage.getItem(key)||'{}');const E=x=>document.getElementById(x);
function media(a){return a.media_type==='VIDEO'?`<video controls preload=metadata src="${a.preview_path}"></video>`:`<img src="${a.preview_path}">`}
function draw(){if(!shown.length)return;let s=shown[i],sel=d[s.slot_id];E('summary').textContent=`Completed: ${Object.keys(d).length} / 18 · Repair item ${i+1} / ${shown.length}`;E('title').textContent=`${s.beat_id} · ${s.slot_id}`;E('status').textContent=`${s.status} · ${s.failure_class}`;E('status').className=s.status;E('narration').textContent=s.narration;E('req').innerHTML=s.required_visible_facts.map(x=>`<li>${x}</li>`).join('')||'<li>Contextual visual; literal proof not required</li>';E('no').innerHTML=s.not_sufficient_facts.map(x=>`<li>${x}</li>`).join('')||'<li>None specified</li>';E('opts').innerHTML=s.options.map((a,j)=>`<div class="opt ${sel&&sel.asset_id===a.asset_id?'selected':''}">${media(a)}<p><b>${j+1}. ${a.media_type}</b> · ${a.episode_code||'approved project context'}</p><button data-j=${j}>USE OPTION ${j+1}</button></div>`).join('');E('opts').querySelectorAll('button').forEach(b=>b.onclick=()=>choose(+b.dataset.j));}
function move(n){i=(i+n+shown.length)%shown.length;draw()}
async function save(row){E('save').textContent='Saving to disk…';let r=await fetch('/save-decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(row)}),x=await r.json();if(!r.ok)throw Error(x.error||'save failed');d[row.slot_id]=row;localStorage.setItem(key,JSON.stringify(d));E('save').textContent=`Saved to disk: YES · ${x.completed}/18`;let start=i;do{move(1)}while(d[shown[i].slot_id]&&i!==start)}
function choose(j){let s=shown[i],a=s.options[j];if(a)save({slot_id:s.slot_id,decision:`USE_OPTION_${j+1}`,asset_id:a.asset_id}).catch(showError)}function none(){let s=shown[i];save({slot_id:s.slot_id,decision:'NONE_GOOD',asset_id:null}).catch(showError)}function showError(e){E('save').textContent='SAVE FAILED: '+e.message;console.error(e)}
E('prev').onclick=()=>move(-1);E('next').onclick=()=>move(1);E('none').onclick=none;E('filter').onchange=e=>{shown=e.target.value==='ALL'?all:all.filter(x=>x.status===e.target.value);i=0;draw()};document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if('12345'.includes(e.key))choose(+e.key-1);else if(e.key.toLowerCase()==='n')none();else if(e.key==='ArrowRight')move(1);else if(e.key==='ArrowLeft')move(-1)});draw();</script></body></html>""".replace("__DATA__",data)
    (runtime/"SPRINT13_REPAIR_REVIEW.html").write_text(html,encoding="utf-8")
    launcher='@echo off\r\ncd /d "'+str(runtime.parents[1])+'"\r\nstart "Sprint13RepairServer" /min python -m scenebrain.sprint13_repair_server\r\ntimeout /t 2 /nobreak >nul\r\nstart "" http://127.0.0.1:8773/SPRINT13_REPAIR_REVIEW.html\r\n'
    (runtime/"START_SPRINT13_REPAIR_REVIEW.bat").write_text(launcher,encoding="ascii")
