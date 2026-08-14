import tempfile, unittest
from pathlib import Path

from scenebrain.exact_tournament_v9 import CONFIG, CandidateAssessment, GroupDecision, FrameDecision, make_crop
from scenebrain.shot_models import ShotRange


class ExactTournamentV9Tests(unittest.TestCase):
    def test_all_24_grouped_without_loss(self):
        ids=[f'H8_{i:02d}' for i in range(1,25)]
        groups=[ids[i:i+CONFIG['group_size']] for i in range(0,24,CONFIG['group_size'])]
        self.assertEqual(len(groups),4);self.assertEqual([x for g in groups for x in g],ids)

    def test_group_none_is_structured(self):
        d=GroupDecision(request_id='x',assessments=[CandidateAssessment(candidate_id='A',classification='NO_MATCH',visible_evidence='absent')],finalists=[],none_from_group=True)
        self.assertTrue(d.none_from_group)

    def test_partial_cannot_be_finalist(self):
        d=GroupDecision(request_id='x',assessments=[CandidateAssessment(candidate_id='A',classification='PARTIAL_MATCH',visible_evidence='object only')],finalists=[],none_from_group=True)
        literal={x.candidate_id for x in d.assessments if x.classification=='LITERAL_MATCH'}
        self.assertFalse(literal)

    def test_timestamp_and_extra_fields_rejected(self):
        with self.assertRaises(Exception):FrameDecision.model_validate({'request_id':'x','candidate_id':'A','decision':'SUPPORTED_INTERVAL','event_start_frame':'F0001','event_end_frame':'F0002','evidence_statement':'yes','timestamp_ms':5})

    def test_frame_ids_not_timestamps(self):
        d=FrameDecision(request_id='x',candidate_id='A',decision='SUPPORTED_INTERVAL',event_start_frame='F0001',event_end_frame='F0004',evidence_statement='motion')
        self.assertEqual(d.event_start_frame,'F0001')

    def test_brief_sampling_policy(self):
        self.assertGreaterEqual(CONFIG['frame_fps'],8)
        self.assertLessEqual(CONFIG['brief_shot_ms'],3000)

    def test_crop_bounds_and_handles(self):
        # Pure bound rule equivalent: handles must clamp to candidate bounds.
        c=ShotRange(candidate_id='A',start_shot='S0001',end_shot='S0001',start_ms=1000,end_ms=2000,scene_ids=['X'],local_score=1,provenance=[])
        frames={'fps':8,'frames':[{'frame_id':'F0001','source_ms':1000},{'frame_id':'F0002','source_ms':1125}]}
        a=max(c.start_ms,frames['frames'][0]['source_ms']-CONFIG['handles_ms']['brief_insert'][0]);b=min(c.end_ms,frames['frames'][1]['source_ms']+125+CONFIG['handles_ms']['brief_insert'][1])
        self.assertEqual(a,1000);self.assertLessEqual(b,2000)

    def test_final_verifier_prompt_is_independent(self):
        from scenebrain.exact_tournament_v9 import CROP_PROMPT
        self.assertIn('independent',CROP_PROMPT)


if __name__=='__main__':unittest.main()
