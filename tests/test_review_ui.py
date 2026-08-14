import json,tempfile,unittest
from pathlib import Path
from scenebrain.production_editor import edit

MEDIA=Path(r"E:\Movies")
class ReviewUIDataTests(unittest.TestCase):
 def test_original_candidate_counts_and_distinction(self):
  p=json.loads((MEDIA/".scene_brain/projects/walter_book_project/EDITOR_PROJECT.json").read_text());self.assertEqual(len(p['timeline']),70);self.assertEqual(sum(x['approval_state']=='NEEDS_CHOICE' for x in p['timeline']),64);self.assertEqual(sum(x['approval_state']=='APPROVED' for x in p['timeline']),1);self.assertEqual(sum(x['approval_state']=='MANUAL_FIX' for x in p['timeline']),5);self.assertTrue(all(1<=len(x['candidates'])<=3 for x in p['timeline'] if x['approval_state']=='NEEDS_CHOICE'))
 def test_candidate_approval_persists_on_copy(self):
  src=MEDIA/".scene_brain/projects/walter_book_project/EDITOR_PROJECT.json";pid='walter_review_unit_copy';dst=MEDIA/".scene_brain/projects"/pid/'EDITOR_PROJECT.json';dst.parent.mkdir(exist_ok=True);p=json.loads(src.read_text());p['project_id']=pid;before=sum(x['approval_state']=='NEEDS_CHOICE' for x in p['timeline']);dst.write_text(json.dumps(p));slot=next(x for x in p['timeline'] if x['approval_state']=='NEEDS_CHOICE');out=edit(MEDIA,pid,{'action':'APPROVE_CANDIDATE','slot_id':slot['presentation_slot_id'],'candidate_index':0});chosen=next(x for x in out['timeline'] if x['presentation_slot_id']==slot['presentation_slot_id']);self.assertEqual(chosen['approval_state'],'APPROVED');self.assertEqual(out['review_counts']['needs_choice'],before-1);self.assertEqual(json.loads(dst.read_text())['review_counts']['approved'],2)
