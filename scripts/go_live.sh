#!/bin/zsh
# Start the app and a temporary Cloudflare tunnel, then print the public URL.
#   scripts/go_live.sh          start (refuses to run without APP_PASSWORD in .env)
#   scripts/go_live.sh --stop   stop the tunnel (the app keeps running locally)
# The *.trycloudflare.com address changes every time the tunnel restarts.
cd "$(dirname "$0")/.." || exit 1
if [[ "$1" == "--stop" ]]; then pkill -f "cloudflared tunnel" && echo "tunnel stopped"; exit 0; fi
grep -q '^APP_PASSWORD=.' .env 2>/dev/null || { echo "Set APP_PASSWORD in .env first — the site must not go public without a password."; exit 1; }
mkdir -p logs
pgrep -f "streamlit run app.py" >/dev/null || (nohup .venv/bin/streamlit run app.py --server.port 8501 --server.headless true > logs/streamlit.log 2>&1 &)
pkill -f "cloudflared tunnel" 2>/dev/null; sleep 1
(nohup cloudflared tunnel --no-autoupdate --url http://localhost:8501 > logs/tunnel.log 2>&1 &)
for i in {1..30}; do
  url=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" logs/tunnel.log | head -1)
  [[ -n "$url" ]] && { echo "Live at: $url  (password is APP_PASSWORD in .env)"; exit 0; }
  sleep 2
done
echo "Tunnel did not start — see logs/tunnel.log"; exit 1
