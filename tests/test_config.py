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

def test_country_codes_survive_yaml_truthiness():
    """YAML 1.1 reads bare NO as false; Norway was silently dropped for weeks."""
    cfg = load_config("config.yaml")
    codes = cfg["countries"]
    assert all(isinstance(c, str) for c in codes), codes
    for code in ("NO", "CH", "DE", "SE", "DK", "FI"):
        assert code in codes, f"{code} missing from {codes}"
