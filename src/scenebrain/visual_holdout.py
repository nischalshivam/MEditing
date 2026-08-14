from __future__ import annotations

import json
from pathlib import Path

from .hashing import sha256_file

# Frozen before any Sprint 3 resolver exists. These were labelled from local
# S04E01 frames/contact sheets; they are never used to alter the Scene Atlas.
ITEMS = [
 ("V01","Gale slices open a shipping crate with a green utility knife.","EXACT_VISIBLE_EVENT",[[1,6]],"EXACT"),
 ("V02","Gale shows Gus the newly installed superlab equipment.","EXACT_VISIBLE_EVENT",[[12,46]],"EXACT"),
 ("V03","Jesse points a handgun while alone inside his cluttered house.","EXACT_VISIBLE_EVENT",[[48,56]],"EXACT"),
 ("V04","Investigators stand over Gale's body at the apartment crime scene.","EXACT_VISIBLE_EVENT",[[62,64]],"EXACT"),
 ("V05","Walter, Jesse, Mike and Victor wait together inside the dark superlab.","SCENE_CONTEXT",[[65,95]],"CONTEXT"),
 ("V06","Marie speaks to Skyler at Skyler's front door.","EXACT_VISIBLE_EVENT",[[96,116]],"EXACT"),
 ("V07","Skyler watches Marie drive away and returns inside.","EXACT_VISIBLE_EVENT",[[117,130]],"EXACT"),
 ("V08","Jesse puts on protective equipment and prepares laboratory machinery.","EXACT_VISIBLE_EVENT",[[139,153]],"EXACT"),
 ("V09","Saul searches frantically on his office floor while Huell waits.","EXACT_VISIBLE_EVENT",[[154,175]],"EXACT"),
 ("V10","Skyler talks by phone with Saul at an outdoor payphone.","SCENE_CONTEXT",[[176,187]],"EXACT"),
 ("V11","A locksmith holds Skyler's baby while opening the front door.","EXACT_VISIBLE_EVENT",[[188,207]],"EXACT"),
 ("V12","Skyler enters the unlocked home and the locksmith departs.","EXACT_VISIBLE_EVENT",[[205,221]],"EXACT"),
 ("V13","Hank lies in bed researching minerals on a laptop.","OBJECT_ACTION",[[222,241]],"EXACT"),
 ("V14","Gus silently enters the superlab in a dark suit.","EXACT_VISIBLE_EVENT",[[242,260]],"EXACT"),
 ("V15","Walter looks terrified while waiting for Gus to respond.","REACTION",[[250,275]],"CONTEXT"),
 ("V16","Gus changes from his suit into protective clothing.","OBJECT_ACTION",[[275,300]],"EXACT"),
 ("V17","Gus holds the green box cutter before attacking Victor.","OBJECT_ACTION",[[310,330]],"CONTEXT"),
 ("V18","Mike reacts in shock during Victor's killing.","REACTION",[[330,355]],"CONTEXT"),
 ("V19","Walter and Jesse react in horror while restrained in the lab.","REACTION",[[330,390]],"CONTEXT"),
 ("V20","Gus grabs Victor and cuts his throat with the box cutter.","EXACT_VISIBLE_EVENT",[[360,401]],"EXACT"),
 ("V21","Gus cleans himself and changes back into his suit after the killing.","OBJECT_ACTION",[[385,401]],"CONTEXT"),
 ("V22","Walter and Jesse eat at a diner while discussing Gus.","SCENE_CONTEXT",[[402,426]],"EXACT"),
 ("V23","Walter arrives home by taxi and speaks with Skyler outside.","SCENE_CONTEXT",[[427,437]],"EXACT"),
 ("V24","Jesse lies among scattered objects during the closing aftermath montage.","REACTION",[[438,451]],"CONTEXT"),
 ("V25","A close-up shows Hank's mineral-shopping webpage.","OBJECT_ACTION",[[222,241]],"CONTEXT"),
 ("V26","The green utility knife is visible without Gale's face in the same close-up.","CONFUSING_SIMILAR",[[1,10]],"EXACT"),
 ("V27","Gus is visible in the superlab before changing clothes.","CONFUSING_SIMILAR",[[242,300]],"CONTEXT"),
 ("V28","A folded jacket and rolled tie lie together on a stainless counter.","NEGATIVE_NONE",[],"NONE"),
 ("V29","Mike lowers a visible handgun immediately after Victor is cut.","NEGATIVE_NONE",[],"NONE"),
 ("V30","Gus washes bloody hands in a stainless-steel sink.","NEGATIVE_NONE",[],"NONE"),
]


def freeze_visual_holdout(source_sha: str, output: Path) -> dict:
    rows=[]
    for key,query,category,ranges,verdict in ITEMS:
        rows.append({"schema_version":"visual-holdout/1.0","question_id":key,"episode":"S04E01","query":query,
          "category":category,"label_status":"HUMAN_VERIFIED","ground_truth":{"verdict":verdict,
          "acceptable_shot_ranges":[{"start_shot":f"S{a:04d}","end_shot":f"S{b:04d}"} for a,b in ranges]},
          "source_sha256":source_sha,"provenance":{"reviewer":"codex_sprint2_visual_review","source_frames_inspected":True}})
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise FileExistsError(output)
    output.write_text("\n".join(json.dumps(x,separators=(",",":")) for x in rows)+"\n",encoding="utf-8")
    return {"name":"S04E01_VISUAL_HOLDOUT_V1","path":str(output.resolve()),"sha256":sha256_file(output),"questions":len(rows),
      "categories":{k:sum(x[2]==k for x in ITEMS) for k in sorted({x[2] for x in ITEMS})},"frozen_before_sprint3":True}
