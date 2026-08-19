#!/usr/bin/env bash
# CyberJobs Radar — one command: refresh jobs, serve the PWA, expose it to your phone.
#
#   ./run.sh          fetch + serve locally at http://localhost:8000/
#   ./run.sh --tunnel fetch + serve + a public phone-reachable URL via cloudflared
#
# Put your keys in .env first (cp .env.example .env). Works without keys too
# (Sweden + remote jobs, no AI scores).
set -euo pipefail
cd "$(dirname "$0")"

PORT=8000
[ -f .env ] && { set -a; . ./.env; set +a; }

echo "▸ fetching jobs…"
python -m pipeline.run

# mirror the deploy layout so index.html finds data/jobs.json beside it
mkdir -p web/data && cp data/jobs.json web/data/

echo "▸ serving http://localhost:$PORT/"
python -m http.server "$PORT" -d web >/tmp/cyberjobs-serve.log 2>&1 &
SERVE_PID=$!
trap 'kill $SERVE_PID 2>/dev/null || true' EXIT

if [ "${1:-}" = "--tunnel" ]; then
  if ! command -v cloudflared >/dev/null; then
    echo "cloudflared not found. Install it, or open http://localhost:$PORT/ on this machine."
    echo "  Debian/Kali: sudo apt install cloudflared   (or grab the binary from Cloudflare)"
  else
    echo "▸ opening public tunnel (scan/tap the trycloudflare URL below on your phone)…"
    cloudflared tunnel --url "http://localhost:$PORT"
    exit 0
  fi
fi

echo "▸ running. Ctrl+C to stop."
wait $SERVE_PID
