from __future__ import annotations

import json,tempfile,unittest
from pathlib import Path

from pydantic import ValidationError

from scenebrain.db import connect
from scenebrain.resolver_models import CandidateResult,ResolverResult,SceneRetrievalRequest
from scenebrain.shot_models import ShotRequest,ShotResolution
from scenebrain.shot_resolver import derive_crop,generate_candidates
from scenebrain.shot_verifier import CandidateVerdict,CropVerdict
from scenebrain.moment_resolver_v2 import CONFIG as V2_CONFIG,generate_v2
from scenebrain.moment_verifier_v2 import CandidateV2,RefineV2
from scenebrain.retrieval_contract_v3 import normalize_request,region_discovery_allowed,upstream_export_authorized
from scenebrain.reranker_v3 import rerank_v3

class ShotResolverUnitTests(unittest.TestCase):
    def request(self,decision='VERIFIED',scene='S04E01_SC011'):
        req=SceneRetrievalRequest(request_id='T',query_text='Gus holds box cutter',evidence_class='EXACT_EVENT',objects=['box cutter'])
        c=CandidateResult(scene_id=scene,start_ms=0,end_ms=9,total_score=.8,channel_scores={'event':.8},matched_fragments=[{'text':'Gus holds box cutter','evidence_shots':['S0002']}],matched_dialogue=[],evidence_shot_ids=['S0002'],atlas_status='RESOLVED',matches=[],conflicts=[],neighbors=[])
        return ShotRequest(scene_request=req,sprint3_result=ResolverResult(request_id='T',resolver_version='scene-resolver/1.0',decision=decision,primary_scene=scene if decision!='ABSTAIN' else None,candidates=[c],decision_reason='x',provenance={}))

    def db(self):
        td=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(td.cleanup);c=connect(Path(td.name)/'x.db');self.addCleanup(c.close)
        with c:
            c.execute("insert into titles(canonical_name,kind) values('Breaking Bad','SERIES')")
            c.execute("insert into source_files(title_id,season,episode,path,bytes,mtime_ns,sha256,duration_ms,probe_json) values(1,4,1,'x',1,1,'abc',10000,'{}')")
            for i in range(6):c.execute("insert into shots(source_file_id,ordinal,start_ms,end_ms,detector,detector_version,input_fingerprint) values(1,?,?,?,?,?,?)",(i,i*1000,(i+1)*1000,'d','1','f'))
            c.execute("insert into scenes(source_file_id,scene_uid,ordinal,start_shot_id,end_shot_id,start_ms,end_ms,boundary_status,scene_type,visual_summary,atlas_fingerprint,analysis_status) values(1,'S04E01_SC011',1,1,6,0,6000,'SUPPORTED','normal','x','a','RESOLVED')")
            for i in range(1,7):c.execute("insert into scene_shots(scene_id,shot_id,ordinal) values(1,?,?)",(i,i-1))
            c.execute("insert into resolver_input_freezes(source_file_id,freeze_version,input_fingerprint,manifest_path,manifest_sha256) values(1,'x','rf','x','x')")
            c.execute("insert into resolver_versions(version,input_freeze_id,schema_version,ranking_config_json,embedding_model,resolver_fingerprint) values('scene-resolver/1.0',1,'x','{}','x','fp')")
        return c

    def test_sprint3_top_scene_and_evidence_expansion(self):
        out=generate_candidates(self.db(),self.request());self.assertTrue(out);self.assertLessEqual(len(out),12);self.assertTrue(any(x.start_shot<='S0002'<=x.end_shot for x in out))
    def test_contextual_and_abstain_contracts(self):
        for d,expected in [('CONTEXTUAL','REVIEW_REQUIRED'),('ABSTAIN','ABSTAIN')]:
            base={'request_id':'T','version':'v','decision':expected,'candidates':[],'reason':'x','provenance':{}}
            self.assertEqual(ShotResolution(**base).decision,expected)
    def test_stale_sprint3_version(self):
        r=self.request();r.sprint3_result.resolver_version='old'
        with self.assertRaisesRegex(ValueError,'stale'):generate_candidates(self.db(),r)
    def test_invalid_physical_shot(self):
        r=self.request();r.sprint3_result.candidates[0].matched_fragments[0]['evidence_shots']=['S_BAD']
        self.assertEqual(generate_candidates(self.db(),r),[])
    def test_no_model_timestamps_or_extra_fields(self):
        with self.assertRaises(ValidationError):CandidateVerdict.model_validate({'request_id':'T','decision':'NONE_OF_THESE','candidate_id':None,'supporting_shot_ids':[],'evidence_statement':'x','timestamp':1})
        with self.assertRaises(ValidationError):CropVerdict.model_validate({'request_id':'T','candidate_id':'C','decision':'REJECTED','supporting_shot_ids':[],'literal_action_visible':False,'correct_object':None,'required_character_visible':None,'temporal_relation_supported':False,'usability_flags':[],'evidence_statement':'x','start_ms':1})
    def test_none_of_these_shape(self):
        x=CandidateVerdict(request_id='T',decision='NONE_OF_THESE',candidate_id=None,supporting_shot_ids=[],evidence_statement='absent');self.assertIsNone(x.candidate_id)
    def test_crop_uses_local_bounds(self):
        from scenebrain.shot_models import ShotRange
        c=ShotRange(candidate_id='C',start_shot='S0001',end_shot='S0002',start_ms=1000,end_ms=3000,scene_ids=['S'],local_score=1,provenance=[])
        self.assertEqual(derive_crop(c,['S0001']),(1000,3000))
    def test_s013_boundary_sensitive(self):
        r=self.request();r.sprint3_result.candidates[0].scene_id='S04E01_SC013';r.sprint3_result.primary_scene='S04E01_SC013'
        c=self.db();c.execute("update scenes set scene_uid='S04E01_SC013'")
        out=generate_candidates(c,r);self.assertTrue(out[0].boundary_sensitive)

    def test_v2_micro_windows_and_candidate_cap(self):
        out=generate_v2(self.db(),self.request());self.assertTrue(out);self.assertLessEqual(len(out),V2_CONFIG['candidate_k']);self.assertTrue(all(x.end_ms-x.start_ms<=V2_CONFIG['window_ms'] for x in out))
    def test_v2_diverse_lanes(self):
        c=self.db();c.execute("insert into scene_retrieval_fragments(scene_id,fragment_type,objective_text,normalized_text,evidence_shot_ids_json,trust_status,source_fingerprint,provenance_json,fragment_fingerprint) values(1,'ACTION','Gus holds box cutter','gus holds box cutter','[\"S0002\"]','SUPPORTED_VISUAL','x','{}','ff')")
        out=generate_v2(c,self.request());lanes={x.provenance[0]['lane'] for x in out};self.assertIn('ACTION',lanes);self.assertGreaterEqual(len(lanes),1)
    def test_v2_frame_refinement_rejects_timestamp(self):
        with self.assertRaises(ValidationError):RefineV2.model_validate({'request_id':'T','candidate_id':'C','decision':'SUPPORTED_INTERVAL','first_frame_index':1,'last_frame_index':2,'evidence_statement':'x','start_ms':3})
    def test_v2_candidate_forbids_extra(self):
        with self.assertRaises(ValidationError):CandidateV2.model_validate({'request_id':'T','decision':'NONE_OF_THESE','candidate_id':None,'supporting_shot_ids':[],'evidence_statement':'x','scene_id':'fake'})
    def test_v3_abstain_regions_but_no_export_authority(self):
        r=self.request('ABSTAIN');self.assertTrue(region_discovery_allowed(r));self.assertFalse(upstream_export_authorized(r))
    def test_v3_structured_paraphrase(self):
        r=self.request();r.scene_request.query_text='Gale gives the sample to Victor';s=normalize_request(r);self.assertEqual(s.action_family,'transfer');self.assertEqual(s.object,'sample')
    def test_v3_component_receipts_and_diversity(self):
        c=self.db();c.execute("insert into scene_retrieval_fragments(scene_id,fragment_type,objective_text,normalized_text,evidence_shot_ids_json,trust_status,source_fingerprint,provenance_json,fragment_fingerprint) values(1,'ACTION','Gus holds box cutter','gus holds box cutter','[\"S0002\"]','SUPPORTED_VISUAL','x','{}','ff')");out,_=rerank_v3(c,self.request());self.assertTrue(out);self.assertIn('component_scores',out[0].provenance[0])

if __name__=='__main__':unittest.main()
