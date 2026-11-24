import os
import json
import urllib.request
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN", ""
)

CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID", ""
)


def send_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        print(
            "Telegram not configured",
            flush=True
        )
        return False

    url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/sendMessage"
    )

    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=10
        ) as response:
            result = json.loads(
                response.read()
            )

        return bool(result.get("ok"))

    except Exception:
        print(
            "Telegram delivery failed",
            flush=True
        )
        return False


def startup_alert(equity):
    return send_alert(
        "ETH EDGE COMMANDER V2\n"
        "AUTONOMOUS ENGINE ONLINE\n\n"
        "Mode: PAPER TRADING\n"
        f"Equity: ${equity:,.2f}\n"
        "Real execution: DISABLED"
    )


def trade_alert(approval):
    direction = approval["verdict"]

    symbol = (
        "🟢" if direction == "LONG"
        else "🔴"
    )

    return send_alert(
        f"{symbol} {direction} — PAPER TRADE\n\n"
        "ETH/USD\n"
        f"Strategy: {approval['family']}\n\n"
        f"Entry: ${approval['estimated_fill']:,.2f}\n"
        f"Stop: ${approval['stop']:,.2f}\n"
        f"TP1: ${approval['tp1']:,.2f}\n"
        f"TP2: ${approval['tp2']:,.2f}\n\n"
        f"Quantity: {approval['quantity']} ETH\n"
        f"Notional: ${approval['notional']:,.2f}\n"
        f"Leverage: {approval['leverage']}x\n"
        f"Risk: ${approval['planned_loss']:,.2f}\n"
        f"Potential profit: "
        f"${approval['potential_profit']:,.2f}\n"
        f"Net R:R: {approval['net_reward_risk']}\n\n"
        "Risk governor: APPROVED\n"
        "Simulated execution only."
    )


def exit_alert(event, equity):
    reason = event["reason"]
    pnl = event["pnl"]

    icons = {
        "TP1": "🎯",
        "TP2": "🏆",
        "STOP_LOSS": "🛑",
        "EMERGENCY_EXIT": "🚨"
    }

    symbol = icons.get(reason, "📊")

    return send_alert(
        f"{symbol} {reason}\n\n"
        f"Exit: ${event['price']:,.2f}\n"
        f"Quantity: {event['quantity']:.4f} ETH\n"
        f"Net P&L: ${pnl:+,.2f}\n"
        f"Account equity: ${equity:,.2f}\n\n"
        "Paper trading only."
    )


def lockout_alert(reason, equity):
    return send_alert(
        "🚨 MODULE X LOCKOUT\n\n"
        "New trades disabled.\n"
        f"Reason: {reason}\n"
        f"Equity: ${equity:,.2f}"
    )


def performance_alert(stats):
    return send_alert(
        "📊 ETH EDGE COMMANDER REPORT\n\n"
        f"Equity: ${stats['equity']:,.2f}\n"
        f"Realized P&L: "
        f"${stats['realized_pnl']:+,.2f}\n"
        f"Closed trades: {stats['closed_trades']}\n"
        f"Wins: {stats['winning_trades']}\n"
        f"Losses: {stats['losing_trades']}\n"
        f"Win rate: {stats['win_rate']}\n"
        f"Profit factor: {stats['profit_factor']}\n"
        f"Expectancy: {stats['expectancy']}\n"
        f"Max drawdown: "
        f"${stats['max_drawdown']:,.2f}\n\n"
        "Paper trading performance."
    )
