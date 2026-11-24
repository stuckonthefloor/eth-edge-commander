import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

VERSION = "ETH EDGE COMMANDER V2.1"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def telegram_request(method, payload, timeout=15):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram not configured", flush=True)
        return None

    url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/"
        + method
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout
        ) as response:
            result = json.loads(response.read())

        if result.get("ok"):
            return result

        print("Telegram request rejected", flush=True)

    except urllib.error.HTTPError as error:
        print(
            f"Telegram HTTP error: {error.code}",
            flush=True
        )

    except Exception as error:
        print(
            f"Telegram error: {type(error).__name__}",
            flush=True
        )

    return None


def send_alert(message):
    result = telegram_request(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": str(message)[:4000]
        }
    )

    return result is not None


def money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "Unavailable"


def signed_money(value):
    try:
        return f"${float(value):+,.2f}"
    except (TypeError, ValueError):
        return "Unavailable"


def metric(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def startup_alert(equity):
    return send_alert(
        f"{VERSION}\n"
        "🟢 AUTONOMOUS ENGINE ONLINE\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Mode: PAPER TRADING\n"
        "Instrument: ETH/USD\n"
        f"Equity: {money(equity)}\n"
        "Real execution: DISABLED"
    )


def trade_alert(approval):
    direction = approval.get("verdict", "UNKNOWN")

    symbol = "🟢" if direction == "LONG" else "🔴"

    return send_alert(
        f"{symbol} {VERSION}\n"
        f"{direction} — PAPER TRADE OPENED\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Instrument: ETH/USD\n"
        f"Strategy: {approval.get('family', 'Unknown')}\n\n"
        f"Entry: {money(approval.get('estimated_fill'))}\n"
        f"Stop loss: {money(approval.get('stop'))}\n"
        f"Take profit 1: {money(approval.get('tp1'))}\n"
        f"Take profit 2: {money(approval.get('tp2'))}\n\n"
        "POSITION DETAILS\n"
        f"Quantity: {approval.get('quantity')} ETH\n"
        f"Notional: {money(approval.get('notional'))}\n"
        f"Leverage: {approval.get('leverage')}x\n\n"
        "RISK MANAGEMENT\n"
        f"Planned risk: {money(approval.get('planned_loss'))}\n"
        f"Potential profit: {money(approval.get('potential_profit'))}\n"
        f"Net reward/risk: {metric(approval.get('net_reward_risk'))}R\n\n"
        "Risk governor: APPROVED\n"
        "Real execution: DISABLED\n\n"
        "Simulated execution only.\n"
        "Kraken Prop prices and fills may differ."
    )


def exit_alert(event, equity):
    reason = event.get("reason", "EXIT")

    titles = {
        "TP1": "🎯 TAKE PROFIT 1",
        "TP2": "🏆 TAKE PROFIT 2",
        "STOP_LOSS": "🛑 STOP LOSS",
        "EMERGENCY_EXIT": "🚨 EMERGENCY EXIT"
    }

    title = titles.get(reason, "📊 POSITION EXIT")

    return send_alert(
        f"{VERSION}\n"
        f"{title}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Reason: {reason}\n"
        f"Exit price: {money(event.get('price'))}\n"
        f"Quantity closed: {event.get('quantity')} ETH\n"
        f"Exit P&L: {signed_money(event.get('pnl'))}\n\n"
        f"Account equity: {money(equity)}\n\n"
        "Paper trading only."
    )


def lockout_alert(reason, equity):
    return send_alert(
        f"{VERSION}\n"
        "🚨 MODULE X RISK LOCKOUT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "New paper trades disabled.\n\n"
        f"Reason: {reason}\n"
        f"Equity: {money(equity)}\n\n"
        "Capital protection activated."
    )


def performance_text(stats):
    return (
        f"{VERSION}\n"
        "📊 PERFORMANCE REPORT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Equity: {money(stats.get('equity'))}\n"
        f"Balance: {money(stats.get('balance'))}\n"
        f"Realized P&L: {signed_money(stats.get('realized_pnl'))}\n"
        f"Open P&L: {signed_money(stats.get('unrealized_pnl'))}\n\n"
        f"Closed trades: {stats.get('closed_trades', 'N/A')}\n"
        f"Wins: {stats.get('winning_trades', 'N/A')}\n"
        f"Losses: {stats.get('losing_trades', 'N/A')}\n"
        f"Win rate: {stats.get('win_rate', 'N/A')}\n"
        f"Profit factor: {metric(stats.get('profit_factor'))}\n"
        f"Expectancy: {metric(stats.get('expectancy'))}\n"
        f"Max drawdown: {money(stats.get('max_drawdown'))}\n"
        f"Peak equity: {money(stats.get('peak_equity'))}\n\n"
        "Paper trading performance only."
    )


def performance_alert(stats):
    return send_alert(performance_text(stats))


def help_text():
    return (
        f"{VERSION}\n"
        "⚡ TELEGRAM COMMAND CENTER\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "/status - Market intelligence\n"
        "/balance - Account balance\n"
        "/positions - Open paper positions\n"
        "/report - Performance statistics\n"
        "/health - Engine health\n"
        "/risk - Risk governor status\n"
        "/help - Available commands\n\n"
        "All commands are read-only.\n"
        "Real execution is disabled."
    )


def data_is_fresh(state):
    try:
        updated = datetime.fromisoformat(
            state["updated"].replace("Z", "+00:00")
        )

        age = (
            datetime.now(timezone.utc) - updated
        ).total_seconds()

        return (
            state.get("status") == "ONLINE"
            and not state.get("error")
            and 0 <= age <= 30
        )

    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def command_response(command, state):
    account = state.get("account") or {}
    analysis = state.get("analysis") or {}

    if command in ("/help", "/start"):
        return help_text()

    fresh = data_is_fresh(state)

    warning = (
        "" if fresh else
        "\n\n⚠️ Engine data may be stale or unavailable."
    )

    if command == "/status":
        return (
            f"{VERSION}\n"
            "📡 MARKET INTELLIGENCE\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"ETH: {money(state.get('price'))}\n"
            f"Source: {state.get('market_source', 'Unknown')}\n"
            f"Trend: {analysis.get('trend', 'Unknown')}\n"
            f"Structure: {analysis.get('structure', 'Unknown')}\n\n"
            f"Verdict: {state.get('verdict') if fresh else 'STALE'}\n"
            f"Reason: {state.get('reason', 'Unavailable')}\n\n"
            f"Completed scans: {state.get('scans', 0)}\n"
            "Mode: PAPER TRADING"
            + warning
        )

    if command == "/health":
        return (
            f"{VERSION}\n"
            "🖥 SYSTEM HEALTH\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"Status: {state.get('status', 'Unknown')}\n"
            f"Data fresh: {'YES' if fresh else 'NO'}\n"
            f"Scans: {state.get('scans', 0)}\n"
            f"Last update: {state.get('updated')}\n"
            f"Engine error: {'YES' if state.get('error') else 'None reported'}\n"
            f"Trading locked: {account.get('trading_locked', 'Unknown')}\n\n"
            "Real execution: DISABLED"
            + warning
        )

    if command not in (
        "/balance", "/positions", "/report", "/risk"
    ):
        return help_text()

    if not account:
        return (
            "Account data is not available yet.\n"
            "Try /health and check again shortly."
        )

    if command == "/balance":
        return (
            f"{VERSION}\n"
            "💰 PAPER ACCOUNT\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"Equity: {money(account.get('equity'))}\n"
            f"Balance: {money(account.get('balance'))}\n"
            f"Realized P&L: {signed_money(account.get('realized_pnl'))}\n"
            f"Open P&L: {signed_money(account.get('unrealized_pnl'))}\n\n"
            "Simulated funds only."
            + warning
        )

    if command == "/positions":
        if "open_position" in account:
            position = account["open_position"]
        elif "position" in account:
            position = account["position"]
        else:
            return (
                "Position data unavailable."
                + warning
            )

        if not position:
            return "No open paper positions." + warning

        if not isinstance(position, dict):
            return (
                "Open position data:\n"
                + str(position)
                + warning
            )

        return (
            f"{VERSION}\n"
            "📍 OPEN PAPER POSITION\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"Current ETH: {money(state.get('price'))}\n\n"
            + json.dumps(
                position,
                indent=2,
                default=str
            )[:3000]
            + warning
        )

    if command == "/report":
        return performance_text(account) + warning

    if command == "/risk":
        equity = account.get("equity")
        overall = state.get("overall_floor")
        daily = state.get("daily_threshold")

        buffer = None

        try:
            buffer = float(equity) - max(
                float(overall),
                float(daily)
            )
        except (TypeError, ValueError):
            pass

        locked = account.get("trading_locked")

        lock_status = (
            "LOCKED" if locked is True else
            "UNLOCKED" if locked is False else
            "UNKNOWN"
        )

        return (
            f"{VERSION}\n"
            "🛡 MODULE X RISK GOVERNOR\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"Equity: {money(equity)}\n"
            f"Overall floor: {money(overall)}\n"
            f"Daily threshold: {money(daily)}\n"
            f"Remaining buffer: {money(buffer)}\n\n"
            f"Trading status: {lock_status}\n"
            f"Lock reason: {account.get('lock_reason') or 'Not reported'}\n"
            f"Max drawdown: {money(account.get('max_drawdown'))}\n\n"
            "Daily threshold is currently fixed.\n"
            "Real execution: DISABLED"
            + warning
        )

    return help_text()


def register_commands():
    commands = [
        ("status", "Market intelligence"),
        ("balance", "Paper account balance"),
        ("positions", "Open paper positions"),
        ("report", "Performance statistics"),
        ("health", "Engine health"),
        ("risk", "Risk governor"),
        ("help", "Available commands")
    ]

    return telegram_request(
        "setMyCommands",
        {
            "commands": [
                {
                    "command": command,
                    "description": description
                }
                for command, description in commands
            ]
        }
    )


def command_listener(get_state):
    if not BOT_TOKEN or not CHAT_ID:
        print(
            "Telegram credentials missing",
            flush=True
        )
        return

    register_commands()

    offset = 0

    print(
        "Telegram command center started",
        flush=True
    )

    while True:
        try:
            result = telegram_request(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message"]
                },
                timeout=35
            )

            if result is None:
                time.sleep(10)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat = message.get("chat", {})

                if str(chat.get("id")) != str(CHAT_ID):
                    continue

                if chat.get("type") != "private":
                    continue

                message_time = message.get("date", 0)

                if time.time() - message_time > 120:
                    continue

                text = message.get("text", "").strip()

                if not text.startswith("/"):
                    continue

                command = (
                    text.split()[0]
                    .split("@")[0]
                    .lower()
                )

                state = get_state()

                response = command_response(
                    command,
                    state
                )

                send_alert(response)

        except Exception as error:
            print(
                "Telegram listener error: "
                + type(error).__name__,
                flush=True
            )

            time.sleep(10)
