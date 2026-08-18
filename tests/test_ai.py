import json
from pipeline.ai import analyze
from pipeline.models import Job, make_id, NOT_STATED

class FakeResp:
    def __init__(self, content): self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

class FakeClient:
    def __init__(self, content): self._c = content; self.chat = self
    @property
    def completions(self): return self
    def create(self, **kw): return FakeResp(self._c)

def _job():
    return Job(id=make_id("s","1","https://x/1"), title="SOC Analyst Intern",
               company="ACME", location="Zurich", country="CH",
               url="https://x/1", source="s", source_type="api",
               description="Monitor SIEM alerts. Sponsorship available.")

def test_analyze_fills_fields_and_preserves_not_stated():
    content = json.dumps({"score": 82, "score_reason": "entry SOC + sponsorship",
                          "skills": ["SIEM", "log analysis"], "hiring_process": NOT_STATED,
                          "seniority_fit": "intern/junior"})
    j = _job()
    analyze(j, {"needs_sponsorship": True}, FakeClient(content), "m")
    assert j.score == 82
    assert j.skills == ["SIEM", "log analysis"]
    assert j.hiring_process == NOT_STATED

def test_analyze_survives_bad_json():
    j = _job()
    analyze(j, {}, FakeClient("not json at all"), "m")
    assert j.score is None
    assert j.score_reason == "AI unavailable"
    assert j.hiring_process == NOT_STATED

def test_analyze_survives_client_error():
    class FakeResp:
        def __init__(self, content): self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

    class FakeClient:
        def __init__(self, content): self._c = content; self.chat = self
        @property
        def completions(self): return self
        def create(self, **kw): return FakeResp(self._c)
    class Boom:
        chat = property(lambda self: self)
        def create(self, **kw): raise RuntimeError("429")
    j = _job()
    # Boom needs chat.completions.create; emulate:
    class Boom2:
        def __init__(self): self.chat = self
        @property
        def completions(self): return self
        def create(self, **kw): raise RuntimeError("429")
    analyze(j, {}, Boom2(), "m")
    assert j.score is None and j.score_reason == "AI unavailable"
