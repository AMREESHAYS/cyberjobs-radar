#!/usr/bin/env bash
# Assemble the deployable site: the PWA plus the data file it fetches at runtime.
set -euo pipefail
rm -rf _site
mkdir -p _site/data
cp -r web/. _site/
cp data/jobs.json _site/data/jobs.json
cp data/meta.json _site/data/meta.json 2>/dev/null || true
rm -rf _site/data/.gitkeep
echo "_site ready: $(du -sh _site | cut -f1), $(find _site -type f | wc -l) files"
