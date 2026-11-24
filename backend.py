import os
import time
import json
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAIR = "ETHUSD"
SCAN_INTERVAL = 15
STARTING_EQUITY = 5000.0
RISK_PER_TRADE = 20.0
OVERALL_FLOOR = 4700.0
DAILY_THRESHOLD = 4792.26
MAX_LEVERAGE = 5

LOCK = threading.Lock()

STATE = {
    "system": "ETH EDGE COMMANDER V2",
    "mode": "PAPER",
    "status": "STARTING",
    "price": None,
    "equity": STARTING_EQUITY,
    "risk_per_trade": RISK_PER_TRADE,
    "overall_floor": OVERALL_FLOOR,
    "daily_threshold": DAILY_THRESHOLD,
    "max_leverage": MAX_LEVERAGE,
    "real_execution": False,
    "paper_execution": False,
    "verdict": "WAIT",
    "scans": 0,
    "updated": None,
    "error": None
}


def kraken_request(endpoint, params=""):
    url = (
        "https://api.kraken.com/0/public/"
        + endpoint + "?" + params
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ETH-Edge-Commander/2.0"}
    )

    with urllib.request.urlopen(
        request, timeout=15
    ) as response:
        data = json.loads(response.read())

    if data.get("error"):
        raise RuntimeError(str(data["error"]))

    return data["result"]


def get_price():
    result = kraken_request(
        "Ticker", "pair=" + PAIR
    )

    ticker = next(iter(result.values()))
    return float(ticker["c"][0])


def get_candles(interval):
    result = kraken_request(
        "OHLC",
        f"pair={PAIR}&interval={interval}"
    )

    for key, candles in result.items():
        if key != "last":
            return candles[:-1]

    raise RuntimeError("No candle data")


def scan_market():
    while True:
        try:
            price = get_price()

            with LOCK:
                STATE.update({
                    "price": price,
                    "status": "ONLINE",
                    "verdict": "WAIT",
                    "updated": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "error": None
                })

                STATE["scans"] += 1

            print(
                f"ETH/USD: ${price:.2f} | "
                f"Scan: {STATE['scans']}",
                flush=True
            )

        except Exception as error:
            with LOCK:
                STATE.update({
                    "status": "DATA_ERROR",
                    "verdict": "NO TRADE",
                    "error": str(error)
                })

            print(
                f"Scanner error: {error}",
                flush=True
            )

        time.sleep(SCAN_INTERVAL)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path not in (
            "/", "/status", "/health"
        ):
            self.send_error(404)
            return

        with LOCK:
            snapshot = dict(STATE)

        payload = json.dumps(snapshot).encode()

        self.send_response(200)
        self.send_header(
            "Content-Type", "application/json"
        )
        self.send_header(
            "Access-Control-Allow-Origin", "*"
        )
        self.send_header(
            "Cache-Control", "no-store"
        )
        self.send_header(
            "Content-Length", str(len(payload))
        )
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print(
        "ETH EDGE COMMANDER V2 starting",
        flush=True
    )

    scanner = threading.Thread(
        target=scan_market,
        daemon=True
    )

    scanner.start()

    port = int(os.environ.get("PORT", 10000))

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()
