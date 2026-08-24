#!/usr/bin/env bash
# Assemble the deployable site: the PWA plus the data file it fetches at runtime.
set -euo pipefail
rm -rf _site
mkdir -p _site/data
cp -r web/. _site/
# The phone does not need 2 MB of ad text to draw a list. It gets a preview and
# a full_text flag; the whole ad stays server-side for the drafting endpoint.
python3 - <<'PYEOF'
import json
jobs = json.load(open("data/jobs.json"))
# Only the fields the list actually draws or filters on. Repeated key names were
# 1.2 MB of the payload on their own, and the ad text is shown in full only by
# the drafting endpoint, which reads the unabridged file server-side.
FIELDS = ("id title company location country url source source_type score score_reason "
          "skills salary salary_inr employment_type experience_required remote "
          "visa_sponsorship role_summary expectations hiring_process seniority_fit last_seen "
          "first_seen").split()
PREVIEW = 160
slim = []
for j in jobs:
    desc = j.get("description") or ""
    row = {k: j[k] for k in FIELDS if k in j and j[k] not in (None, "", [], "not stated")}
    row["description"] = desc[:PREVIEW]
    if len(desc) > 520:
        row["full_text"] = True
    slim.append(row)
json.dump(slim, open("_site/data/jobs.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(jobs, open("_site/data/jobs.full.json", "w"), ensure_ascii=False, separators=(",", ":"))
PYEOF
cp data/meta.json _site/data/meta.json 2>/dev/null || true
# the draft endpoint needs the profile; yaml is not readable from a Worker
python3 -c "from pipeline.config import load_profile;import json;json.dump(load_profile(),open('_site/data/profile.json','w'))"
rm -rf _site/data/.gitkeep
echo "_site ready: $(du -sh _site | cut -f1), $(find _site -type f | wc -l) files"
