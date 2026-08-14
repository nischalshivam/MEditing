import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from scenebrain.production_visual_composer import *
from scenebrain.production_visual_composer import _quality
from scenebrain.db import connect

def asset(mt=MediaType.VIDEO,cid='a'):
 return Asset(asset_id=cid,media_type=mt,source_path='x',source_hash='a'*64,season=4,episode=1,scene_id='s',shot_ids=['S0001'],source_in_ms=1000,source_out_ms=4000 if mt==MediaType.VIDEO else None,frame_time_ms=2000 if mt==MediaType.IMAGE else None,derivative_path='d',preview_path='p')

class ComposerTests(unittest.TestCase):
 def test_media_color_independent(self):
  for color in (Color.GREEN,Color.YELLOW,Color.ORANGE):
   for mt in (MediaType.VIDEO,MediaType.IMAGE):
    s=VisualSlot(slot_id='s',timeline_start_ms=0,timeline_end_ms=5000,color=color,media_type=mt,chosen_asset=asset(mt),reason='x',review_required=color!=Color.GREEN)
    self.assertEqual(s.media_type,mt)
 def test_dynamic_duration(self):
  self.assertEqual(len(split_slots(0,5000)),1);self.assertEqual(len(split_slots(0,9000)),2)
  self.assertNotEqual([b-a for a,b in split_slots(0,9001)],[3000,3000])
 def test_natural_ranges(self):
  shots=[{'ordinal':1,'start_ms':0,'end_ms':2100},{'ordinal':2,'start_ms':2100,'end_ms':5700},{'ordinal':3,'start_ms':5700,'end_ms':9900}]
  out=natural_video_ranges({'start_shot':'S0002','end_shot':'S0002','start_ms':2500,'end_ms':5000,'shot_ids':['S0002']},shots,9900)
  self.assertTrue(all(0<=x['start_ms']<x['end_ms']<=9900 for x in out));self.assertGreater(len({x['end_ms']-x['start_ms'] for x in out}),1)
 def test_image_quality_rejection(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.jpg';Image.new('RGB',(100,100),'black').save(p);score,signals=_quality(p);self.assertTrue(signals['rejected'])
 def test_repetition_penalty(self):
  r=RepetitionManager();a=asset();self.assertEqual(r.penalty(a),0);r.use(a);self.assertGreater(r.penalty(a),0)
 def test_plan_v2(self):
  s=VisualSlot(slot_id='s',timeline_start_ms=0,timeline_end_ms=5000,color=Color.YELLOW,media_type=MediaType.VIDEO,chosen_asset=asset(),reason='x',review_required=True)
  b=BeatV2(beat_id='b',narration='n',timeline_start_ms=0,timeline_end_ms=5000,evidence_class='EXACT_EVENT',preferred_presentation=Presentation.VIDEO_PREFERRED,visual_slots=[s])
  p=VisualPlanV2(project={'project_id':'p'},script_hash='x',library_scope=[],beats=[b],source_receipt={},plan_fingerprint='f');self.assertEqual(p.schema_version,'visual-plan/2.0')
 def test_memory_separation_and_false_positive(self):
  with tempfile.TemporaryDirectory() as d:
   c=connect(Path(d)/'x.db');ensure_memory_schema(c);s=VisualSlot(slot_id='s',timeline_start_ms=0,timeline_end_ms=5000,color=Color.YELLOW,media_type=MediaType.VIDEO,chosen_asset=asset(),reason='x',review_required=True);b=BeatV2(beat_id='b',narration='n',timeline_start_ms=0,timeline_end_ms=5000,evidence_class='EXACT_EVENT',preferred_presentation=Presentation.VIDEO_PREFERRED,visual_slots=[s]);p=VisualPlanV2(project={'project_id':'p'},script_hash='x',library_scope=[],beats=[b],source_receipt={},plan_fingerprint='f')
   persist_review(c,p,'s','USE_OPTION_1','a',10,'CONTEXTUAL_VISUAL_APPROVAL');self.assertEqual(c.execute('select approval_type from editorial_memory_v2').fetchone()[0],'CONTEXTUAL_VISUAL_APPROVAL')
   persist_review(c,p,'s','MARK_WRONG','a');self.assertEqual(c.execute('select count(*) from green_false_positive_audit').fetchone()[0],1)
   c.close()
