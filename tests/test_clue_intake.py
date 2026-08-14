from scenebrain.clue_intake import validate_clue

def clue(narration="Walter waits.",**beat):
 return {"schema_version":"production-clue-script/4.0","canonical_events":[],"beats":[{"beat_id":"B001","narration":narration,"evidence_class":"EDITORIAL_CONTEXT",**beat}]}

def test_exact_and_punctuation_comparisons():
 assert validate_clue("Walter waits.",clue(),["Breaking Bad"])["comparison"]=="EXACT_MATCH"
 assert validate_clue("Walter waits!",clue(),["Breaking Bad"])["comparison"]=="PUNCTUATION_ONLY_DIFFERENCE"

def test_word_mismatch_and_scope_fail_closed():
 result=validate_clue("Walter leaves.",clue(source_title_preference="Better Call Saul"),["Breaking Bad"])
 assert not result["valid"]
 assert {x["code"] for x in result["errors"]}=={"NARRATION_MISMATCH","SOURCE_SCOPE"}

def test_self_declared_validation_is_not_trusted():
 value=clue("Different words.");value["validation"]={"all_narration_covered_once":True}
 assert not validate_clue("Original words.",value,["Breaking Bad"])["valid"]
