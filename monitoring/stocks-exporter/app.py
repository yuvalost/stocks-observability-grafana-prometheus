import os, time, threading, random, math
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Gauge, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest

# optional imports; we won't use them if DEMO_ONLY=true
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except Exception:
    yf = None
    pd = None
    np = None

from pathlib import Path

TICKERS_ENV  = os.getenv("TICKERS", "")
TICKERS_FILE = os.getenv("TICKERS_FILE", "/app/tickers.txt")
MAX_TICKERS  = int(os.getenv("MAX_TICKERS", "120"))
SLEEP_PER    = float(os.getenv("SLEEP_PER_SYMBOL", "0.15"))
REFRESH      = int(os.getenv("REFRESH_SECONDS", "60"))
DEMO         = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_ONLY    = os.getenv("DEMO_ONLY", "false").lower() == "true"

def load_tickers():
    items = []
    p = Path(TICKERS_FILE)
    if p.exists():
        raw = p.read_text(encoding="utf-8", errors="ignore")
        for part in raw.replace(",", "\n").splitlines():
            s = part.strip().upper()
            if s: items.append(s)
    if not items and TICKERS_ENV:
        items = [t.strip().upper() for t in TICKERS_ENV.split(",") if t.strip()]
    out, seen = [], set()
    for t in items:
        if t not in seen:
            out.append(t); seen.add(t)
    return out[:MAX_TICKERS]

registry = CollectorRegistry()
price_g   = Gauge("stock_price", "Last trade/close price", ["symbol"], registry=registry)
ok_g      = Gauge("stock_scrape_success", "1=ok,0=fail", ["symbol"], registry=registry)
rsi14_g   = Gauge("stock_rsi14", "RSI(14)", ["symbol"], registry=registry)
macd_g    = Gauge("stock_macd", "MACD line (12-26)", ["symbol"], registry=registry)
macdsig_g = Gauge("stock_macd_signal", "MACD signal (9)", ["symbol"], registry=registry)
macdh_g   = Gauge("stock_macd_hist", "MACD histogram", ["symbol"], registry=registry)
bbp_g     = Gauge("stock_bbp_20d", "Bollinger %B (20d)", ["symbol"], registry=registry)
ret1_g    = Gauge("stock_return_1d_percent", "1d return %", ["symbol"], registry=registry)
ret5_g    = Gauge("stock_return_5d_percent", "5d return %", ["symbol"], registry=registry)
ret20_g   = Gauge("stock_return_20d_percent", "20d return %", ["symbol"], registry=registry)
vol20_g   = Gauge("stock_vol_20d_annualized", "Realized vol 20d (annualized, %)", ["symbol"], registry=registry)
vol_g     = Gauge("stock_volume", "Volume (shares)", ["symbol"], registry=registry)
volavg_g  = Gauge("stock_volume_avg_20d", "Avg vol 20d (shares)", ["symbol"], registry=registry)
volrat_g  = Gauge("stock_volume_ratio", "Volume/Avg20d", ["symbol"], registry=registry)

last_price_cache = {}

def synth(sym):
    base = last_price_cache.get(sym, 100.0 + random.random()*20.0)
    step = random.gauss(0, 0.002)
    base *= (1.0 + step)
    last_price_cache[sym] = base
    return {"price": base, "rsi14": 50+random.gauss(0,10), "macd": random.gauss(0,1),
            "macdsig": random.gauss(0,1), "macdh": random.gauss(0,1), "bbp": random.uniform(0,100),
            "ret1": random.gauss(0,1), "ret5": random.gauss(0,3), "ret20": random.gauss(0,6),
            "rv20": abs(random.gauss(25,5)), "v_now": random.randint(1_000_000,5_000_000),
            "v_avg": random.randint(1_000_000,5_000_000), "v_ratio": random.uniform(0.5,2.5)}

def set_metrics(sym, d, ok):
    price_g.labels(sym).set(d["price"]);           ok_g.labels(sym).set(1 if ok else 0)
    rsi14_g.labels(sym).set(d["rsi14"]);           macd_g.labels(sym).set(d["macd"])
    macdsig_g.labels(sym).set(d["macdsig"]);       macdh_g.labels(sym).set(d["macdh"])
    bbp_g.labels(sym).set(d["bbp"])
    ret1_g.labels(sym).set(d["ret1"]);             ret5_g.labels(sym).set(d["ret5"])
    ret20_g.labels(sym).set(d["ret20"]);           vol20_g.labels(sym).set(d["rv20"])
    vol_g.labels(sym).set(d["v_now"]);             volavg_g.labels(sym).set(d["v_avg"])
    volrat_g.labels(sym).set(d["v_ratio"])

def fetch_loop():
    while True:
        tickers = load_tickers()
        for sym in tickers:
            try:
                if DEMO_ONLY or yf is None:   # <-- never hit network in demo-only mode
                    set_metrics(sym, synth(sym), False)
                else:
                    # try real data; on failure, optionally synth
                    t = yf.Ticker(sym)
                    df = t.history(period="90d", interval="1d", actions=False)
                    if df is None or df.empty:
                        raise RuntimeError("empty history")
                    import pandas as pd, numpy as np, math
                    close = df["Close"].astype(float)
                    vol   = df["Volume"].astype(float) if "Volume" in df.columns else close*0
                    # indicators (as before)
                    delta = close.diff()
                    gain  = (delta.clip(lower=0)).ewm(alpha=1/14, adjust=False).mean()
                    loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean().replace(0, np.nan)
                    rs    = gain / loss
                    rsi14 = float((100 - (100 / (1 + rs))).dropna().iloc[-1])
                    ema = lambda s, n: s.ewm(span=n, adjust=False).mean()
                    macd  = ema(close,12)-ema(close,26); macds=ema(macd,9); macdh=macd-macds
                    sma20 = close.rolling(20).mean(); std20=close.rolling(20).std(ddof=0)
                    bbp   = float(((close-(sma20-2*std20))/((sma20+2*std20)-(sma20-2*std20))*100).dropna().iloc[-1])
                    ret1  = float(close.pct_change(1).iloc[-1]*100)
                    ret5  = float(close.pct_change(5).iloc[-1]*100)
                    ret20 = float(close.pct_change(20).iloc[-1]*100)
                    lret  = np.log(close).diff(); rv20=float(lret.tail(20).std(ddof=0)*(252**0.5)*100)
                    v_now = float(vol.iloc[-1]) if len(vol) else 0.0
                    v_avg = float(vol.rolling(20).mean().iloc[-1]) if len(vol)>=20 else 0.0
                    v_ratio = float(v_now/v_avg) if v_avg>0 else 0.0
                    d = {"price": float(close.iloc[-1]), "rsi14": rsi14, "macd": float(macd.iloc[-1]),
                         "macdsig": float(macds.iloc[-1]), "macdh": float(macdh.iloc[-1]), "bbp": bbp,
                         "ret1": ret1, "ret5": ret5, "ret20": ret20, "rv20": rv20,
                         "v_now": v_now, "v_avg": v_avg, "v_ratio": v_ratio}
                    last_price_cache[sym] = d["price"]; set_metrics(sym, d, True)
            except Exception:
                # fallback
                if DEMO or DEMO_ONLY:
                    set_metrics(sym, synth(sym), False)
                else:
                    if sym in last_price_cache: price_g.labels(sym).set(last_price_cache[sym])
                    ok_g.labels(sym).set(0)
            time.sleep(SLEEP_PER)
        time.sleep(REFRESH)

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404); self.end_headers(); return
        out = generate_latest(registry)
        self.send_response(200); self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(out))); self.end_headers()
        self.wfile.write(out)

if __name__ == "__main__":
    threading.Thread(target=fetch_loop, daemon=True).start()
    HTTPServer(("0.0.0.0", 9400), MetricsHandler).serve_forever()