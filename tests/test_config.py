from pipeline.config import load_config, load_profile

def test_config_has_countries_and_terms(tmp_path, monkeypatch):
    p = tmp_path / "config.yaml"
    p.write_text("countries: [CH, DE, SE]\nsearch_terms: [security]\nage_out_days: 45\n")
    monkeypatch.setenv("GROQ_API_KEY", "sk-test")
    cfg = load_config(str(p))
    assert cfg["countries"] == ["CH", "DE", "SE"]
    assert cfg["secrets"]["GROQ_API_KEY"] == "sk-test"

def test_profile_loads(tmp_path):
    p = tmp_path / "profile.yaml"
    p.write_text("experience: junior\nneeds_sponsorship: true\nroles: [soc, pentest]\n")
    prof = load_profile(str(p))
    assert prof["needs_sponsorship"] is True
