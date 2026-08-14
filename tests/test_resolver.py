from __future__ import annotations

import json
import unittest
from pathlib import Path
from pydantic import ValidationError

from scenebrain.db import connect
from scenebrain.hashing import fingerprint
from scenebrain.resolver import EMBEDDING_MODEL,PROFILES,resolve_local,vector
from scenebrain.resolver_models import SceneRetrievalRequest
from scenebrain.scene_verifier import VerifierResponse,apply_verifier

ROOT=Path(__file__).resolve().parents[1]

class ResolverIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.conn=connect(ROOT/'runtime/scene_brain.db')
    @classmethod
    def tearDownClass(cls):cls.conn.close()

    def req(self,query,kind='EXACT_EVENT',**kw):return SceneRetrievalRequest(request_id='test',query_text=query,evidence_class=kind,**kw)

    def test_fragment_construction_and_provenance(self):
        n=self.conn.execute('select count(*) from scene_retrieval_fragments').fetchone()[0];self.assertGreater(n,900)
        row=self.conn.execute("select scene_id,provenance_json from scene_retrieval_fragments where fragment_type='EVENT' limit 1").fetchone();self.assertIsNotNone(json.loads(row['provenance_json'])['proposal_id'])

    def test_fts_ranking(self):
        rows=self.conn.execute("select f.fragment_type from scene_retrieval_fts join scene_retrieval_fragments f on f.id=scene_retrieval_fts.rowid where scene_retrieval_fts match 'box AND cutter'").fetchall();self.assertTrue(rows)

    def test_dialogue_maps_to_scene(self):
        r=resolve_local(self.conn,self.req('Get back to work','EXACT_DIALOGUE',dialogue_clue='Get back to work'));self.assertEqual(r.primary_scene,'S04E01_SC011')

    def test_semantic_index_versioning_and_determinism(self):
        self.assertEqual(vector('box cutter'),vector('box cutter'));self.assertIn('/1.0',EMBEDDING_MODEL)

    def test_evidence_profiles_differ(self):self.assertGreater(PROFILES['EXACT_DIALOGUE']['dialogue'],PROFILES['EXACT_EVENT']['dialogue'])

    def test_unsupported_character_is_soft(self):
        r=resolve_local(self.conn,self.req('Francesca Liddy in Saul office','CHARACTER_CONTEXT',characters_required=['Francesca Liddy'],exactness_policy='CONTEXT_OK'));self.assertTrue(r.candidates);self.assertLessEqual(r.candidates[0].channel_scores['character'],.35)

    def test_negative_constraint_penalty(self):
        r=resolve_local(self.conn,self.req('Gus kills Victor with box cutter',negative_constraints=['box cutter']));self.assertEqual(r.decision,'ABSTAIN');self.assertTrue(any(x.conflicts for x in r.candidates))

    def test_unresolved_scene_retained_and_neighbors(self):
        r=resolve_local(self.conn,self.req('Gus kills Victor box cutter'));c=next(x for x in r.candidates if x.scene_id=='S04E01_SC011');self.assertEqual(c.atlas_status,'UNRESOLVED');self.assertTrue(c.neighbors)

    def test_duplicate_candidates_collapsed(self):
        r=resolve_local(self.conn,self.req('laboratory'));ids=[x.scene_id for x in r.candidates];self.assertEqual(len(ids),len(set(ids)))

    def test_none_abstention(self):self.assertEqual(resolve_local(self.conn,self.req('dragon lands in swimming pool')).decision,'ABSTAIN')

    def test_gemini_none_of_these(self):
        local=resolve_local(self.conn,self.req('dragon lands'))
        out=apply_verifier(local,{'status':'SUCCESS','used':True,'response':{'request_id':'test','decision':'NONE_OF_THESE','candidate_scene_id':None,'evidence_shots':[],'reasoning':'none'}},self.req('dragon lands'));self.assertEqual(out.decision,'ABSTAIN')

    def test_malformed_verifier_response(self):
        with self.assertRaises(ValidationError):VerifierResponse.model_validate({'request_id':'x','decision':'LITERAL_MATCH','candidate_scene_id':'S1','evidence_shots':[],'reasoning':'x','timestamp':1})

    def test_stale_fingerprints_invalidate(self):
        self.assertNotEqual(fingerprint('atlas-a','prompt'),fingerprint('atlas-b','prompt'))

    def test_model_timestamp_forbidden(self):
        data={'request_id':'x','query_text':'x','evidence_class':'EXACT_EVENT','timestamp_ms':2}
        with self.assertRaises(ValidationError):SceneRetrievalRequest.model_validate(data)

if __name__=='__main__':unittest.main()
