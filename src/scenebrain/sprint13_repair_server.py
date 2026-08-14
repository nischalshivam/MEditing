from __future__ import annotations
import json, os
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .db import connect

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"runtime/sprint13_repair"
PLAN=RUNTIME/"REPAIRED_VISUAL_PLAN.json"
AUDIT=RUNTIME/"audit"

def persist(payload: dict) -> dict:
    plan=json.loads(PLAN.read_text(encoding="utf-8")); items={x["slot_id"]:x for x in plan["items"]}
    sid=str(payload.get("slot_id","")); decision=str(payload.get("decision","")); aid=payload.get("asset_id")
    if sid not in items: raise ValueError("unknown repair slot")
    if decision not in {"USE_OPTION_1","USE_OPTION_2","USE_OPTION_3","USE_OPTION_4","USE_OPTION_5","NONE_GOOD"}: raise ValueError("invalid decision")
    assets={x["asset_id"] for x in items[sid]["options"]}
    if decision=="NONE_GOOD": aid=None
    elif aid not in assets: raise ValueError("asset was not presented for this slot")
    row={"slot_id":sid,"beat_id":items[sid]["beat_id"],"decision":decision,"asset_id":aid,"saved_at":datetime.now(timezone.utc).isoformat(),"plan_fingerprint":plan["fingerprint"]}
    AUDIT.mkdir(parents=True,exist_ok=True); path=AUDIT/"SPRINT13_REPAIR_DECISIONS.json"
    existing=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version":"repair-decisions/1.0","project_fingerprint":plan["project_fingerprint"],"decisions":{}}
    existing["decisions"][sid]=row; tmp=path.with_suffix(".building.json"); tmp.write_text(json.dumps(existing,indent=2),encoding="utf-8"); tmp.replace(path)
    db=connect(ROOT/"runtime/scene_brain.db")
    db.execute("insert into project_repair_decisions(project_fingerprint,slot_id,decision,asset_id,decision_json,updated_at) values(?,?,?,?,?,?) on conflict(project_fingerprint,slot_id) do update set decision=excluded.decision,asset_id=excluded.asset_id,decision_json=excluded.decision_json,updated_at=excluded.updated_at",
               (plan["project_fingerprint"],sid,decision,aid,json.dumps(row,sort_keys=True),row["saved_at"]));db.commit();db.close()
    return {"ok":True,"saved":row,"completed":len(existing["decisions"]),"total":len(items)}

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path!="/save-decision": self.send_error(404); return
        try:
            n=int(self.headers.get("Content-Length","0")); result=persist(json.loads(self.rfile.read(n))); code=200
        except Exception as exc: result={"ok":False,"error":str(exc)}; code=400
        body=json.dumps(result).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)

def main():
    os.chdir(RUNTIME); print("Sprint 13 repair review: http://127.0.0.1:8773/SPRINT13_REPAIR_REVIEW.html")
    ThreadingHTTPServer(("127.0.0.1",8773),Handler).serve_forever()
if __name__=="__main__":main()
