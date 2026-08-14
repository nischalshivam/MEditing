import unittest
from scenebrain.sprint13_audit_server import freeze
class AuditTests(unittest.TestCase):
 def test_no_decision_fabrication(self):
  with self.assertRaises(ValueError):freeze({'local_storage_key':'wrong','decisions':{}})
