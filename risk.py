import math

STARTING_EQUITY = 5000.0
BASE_RISK = 20.0
RISK_PERCENT = 0.004
MAX_LEVERAGE = 5.0

OVERALL_FLOOR = 4700.0
DAILY_THRESHOLD = 4792.26

COMMISSION = 0.0004
SLIPPAGE = 0.0002

MIN_NET_RR = 1.5
SAFETY_BUFFER = 10.0
MAX_HEADROOM_RISK = 0.10
QUANTITY_STEP = 0.0001


def reject(reason):
    return {
        "approved": False,
        "verdict": "REJECTED",
        "reason": reason,
        "quantity": 0
    }


def calculate_risk(
    equity,
    overall_floor,
    daily_threshold
):
    floor = max(
        overall_floor,
        daily_threshold
    )

    headroom = equity - floor
    available = headroom - SAFETY_BUFFER

    if available <= 0:
        return 0

    scaled_risk = equity * RISK_PERCENT

    protected_risk = (
        available * MAX_HEADROOM_RISK
    )

    return max(
        0,
        min(scaled_risk, protected_risk)
    )


def execution_price(price, side):
    if side == "BUY":
        return price * (1 + SLIPPAGE)

    return price * (1 - SLIPPAGE)


def trade_pnl(
    direction,
    entry,
    exit_price,
    quantity
):
    sign = 1 if direction == "LONG" else -1

    gross = (
        (exit_price - entry)
        * quantity
        * sign
    )

    fees = (
        entry + exit_price
    ) * quantity * COMMISSION

    return gross - fees


def approve_trade(
    setup,
    equity,
    overall_floor=OVERALL_FLOOR,
    daily_threshold=DAILY_THRESHOLD,
    open_position=False,
    trading_locked=False,
    signal_id=None,
    last_signal_id=None
):
    if trading_locked:
        return reject("Trading is locked")

    if open_position:
        return reject("Position already open")

    if not signal_id:
        return reject("Missing signal ID")

    if signal_id == last_signal_id:
        return reject("Duplicate signal")

    if not setup:
        return reject("No qualifying setup")

    try:
        equity = float(equity)
        overall_floor = float(overall_floor)
        daily_threshold = float(daily_threshold)

        entry = float(setup["entry"])
        stop = float(setup["stop"])
        tp1 = float(setup["tp1"])
        tp2 = float(setup["tp2"])

        direction = setup["direction"]

    except (KeyError, ValueError, TypeError):
        return reject("Invalid setup data")

    values = [
        equity, overall_floor,
        daily_threshold, entry,
        stop, tp1, tp2
    ]

    if not all(
        math.isfinite(v) and v > 0
        for v in values
    ):
        return reject("Invalid numeric values")

    if equity <= overall_floor:
        return reject("Overall drawdown breached")

    if equity <= daily_threshold:
        return reject("Daily drawdown breached")

    if direction not in ("LONG", "SHORT"):
        return reject("Invalid direction")

    if direction == "LONG":
        if not stop < entry < tp1 < tp2:
            return reject("Invalid long structure")

        entry_side = "BUY"
        exit_side = "SELL"

    else:
        if not tp2 < tp1 < entry < stop:
            return reject("Invalid short structure")

        entry_side = "SELL"
        exit_side = "BUY"

    risk_budget = calculate_risk(
        equity,
        overall_floor,
        daily_threshold
    )

    if risk_budget <= 0:
        return reject("Insufficient risk headroom")

    entry_fill = execution_price(
        entry, entry_side
    )

    stop_fill = execution_price(
        stop, exit_side
    )

    tp1_fill = execution_price(
        tp1, exit_side
    )

    tp2_fill = execution_price(
        tp2, exit_side
    )

    loss_per_eth = -trade_pnl(
        direction,
        entry_fill,
        stop_fill,
        1.0
    )

    if loss_per_eth <= 0:
        return reject("Invalid stop risk")

    risk_quantity = (
        risk_budget / loss_per_eth
    )

    max_notional = equity * MAX_LEVERAGE

    leverage_quantity = (
        max_notional / entry_fill
    )

    quantity = min(
        risk_quantity,
        leverage_quantity
    )

    quantity = (
        math.floor(quantity / QUANTITY_STEP)
        * QUANTITY_STEP
    )

    quantity = round(quantity, 4)

    if quantity <= 0:
        return reject("Position size too small")

    planned_loss = (
        loss_per_eth * quantity
    )

    profit_tp1 = trade_pnl(
        direction,
        entry_fill,
        tp1_fill,
        quantity * 0.5
    )

    profit_tp2 = trade_pnl(
        direction,
        entry_fill,
        tp2_fill,
        quantity * 0.5
    )

    expected_reward = (
        profit_tp1 + profit_tp2
    )

    net_rr = expected_reward / planned_loss

    if net_rr < MIN_NET_RR:
        return reject(
            "Insufficient net reward to risk"
        )

    projected_equity = (
        equity - planned_loss
    )

    protected_floor = max(
        overall_floor,
        daily_threshold
    ) + SAFETY_BUFFER

    if projected_equity <= protected_floor:
        return reject(
            "Trade threatens drawdown floor"
        )

    notional = quantity * entry_fill
    leverage = notional / equity

    return {
        "approved": True,
        "verdict": direction,
        "reason": "Risk checks passed",
        "family": setup.get("family"),
        "signal_id": signal_id,
        "entry": entry,
        "estimated_fill": entry_fill,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "quantity": quantity,
        "notional": round(notional, 2),
        "leverage": round(leverage, 4),
        "risk_budget": round(risk_budget, 2),
        "planned_loss": round(planned_loss, 2),
        "potential_profit": round(
            expected_reward, 2
        ),
        "net_reward_risk": round(net_rr, 2),
        "projected_stop_equity": round(
            projected_equity, 2
        ),
        "real_execution": False,
        "mode": "PAPER"
    }
