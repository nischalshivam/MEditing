import unittest
from scenebrain.repair_v13 import *
class RepairTests(unittest.TestCase):
 def test_callback_general(self):
  xs=compile_v2([{'exact_narration':'Money event','canonical_event_id':'MONEY','primary_subjects':['Skyler'],'location_clues':[],'evidence_class':'EXACT_EVENT'},{'exact_narration':'That failure mattered','canonical_event_id':'NONE / EDITORIAL','primary_subjects':['Skyler'],'location_clues':[],'evidence_class':'EDITORIAL_CONTEXT'}]);self.assertEqual(xs[1]['context_anchor_event_ids'],['MONEY'])
 def test_repair_isolation(self):
  a={'decisions':[{'decision':'PROJECT_SLOT_APPROVAL','original_color':'YELLOW'},{'decision':'NONE_GOOD','original_color':'YELLOW'},{'decision':'PROJECT_SLOT_APPROVAL','original_color':'ORANGE_UNRESOLVED'}]};self.assertEqual(len(repair_set(a)),1)
