import os
import time
import json
import copy
import threading
import urllib.request

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)

from strategy import analyze_market
from risk import approve_trade
from paper import PaperEngine
from storage import Storage

from notifications import (
    startup_alert,
    trade_alert,
    exit_alert,
    lockout_alert
)

PAIR = "ETHUSD"
SCAN_INTERVAL = 5
ANALYSIS_INTERVAL = 30

STARTING_EQUITY = 5000.0
OVERALL_FLOOR = 4700.0
DAILY_THRESHOLD = 4792.26

LOCK = threading.Lock()

engine = PaperEngine(STARTING_EQUITY)
storage = Storage()

restored = storage.restore(engine)

STATE = {
    "system": "ETH EDGE COMMANDER V2",
    "mode": "PAPER",
    "status": "STARTING",
    "market_source": "Kraken Spot",
    "real_execution": False,
    "paper_execution": True,
    "price": None,
    "verdict": "WAIT",
    "reason": "Initializing",
    "scans": 0,
    "updated": None,
    "error": None,
    "restored_account": restored
}


def publish(**values):
    with LOCK:
        STATE.update(copy.deepcopy(values))


def kraken_request(endpoint, params):
    url = (
        "https://api.kraken.com/0/public/"
        + endpoint + "?" + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ETH-Edge-Commander/2.0"
        }
    )

    with urllib.request.urlopen(
        request, timeout=10
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

    raise RuntimeError("Missing candles")


def notify(function, *args):
    threading.Thread(
        target=function,
        args=copy.deepcopy(args),
        daemon=True
    ).start()


def persist(events=None):
    try:
        storage.save(engine, events)
    except Exception:
        engine.trading_locked = True
        engine.lock_reason = "Database failure"
        raise


def scan_market():
    last_analysis = 0
    last_candle = None
    scans = 0
    announced = False

    verdict = "WAIT"
    reason = "Monitoring market"
    analysis = None
    approval = None

    while True:
        try:
            price = get_price()
            scans += 1

            was_locked = engine.trading_locked

            exits = engine.update_price(
                price,
                OVERALL_FLOOR,
                DAILY_THRESHOLD
            )

            events = [
                {
                    "type": "EXIT",
                    "data": event
                }
                for event in exits
                if event
            ]

            persist(events)

            if not announced:
                notify(
                    startup_alert,
                    engine.equity(price)
                )
                announced = True

            for event in exits:
                if event:
                    notify(
                        exit_alert,
                        event,
                        engine.equity(price)
                    )

            if (
                engine.trading_locked
                and not was_locked
            ):
                notify(
                    lockout_alert,
                    engine.lock_reason,
                    engine.equity(price)
                )

            if engine.trading_locked:
                verdict = "NO TRADE"
                reason = engine.lock_reason

            elif engine.position:
                verdict = "HOLD"
                reason = "Managing open position"

            elif (
                time.monotonic() - last_analysis
                >= ANALYSIS_INTERVAL
            ):
                last_analysis = time.monotonic()

                h1 = get_candles(60)
                m15 = get_candles(15)
                m5 = get_candles(5)

                analysis = analyze_market(
                    h1, m15, m5
                )

                verdict = analysis["verdict"]
                reason = analysis["reason"]

                setup = analysis.get("setup")

                if setup:
                    signal_time = analysis[
                        "signal_time"
                    ]

                    signal_id = (
                        f"{PAIR}-"
                        f"{signal_time}"
                    )

                    age = (
                        time.time()
                        - signal_time
                        - 300
                    )

                    if not 0 <= age <= 90:
                        verdict = "WAIT"
                        reason = "Signal is stale"

                    elif signal_time == last_candle:
                        verdict = "WAIT"
                        reason = "Candle already evaluated"

                    elif signal_id in engine.used_signals:
                        verdict = "WAIT"
                        reason = "Signal already traded"

                    else:
                        last_candle = signal_time

                        price = get_price()

                        original_entry = setup["entry"]

                        drift = abs(
                            price - original_entry
                        )

                        max_drift = (
                            setup["stop_distance"]
                            * 0.15
                        )

                        if drift > max_drift:
                            verdict = "NO TRADE"
                            reason = "Entry price moved"

                        else:
                            setup = dict(setup)
                            setup["entry"] = price

                            approval = approve_trade(
                                setup=setup,
                                equity=engine.equity(price),
                                overall_floor=OVERALL_FLOOR,
                                daily_threshold=DAILY_THRESHOLD,
                                open_position=False,
                                trading_locked=(
                                    engine.trading_locked
                                ),
                                signal_id=signal_id,
                                last_signal_id=(
                                    engine.last_signal_id
                                )
                            )

                            verdict = approval["verdict"]
                            reason = approval["reason"]

                            if approval["approved"]:
                                opened = engine.open_trade(
                                    approval,
                                    price
                                )

                                if opened:
                                    persist([{
                                        "type": "ENTRY",
                                        "data": approval
                                    }])

                                    notify(
                                        trade_alert,
                                        approval
                                    )

                                else:
                                    verdict = "NO TRADE"
                                    reason = "Entry rejected"

            stats = engine.statistics(price)

            publish(
                status="ONLINE",
                price=price,
                scans=scans,
                verdict=verdict,
                reason=reason,
                analysis=analysis,
                approval=approval,
                account=stats,
                equity=stats["equity"],
                overall_floor=OVERALL_FLOOR,
                daily_threshold=DAILY_THRESHOLD,
                history=engine.history[-100:],
                updated=datetime.now(
                    timezone.utc
                ).isoformat(),
                error=None
            )

            print(
                f"ETH ${price:.2f} | "
                f"{verdict} | "
                f"Equity ${stats['equity']:.2f}",
                flush=True
            )

        except Exception as error:
            publish(
                status="ERROR",
                verdict="NO TRADE",
                reason="Engine or data error",
                error=str(error)
            )

            print(
                f"Engine error: {error}",
                flush=True
            )

            time.sleep(15)

        time.sleep(SCAN_INTERVAL)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path not in (
            "/", "/status", "/health"
        ):
            self.send_error(404)
            return

        with LOCK:
            snapshot = copy.deepcopy(STATE)

        if self.path == "/health":
            snapshot = {
                "status": snapshot["status"]
            }

        payload = json.dumps(
            snapshot,
            allow_nan=False
        ).encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.send_header(
            "Content-Length",
            str(len(payload))
        )

        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    scanner = threading.Thread(
        target=scan_market,
        daemon=True
    )

    scanner.start()

    port = int(
        os.environ.get("PORT", 10000)
    )

    print(
        f"Commander listening on {port}",
        flush=True
    )

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()
