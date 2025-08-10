Stocks Observability — Grafana + Prometheus (Docker)
A one-click dashboard to explore stocks like an SRE.
Grafana** visualizations powered by Prometheus and a tiny Python exporter.

Runs in demo mode by default (no API keys, no external calls).
Flip one switch for real quotes later. Not financial advice.

Why this is interesting (for recruiters)
Hands-on observability: dashboards, alerts, time-series rules.
Production-y setup: Docker Compose, provisioning, healthchecks.
Signal-rich views: % change over range, RSI, MACD, Bollinger %B, volume spikes, volatility, RS vs SPY, breadth.
Tools: Docker · Grafana · Prometheus · Python (prometheus_client, optional yfinance)

See it in 60 seconds
# from repo root
docker compose up -d --build

# Open:
# Grafana    -> http://localhost:3000  (admin / admin)
# Prometheus -> http://localhost:9090

Dashboards (Grafana → folder Stocks):

Stocks – Full (Range): Prices, RS vs SPY, Top/Bottom movers, RSI extremes, Volume spikes, Drawdown/Up-from-low, MACD, %B.

Demo data is on by default, so everything has numbers immediately.

Switch to real prices (optional)
In docker-compose.yml, under the exporter(s):

yaml
Copy
Edit
DEMO_ONLY: "false"   # turn off synthetic-only mode
DEMO_MODE: "true"    # keep as soft fallback
SLEEP_PER_SYMBOL: 0.25   # throttle kindly
MAX_TICKERS: 100-150     # per exporter

docker compose up -d --build stocks-exporter   # or -1/-2/-3 if sharded

Repo at a glance
bash
Copy
Edit
docker-compose.yml
grafana/provisioning/      # datasource + dashboards (auto-loaded)
prometheus/prometheus.yml  # scrapes exporters
prometheus/rules/          # range % change, breadth, alerts
stocks-exporter/           # Python exporter + tickers files
Highlights to mention
Built dashboards & rules from scratch, auto-provisioned via code.

Sharded exporters for scale; range-based PromQL for instant visuals.

Clean Docker setup that works on Windows/macOS/Linux.
