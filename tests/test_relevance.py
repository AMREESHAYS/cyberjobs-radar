from pipeline.relevance import is_out_of_reach, drop_out_of_reach, dedupe, _patterns
from pipeline.models import Job

P = _patterns({})

def _job(jid, title="Security Analyst", company="Acme", country="CH",
         location="Zurich", score=None, desc="security work", version=0):
    return Job(id=jid, title=title, company=company, location=location, country=country,
               url=f"https://b.test/{jid}", source="s", source_type="api",
               description=desc, score=score, analysis_version=version)

def test_senior_titles_are_out_of_reach():
    for t in ["Senior Security Engineer", "Lead SOC Analyst", "Head of Security",
              "Security Architect", "Principal Engineer", "IT Security Manager",
              "Teamlead Cyber Defence", "Leiterin Informationssicherheit",
              "Security Engineer with 8+ years"]:
        assert is_out_of_reach(t, P) is True, t

def test_entry_level_titles_are_kept():
    for t in ["Security Analyst", "Junior Security Engineer", "Graduate Cyber Analyst",
              "Security Internship", "Werkstudent IT-Security", "SOC Analyst (m/w/d)",
              "Praktikum Informationssicherheit"]:
        assert is_out_of_reach(t, P) is False, t

def test_an_explicit_junior_marker_beats_a_senior_word():
    # boards do post "Junior Security Manager"; that is still worth seeing
    assert is_out_of_reach("Junior Security Manager", P) is False
    assert is_out_of_reach("Graduate Programme - Security Architect", P) is False

def test_drop_out_of_reach_splits_the_list():
    kept, dropped = drop_out_of_reach(
        [_job("a", "Security Analyst"), _job("b", "Senior Security Analyst")], {})
    assert [j.id for j in kept] == ["a"] and [j.id for j in dropped] == ["b"]

def test_dedupe_collapses_one_posting_spread_over_cities():
    jobs = [_job("1", location="Wrocław"), _job("2", location="Lublin"),
            _job("3", location="Kraków")]
    kept, dropped = dedupe(jobs)
    assert len(kept) == 1 and len(dropped) == 2
    assert kept[0].location == "Wrocław +2 more locations"   # no city silently lost

def test_dedupe_keeps_the_copy_with_the_ai_work():
    plain = _job("plain", desc="short")
    analysed = _job("analysed", score=72, version=5, desc="a much longer description")
    kept, _ = dedupe([plain, analysed])
    assert kept[0].id == "analysed"

def test_dedupe_does_not_merge_across_countries():
    kept, dropped = dedupe([_job("ch", country="CH"), _job("de", country="DE")])
    assert len(kept) == 2 and dropped == []

def test_dedupe_leaves_different_jobs_alone():
    kept, _ = dedupe([_job("a", "Security Analyst"), _job("b", "Cloud Security Engineer")])
    assert len(kept) == 2

from pipeline.relevance import is_on_topic, drop_off_topic

def test_off_topic_postings_are_recognised():
    # these all reached the store when adzuna's what_or matched "junior"
    for title in ["Chef de Partie", "Pflegefachkraft für den Nachtdienst",
                  "Machine Operator Leeuwarden", "Konditor - Backwaren"]:
        assert is_on_topic(_job("x", title, desc="Prepare food.")) is False, title

def test_security_postings_survive_in_every_language_we_fetch():
    for title, desc in [("SOC Analyst", "monitor alerts"),
                        ("Junior Cyber Analyst", "cyber security team"),
                        ("Informatiker", "IT-Sicherheit und Netzwerke"),
                        ("Medewerker", "informatiebeveiliging en netwerk")]:
        assert is_on_topic(_job("y", title, desc=desc)) is True, title

def test_drop_off_topic_splits_the_list():
    kept, dropped = drop_off_topic([_job("a", "SOC Analyst", desc="security"),
                                    _job("b", "Chef de Partie", desc="desserts")])
    assert [j.id for j in kept] == ["a"] and [j.id for j in dropped] == ["b"]
