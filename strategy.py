from math import isfinite

MIN_CANDLES = 25
MIN_STOP_ATR = 0.5
MAX_STOP_ATR = 3.0
TP1_R = 1.5
TP2_R = 3.0


def normalize(candles):
    result = []

    for c in candles:
        result.append({
            "time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4])
        })

    return sorted(
        result, key=lambda c: c["time"]
    )


def atr(candles, period=14):
    if len(candles) < period + 1:
        return 0

    ranges = []

    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i - 1]

        ranges.append(max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"])
        ))

    return sum(ranges[-period:]) / period


def market_trend(candles):
    recent = candles[-10:]
    previous = candles[-20:-10]

    recent_high = max(c["high"] for c in recent)
    recent_low = min(c["low"] for c in recent)

    previous_high = max(c["high"] for c in previous)
    previous_low = min(c["low"] for c in previous)

    if (
        recent_high > previous_high
        and recent_low > previous_low
    ):
        return "BULLISH"

    if (
        recent_high < previous_high
        and recent_low < previous_low
    ):
        return "BEARISH"

    return "RANGE"


def build_setup(
    family, direction, entry,
    stop, volatility, score, reason
):
    distance = abs(entry - stop)

    if not all(isfinite(v) for v in (
        entry, stop, volatility, distance
    )):
        return None

    if volatility <= 0 or distance <= 0:
        return None

    if direction == "LONG" and stop >= entry:
        return None

    if direction == "SHORT" and stop <= entry:
        return None

    if distance < volatility * MIN_STOP_ATR:
        return None

    if distance > volatility * MAX_STOP_ATR:
        return None

    sign = 1 if direction == "LONG" else -1

    return {
        "family": family,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "tp1": entry + sign * distance * TP1_R,
        "tp2": entry + sign * distance * TP2_R,
        "stop_distance": distance,
        "reward_risk": TP2_R,
        "score": score,
        "reason": reason,
        "atr": volatility
    }


def trend_continuation(h1, m15, m5):
    trend = market_trend(h1)
    structure = market_trend(m15)

    trigger = m5[-1]
    previous = m5[-2]
    pullback = m5[-5:-1]

    volatility = atr(m5)
    entry = trigger["close"]
    buffer = volatility * 0.15

    if (
        trend == "BULLISH"
        and structure != "BEARISH"
        and previous["close"] < previous["open"]
        and trigger["close"] > previous["high"]
        and trigger["close"] > trigger["open"]
    ):
        stop = min(
            c["low"] for c in pullback + [trigger]
        ) - buffer

        return build_setup(
            "TREND_CONTINUATION",
            "LONG", entry, stop,
            volatility,
            85 if structure == "BULLISH" else 75,
            "Bullish structure and pullback breakout"
        )

    if (
        trend == "BEARISH"
        and structure != "BULLISH"
        and previous["close"] > previous["open"]
        and trigger["close"] < previous["low"]
        and trigger["close"] < trigger["open"]
    ):
        stop = max(
            c["high"] for c in pullback + [trigger]
        ) + buffer

        return build_setup(
            "TREND_CONTINUATION",
            "SHORT", entry, stop,
            volatility,
            85 if structure == "BEARISH" else 75,
            "Bearish structure and pullback breakdown"
        )

    return None


def liquidity_reversal(h1, m15, m5):
    trend = market_trend(h1)
    trigger = m5[-1]
    sweep = m5[-2]

    reference = m5[-22:-2]

    support = min(c["low"] for c in reference)
    resistance = max(c["high"] for c in reference)

    volatility = atr(m5)
    entry = trigger["close"]
    buffer = volatility * 0.15

    if (
        trend != "BEARISH"
        and sweep["low"] < support
        and sweep["close"] > support
        and trigger["close"] > sweep["high"]
    ):
        return build_setup(
            "LIQUIDITY_REVERSAL",
            "LONG", entry,
            min(sweep["low"], trigger["low"]) - buffer,
            volatility, 80,
            "Support sweep, reclaim and confirmation"
        )

    if (
        trend != "BULLISH"
        and sweep["high"] > resistance
        and sweep["close"] < resistance
        and trigger["close"] < sweep["low"]
    ):
        return build_setup(
            "LIQUIDITY_REVERSAL",
            "SHORT", entry,
            max(sweep["high"], trigger["high"]) + buffer,
            volatility, 80,
            "Resistance sweep and bearish confirmation"
        )

    return None


def analyze_market(raw_h1, raw_m15, raw_m5):
    h1 = normalize(raw_h1)
    m15 = normalize(raw_m15)
    m5 = normalize(raw_m5)

    if min(len(h1), len(m15), len(m5)) < MIN_CANDLES:
        return {
            "verdict": "WAIT",
            "reason": "Insufficient candle history",
            "setup": None
        }

    candidates = []

    for strategy in (
        trend_continuation,
        liquidity_reversal
    ):
        candidate = strategy(h1, m15, m5)

        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        return {
            "verdict": "WAIT",
            "trend": market_trend(h1),
            "structure": market_trend(m15),
            "reason": "No qualifying setup",
            "setup": None
        }

    directions = {
        c["direction"] for c in candidates
    }

    if len(directions) > 1:
        return {
            "verdict": "NO TRADE",
            "reason": "Conflicting strategy signals",
            "setup": None
        }

    best = max(
        candidates, key=lambda c: c["score"]
    )

    return {
        "verdict": "CANDIDATE",
        "trend": market_trend(h1),
        "structure": market_trend(m15),
        "signal_time": m5[-1]["time"],
        "reason": best["reason"],
        "setup": best,
        "candidates": candidates
    }
