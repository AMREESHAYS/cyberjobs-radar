import json
from pipeline.ai import analyze, build_client, _coerce, PROMPT
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
                                  "model_default": "openai/gpt-oss-120b"}}
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

def test_coerce_keeps_only_explicit_sponsorship_answers():
    job = _job()
    _coerce(job, {"score": 70, "visa_sponsorship": "YES", "role_summary": "Run the SOC.",
                  "expectations": "Two years of blue-team work."})
    assert job.visa_sponsorship == "yes"
    assert job.role_summary == "Run the SOC."
    assert job.expectations == "Two years of blue-team work."
    for improvised in ("probably", "likely not", "", None, "maybe"):
        j = _job()
        _coerce(j, {"score": 70, "visa_sponsorship": improvised})
        assert j.visa_sponsorship == NOT_STATED

def test_coerce_defaults_the_new_fields_to_not_stated():
    job = _job()
    _coerce(job, {"score": 50})
    assert job.role_summary == job.expectations == job.visa_sponsorship == NOT_STATED

from pipeline.ai import condense

def test_condense_keeps_requirements_stated_below_the_cutoff():
    filler = "We are a great company with a great mission. " * 60   # >2200 chars
    ad = filler + "\n\nWhat you bring: 5+ years of experience in incident response. " \
                  "A degree in computer science. We sponsor work permits."
    out = condense(ad)
    assert "5+ years of experience" in out       # the whole point
    assert "sponsor work permits" in out
    assert len(out) < len(ad)                    # still cheaper than sending it all

def test_condense_drops_marketing_prose_from_the_tail():
    ad = "x" * 2200 + "\n\nOur office has a ping pong table. We love oat milk lattes."
    out = condense(ad)
    assert "ping pong" not in out and "lattes" not in out

def test_condense_leaves_short_ads_alone():
    ad = "Security analyst wanted. 3 years of experience required."
    assert condense(ad) == ad

def test_prompt_demands_english_and_a_translated_title():
    assert "ALWAYS answer in English" in PROMPT
    assert "title_en" in PROMPT
    assert "gender tag" in PROMPT

def test_coerce_keeps_the_english_title():
    job = _job()
    _coerce(job, {"score": 60, "title_en": "IT Security Specialist"})
    assert job.title_en == "IT Security Specialist"
    j2 = _job()
    _coerce(j2, {"score": 60})
    assert j2.title_en == ""      # nothing invented when the model omits it
