from datetime import datetime, timezone
from math import isfinite
from risk import execution_price, trade_pnl


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class PaperEngine:

    def __init__(self, starting_equity=5000.0):
        self.starting_equity = starting_equity
        self.balance = starting_equity
        self.position = None
        self.history = []
        self.last_signal_id = None
        self.used_signals = set()
        self.trading_locked = False
        self.lock_reason = None
        self.peak_equity = starting_equity
        self.max_drawdown = 0.0

    def open_trade(self, approval, price):
        if self.trading_locked:
            return False

        if self.position is not None:
            return False

        if not approval.get("approved"):
            return False

        signal_id = approval.get("signal_id")

        if not signal_id:
            return False

        if signal_id in self.used_signals:
            return False

        direction = approval["verdict"]

        if direction not in ("LONG", "SHORT"):
            return False

        price = float(price)

        if not isfinite(price) or price <= 0:
            return False

        reference = approval["entry"]

        # Require fresh risk approval at current price.
        if abs(price - reference) > 0.000001:
            return False

        side = "BUY" if direction == "LONG" else "SELL"
        fill = execution_price(price, side)

        quantity = float(approval["quantity"])

        if not isfinite(quantity) or quantity <= 0:
            return False

        self.position = {
            "signal_id": signal_id,
            "family": approval.get("family"),
            "direction": direction,
            "entry": fill,
            "stop": approval["stop"],
            "tp1": approval["tp1"],
            "tp2": approval["tp2"],
            "quantity": quantity,
            "remaining": quantity,
            "initial_risk": approval["planned_loss"],
            "tp1_hit": False,
            "realized_pnl": 0.0,
            "opened_at": timestamp(),
            "exits": []
        }

        self.last_signal_id = signal_id
        self.used_signals.add(signal_id)

        return True

    def close_quantity(self, price, quantity, reason):
        p = self.position

        if p is None:
            return None

        quantity = min(quantity, p["remaining"])

        if quantity <= 0:
            return None

        side = (
            "SELL"
            if p["direction"] == "LONG"
            else "BUY"
        )

        fill = execution_price(price, side)

        pnl = trade_pnl(
            p["direction"],
            p["entry"],
            fill,
            quantity
        )

        self.balance += pnl
        p["realized_pnl"] += pnl
        p["remaining"] -= quantity

        event = {
            "reason": reason,
            "price": fill,
            "quantity": quantity,
            "pnl": pnl,
            "time": timestamp()
        }

        p["exits"].append(event)

        if p["remaining"] <= 0.00000001:
            p["remaining"] = 0
            p["closed_at"] = timestamp()
            p["exit_reason"] = reason

            p["r_multiple"] = (
                p["realized_pnl"]
                / p["initial_risk"]
                if p["initial_risk"] > 0
                else 0
            )

            self.history.append(p)
            self.position = None

        return event

    def update_price(
        self,
        price,
        overall_floor,
        daily_threshold
    ):
        price = float(price)

        if not isfinite(price) or price <= 0:
            return []

        events = []

        floor = max(
            overall_floor,
            daily_threshold
        )

        if self.equity(price) <= floor:
            self.trading_locked = True
            self.lock_reason = "Drawdown threshold reached"

            if self.position:
                events.append(
                    self.close_quantity(
                        price,
                        self.position["remaining"],
                        "EMERGENCY_EXIT"
                    )
                )

            self.update_drawdown(price)
            return events

        p = self.position

        if p is None:
            self.update_drawdown(price)
            return events

        long = p["direction"] == "LONG"

        stop_hit = (
            price <= p["stop"]
            if long
            else price >= p["stop"]
        )

        if stop_hit:
            events.append(
                self.close_quantity(
                    price,
                    p["remaining"],
                    "STOP_LOSS"
                )
            )

        else:
            tp1_hit = (
                price >= p["tp1"]
                if long
                else price <= p["tp1"]
            )

            tp2_hit = (
                price >= p["tp2"]
                if long
                else price <= p["tp2"]
            )

            if tp1_hit and not p["tp1_hit"]:
                p["tp1_hit"] = True

                events.append(
                    self.close_quantity(
                        p["tp1"],
                        p["quantity"] * 0.5,
                        "TP1"
                    )
                )

            if tp2_hit and self.position:
                events.append(
                    self.close_quantity(
                        p["tp2"],
                        p["remaining"],
                        "TP2"
                    )
                )

        if self.equity(price) <= floor:
            self.trading_locked = True
            self.lock_reason = "Drawdown threshold reached"

            if self.position:
                events.append(
                    self.close_quantity(
                        price,
                        self.position["remaining"],
                        "EMERGENCY_EXIT"
                    )
                )

        self.update_drawdown(price)

        return events

    def unrealized_pnl(self, price):
        p = self.position

        if p is None:
            return 0.0

        side = (
            "SELL"
            if p["direction"] == "LONG"
            else "BUY"
        )

        fill = execution_price(price, side)

        return trade_pnl(
            p["direction"],
            p["entry"],
            fill,
            p["remaining"]
        )

    def equity(self, price):
        return (
            self.balance
            + self.unrealized_pnl(price)
        )

    def update_drawdown(self, price):
        equity = self.equity(price)

        self.peak_equity = max(
            self.peak_equity,
            equity
        )

        drawdown = self.peak_equity - equity

        self.max_drawdown = max(
            self.max_drawdown,
            drawdown
        )

    def statistics(self, price):
        trades = len(self.history)

        wins = [
            t for t in self.history
            if t["realized_pnl"] > 0
        ]

        losses = [
            t for t in self.history
            if t["realized_pnl"] < 0
        ]

        gross_profit = sum(
            t["realized_pnl"] for t in wins
        )

        gross_loss = abs(sum(
            t["realized_pnl"] for t in losses
        ))

        net = self.balance - self.starting_equity

        closed_net = sum(
            t["realized_pnl"]
            for t in self.history
        )

        return {
            "mode": "PAPER",
            "real_execution": False,
            "balance": round(self.balance, 2),
            "equity": round(self.equity(price), 2),
            "realized_pnl": round(net, 2),
            "unrealized_pnl": round(
                self.unrealized_pnl(price), 2
            ),
            "closed_trades": trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(
                len(wins) / trades * 100, 2
            ) if trades else None,
            "profit_factor": round(
                gross_profit / gross_loss, 2
            ) if gross_loss else None,
            "expectancy": round(
                closed_net / trades, 2
            ) if trades else None,
            "average_r": round(
                sum(
                    t["r_multiple"]
                    for t in self.history
                ) / trades, 3
            ) if trades else None,
            "max_drawdown": round(
                self.max_drawdown, 2
            ),
            "peak_equity": round(
                self.peak_equity, 2
            ),
            "trading_locked": self.trading_locked,
            "lock_reason": self.lock_reason,
            "open_position": self.position
        }
