import json
from pipeline.ai import analyze, build_client
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

def test_build_client_disabled_when_no_key_for_hosted_provider():
    cfg = {"secrets": {}, "ai": {"base_url_default": "https://api.groq.com/openai/v1",
                                  "model_default": "llama-3.3-70b-versatile"}}
    client, model = build_client(cfg)
    assert client is None
    assert model is not None


def test_build_client_uses_ai_api_key_for_any_provider(monkeypatch):
    # shadow the openai package so this runs whether or not it is installed
    import sys, types
    captured = {}
    fake = types.ModuleType("openai")
    class FakeOpenAI:
        def __init__(self, base_url=None, api_key=None, **kwargs):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured.update(kwargs)
    fake.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake)
    from pipeline.ai import build_client
    cfg = {"secrets": {"AI_API_KEY": "nvapi-xyz",
                       "AI_BASE_URL": "https://integrate.api.nvidia.com/v1",
                       "AI_MODEL": "meta/llama-3.3-70b-instruct"}, "ai": {}}
    client, model = build_client(cfg)
    assert client is not None
    assert captured["api_key"] == "nvapi-xyz"
    assert captured["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert model == "meta/llama-3.3-70b-instruct"
