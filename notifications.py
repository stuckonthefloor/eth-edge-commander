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


def command_response(command, state):
    account = state.get("account") or {}
    equity = account.get("equity", 5000)
    price = state.get("price") or 0
    analysis = state.get("analysis") or {}

    if command == "/status":
        return (
            "ETH EDGE COMMANDER V2.1\n\n"
            f"ETH: ${price:,.2f}\n"
            f"Trend: {analysis.get('trend', 'WAIT')}\n"
            f"Structure: {analysis.get('structure', 'WAIT')}\n"
            f"Verdict: {state.get('verdict')}\n"
            f"Reason: {state.get('reason')}\n\n"
            "Mode: PAPER TRADING"
        )

    if command == "/balance":
        return (
            "ACCOUNT BALANCE\n\n"
            f"Equity: ${equity:,.2f}\n"
            f"Balance: ${account.get('balance', 5000):,.2f}\n"
            f"Realized P&L: ${account.get('realized_pnl', 0):+,.2f}\n"
            f"Open P&L: ${account.get('unrealized_pnl', 0):+,.2f}"
        )

    if command == "/positions":
        position = account.get("open_position")

        if not position:
            return "No open paper positions."

        return (
            "OPEN PAPER POSITION\n\n"
            + json.dumps(position, indent=2)[:3500]
        )

    if command == "/report":
        return (
            "PERFORMANCE REPORT\n\n"
            f"Equity: ${equity:,.2f}\n"
            f"Closed trades: {account.get('closed_trades', 0)}\n"
            f"Wins: {account.get('winning_trades', 0)}\n"
            f"Losses: {account.get('losing_trades', 0)}\n"
            f"Win rate: {account.get('win_rate')}\n"
            f"Profit factor: {account.get('profit_factor')}\n"
            f"Expectancy: {account.get('expectancy')}\n"
            f"Max drawdown: ${account.get('max_drawdown', 0):,.2f}\n\n"
            "Paper trading only."
        )

    if command == "/health":
        return (
            "SYSTEM HEALTH\n\n"
            f"Status: {state.get('status')}\n"
            f"Scans: {state.get('scans', 0)}\n"
            f"Updated: {state.get('updated')}\n"
            f"Error: {state.get('error')}\n"
            f"Trading locked: {account.get('trading_locked')}\n"
            "Real execution: DISABLED"
        )

    return (
        "ETH EDGE COMMANDER COMMANDS\n\n"
        "/status - Market analysis\n"
        "/balance - Account balance\n"
        "/positions - Open positions\n"
        "/report - Performance report\n"
        "/health - System health\n"
        "/help - Command list"
    )


def command_listener(get_state):
    import time

    if not BOT_TOKEN or not CHAT_ID:
        return

    offset = 0

    while True:
        try:
            url = (
                "https://api.telegram.org/bot"
                + BOT_TOKEN
                + "/getUpdates"
            )

            payload = json.dumps({
                "offset": offset,
                "timeout": 25,
                "allowed_updates": ["message"]
            }).encode("utf-8")

            request = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            with urllib.request.urlopen(
                request, timeout=35
            ) as response:
                result = json.loads(response.read())

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat = message.get("chat", {})

                if str(chat.get("id")) != str(CHAT_ID):
                    continue

                if chat.get("type") != "private":
                    continue

                text = message.get("text", "").strip()

                if not text.startswith("/"):
                    continue

                command = text.split()[0].split("@")[0].lower()

                state = get_state()

                send_alert(
                    command_response(command, state)
                )

        except Exception:
            print(
                "Telegram command listener error",
                flush=True
            )
            time.sleep(10)
