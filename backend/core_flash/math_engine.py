"""
PolySwarm 2.0 - Math Engine
The $912k Wallet Strategy (0x8d5d)

Three Logic Gates:
1. Impulse Filter - Detect "God Candles" (>0.5% moves)
2. Trap Detector - Reject wide spreads (>5 cents)
3. Fee Crusher - Require minimum edge (>3.5% to beat fees)

We do NOT trade every micro-movement. We only want God Candles.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Deque
from collections import deque
from datetime import datetime


class SignalType(Enum):
    """Types of trade signals"""
    GOD_CANDLE = "GOD_CANDLE"      # Impulse detected - big move
    VALID_TRADE = "VALID_TRADE"    # All gates passed


class RejectReason(Enum):
    """Reasons for rejecting a trade"""
    NO_IMPULSE = "NO_IMPULSE"      # No significant price movement
    TRAP_DETECTED = "TRAP"         # Wide spread - liquidity trap
    LOW_MARGIN = "LOW_MARGIN"      # Edge doesn't beat fees
    WAITING = "WAITING"            # Accumulating data


class GateStatus(Enum):
    """Status of each logic gate"""
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


@dataclass
class PriceTick:
    """A single price observation"""
    price: float
    timestamp: float  # Unix ms


@dataclass
class GateResult:
    """Result from a logic gate check"""
    gate_name: str
    status: GateStatus
    value: float
    threshold: float
    message: str


@dataclass
class ScanResult:
    """Complete scan result from all three gates"""
    timestamp: float

    # Gate results
    impulse_gate: GateResult
    trap_gate: GateResult
    fee_gate: GateResult

    # Overall
    all_passed: bool
    reject_reason: Optional[RejectReason]

    # Price data
    binance_price: float
    poly_price: float
    price_delta_percent: float
    spread: float
    edge_percent: float

    # Signal info (if passed)
    signal_type: Optional[SignalType] = None
    direction: Optional[str] = None  # BUY_YES or BUY_NO
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": f"SCAN-{int(self.timestamp)}",
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp / 1000).strftime("%H:%M:%S.%f")[:-3],

            # Gates
            "impulse": {
                "status": self.impulse_gate.status.value,
                "value": round(self.impulse_gate.value * 100, 3),  # As percent
                "threshold": self.impulse_gate.threshold * 100,
                "message": self.impulse_gate.message
            },
            "trap": {
                "status": self.trap_gate.status.value,
                "value": round(self.trap_gate.value, 4),
                "threshold": self.trap_gate.threshold,
                "message": self.trap_gate.message
            },
            "fee": {
                "status": self.fee_gate.status.value,
                "value": round(self.fee_gate.value * 100, 2),  # As percent
                "threshold": self.fee_gate.threshold * 100,
                "message": self.fee_gate.message
            },

            # Overall
            "all_passed": self.all_passed,
            "reject_reason": self.reject_reason.value if self.reject_reason else None,
            "signal_type": self.signal_type.value if self.signal_type else None,
            "direction": self.direction,
            "confidence": round(self.confidence, 2),

            # Prices
            "binance_price": round(self.binance_price, 2),
            "poly_price": round(self.poly_price, 2),
            "price_delta_percent": round(self.price_delta_percent, 3),
            "spread": round(self.spread, 4),
            "edge_percent": round(self.edge_percent, 2)
        }


class OpportunityScanner:
    """
    The $912k Wallet Strategy Scanner

    Implements the three logic gates that filter noise and find real opportunities:
    1. Impulse Filter - Only trade on "God Candles" (>0.5% moves)
    2. Trap Detector - Avoid wide spreads (>5 cents)
    3. Fee Crusher - Ensure edge beats fees (>3.5%)
    """

    # === STRATEGY THRESHOLDS (The $912k Parameters) ===

    # Gate A: Impulse Filter
    IMPULSE_THRESHOLD = 0.005      # 0.5% move required
    IMPULSE_WINDOW_MS = 10000      # Look back 10 seconds
    PRICE_HISTORY_MS = 60000       # Keep 60 seconds of history

    # Gate B: Trap Detector
    SPREAD_THRESHOLD = 0.05        # Max 5 cent spread

    # Gate C: Fee Crusher
    MIN_EDGE_THRESHOLD = 0.035     # Need 3.5% edge to beat fees
    TAKER_FEE = 0.03               # 3% Polymarket taker fee
    SLIPPAGE_BUFFER = 0.005        # 0.5% slippage buffer

    def __init__(self):
        # Rolling price history (last 60 seconds)
        self.price_history: Deque[PriceTick] = deque(maxlen=1000)

        # Signal tracking
        self.signal_count = 0
        self.last_signal_time = 0
        self.signal_cooldown_ms = 5000  # 5 second cooldown between signals

        # Stats
        self.scans_total = 0
        self.impulses_detected = 0
        self.traps_detected = 0
        self.low_margin_count = 0
        self.valid_signals = 0

        print("[SCANNER] $912k Wallet Strategy initialized")
        print(f"[SCANNER] Impulse threshold: {self.IMPULSE_THRESHOLD*100}%")
        print(f"[SCANNER] Spread threshold: ${self.SPREAD_THRESHOLD}")
        print(f"[SCANNER] Min edge: {self.MIN_EDGE_THRESHOLD*100}%")

    def add_price(self, price: float, timestamp: float):
        """Add a new price tick to the rolling history"""
        self.price_history.append(PriceTick(price=price, timestamp=timestamp))
        self._cleanup_old_prices(timestamp)

    def _cleanup_old_prices(self, current_time: float):
        """Remove prices older than the history window"""
        cutoff = current_time - self.PRICE_HISTORY_MS
        while self.price_history and self.price_history[0].timestamp < cutoff:
            self.price_history.popleft()

    def get_price_n_seconds_ago(self, seconds: float, current_time: float) -> Optional[float]:
        """Get the price from N seconds ago"""
        target_time = current_time - (seconds * 1000)

        # Find closest price to target time
        closest_price = None
        min_diff = float('inf')

        for tick in self.price_history:
            diff = abs(tick.timestamp - target_time)
            if diff < min_diff:
                min_diff = diff
                closest_price = tick.price

        # Only return if we found something within 2 seconds
        if min_diff < 2000:
            return closest_price
        return None

    def check_impulse_gate(self, current_price: float, current_time: float) -> GateResult:
        """
        Gate A: The Impulse Filter

        Detects "God Candles" - significant price movements that indicate
        the world has changed and Polymarket is likely wrong.

        Trigger: (Current - Price_10s_Ago) / Price_10s_Ago > 0.5%
        """
        price_10s_ago = self.get_price_n_seconds_ago(10, current_time)

        if price_10s_ago is None:
            return GateResult(
                gate_name="IMPULSE",
                status=GateStatus.PENDING,
                value=0,
                threshold=self.IMPULSE_THRESHOLD,
                message="Accumulating price history..."
            )

        # Calculate impulse
        impulse = (current_price - price_10s_ago) / price_10s_ago
        impulse_abs = abs(impulse)

        if impulse_abs >= self.IMPULSE_THRESHOLD:
            self.impulses_detected += 1
            direction = "UP" if impulse > 0 else "DOWN"
            return GateResult(
                gate_name="IMPULSE",
                status=GateStatus.PASS,
                value=impulse,
                threshold=self.IMPULSE_THRESHOLD,
                message=f"GOD CANDLE {direction}! {impulse_abs*100:.2f}% in 10s"
            )
        else:
            return GateResult(
                gate_name="IMPULSE",
                status=GateStatus.FAIL,
                value=impulse,
                threshold=self.IMPULSE_THRESHOLD,
                message=f"No impulse ({impulse_abs*100:.3f}% < {self.IMPULSE_THRESHOLD*100}%)"
            )

    def check_trap_gate(self, best_bid: float, best_ask: float) -> GateResult:
        """
        Gate B: The Trap Detector

        Detects dangerous market conditions:
        - Wide spreads indicate market halt, low liquidity, or trap
        - We refuse to trade if spread > 5 cents
        """
        spread = best_ask - best_bid

        if spread > self.SPREAD_THRESHOLD:
            self.traps_detected += 1
            return GateResult(
                gate_name="TRAP",
                status=GateStatus.FAIL,
                value=spread,
                threshold=self.SPREAD_THRESHOLD,
                message=f"TRAP! Spread ${spread:.3f} > ${self.SPREAD_THRESHOLD}"
            )
        else:
            return GateResult(
                gate_name="TRAP",
                status=GateStatus.PASS,
                value=spread,
                threshold=self.SPREAD_THRESHOLD,
                message=f"Spread OK (${spread:.3f})"
            )

    def check_fee_gate(self, binance_price: float, poly_implied: float, strike: float = 100000) -> GateResult:
        """
        Gate C: The Fee Crusher

        Ensures the edge is large enough to beat:
        - 3% taker fee
        - ~0.5% slippage

        We need at least 3.5% edge to make the trade worthwhile.
        """
        # Calculate fair value delta as percentage
        fair_value_delta = abs(binance_price - poly_implied) / binance_price

        if fair_value_delta < self.MIN_EDGE_THRESHOLD:
            self.low_margin_count += 1
            return GateResult(
                gate_name="FEE",
                status=GateStatus.FAIL,
                value=fair_value_delta,
                threshold=self.MIN_EDGE_THRESHOLD,
                message=f"LOW MARGIN! {fair_value_delta*100:.2f}% < {self.MIN_EDGE_THRESHOLD*100}%"
            )
        else:
            net_edge = fair_value_delta - self.TAKER_FEE - self.SLIPPAGE_BUFFER
            return GateResult(
                gate_name="FEE",
                status=GateStatus.PASS,
                value=fair_value_delta,
                threshold=self.MIN_EDGE_THRESHOLD,
                message=f"Edge OK! {fair_value_delta*100:.2f}% (net ~{net_edge*100:.2f}%)"
            )

    def scan(
        self,
        binance_price: float,
        poly_implied: float,
        best_bid: float,
        best_ask: float,
        timestamp: float
    ) -> ScanResult:
        """
        Run the full three-gate scan.

        State Machine:
        1. Update prices
        2. Check IMPULSE (Is Binance moving fast?)
        3. Check TRAP (Is Poly broken?)
        4. Check FEE (Is it worth it?)
        5. Emit signal only if ALL pass
        """
        self.scans_total += 1

        # Add price to history
        self.add_price(binance_price, timestamp)

        # Run all three gates
        impulse_result = self.check_impulse_gate(binance_price, timestamp)
        trap_result = self.check_trap_gate(best_bid, best_ask)
        fee_result = self.check_fee_gate(binance_price, poly_implied)

        # Calculate metrics
        spread = best_ask - best_bid
        price_delta = (binance_price - poly_implied) / binance_price
        edge = abs(price_delta)

        # Determine overall result
        all_passed = (
            impulse_result.status == GateStatus.PASS and
            trap_result.status == GateStatus.PASS and
            fee_result.status == GateStatus.PASS
        )

        # Determine reject reason (first gate to fail)
        reject_reason = None
        if not all_passed:
            if impulse_result.status == GateStatus.PENDING:
                reject_reason = RejectReason.WAITING
            elif impulse_result.status == GateStatus.FAIL:
                reject_reason = RejectReason.NO_IMPULSE
            elif trap_result.status == GateStatus.FAIL:
                reject_reason = RejectReason.TRAP_DETECTED
            elif fee_result.status == GateStatus.FAIL:
                reject_reason = RejectReason.LOW_MARGIN

        # Build signal info if all passed
        signal_type = None
        direction = None
        confidence = 0.0

        if all_passed:
            self.valid_signals += 1
            signal_type = SignalType.GOD_CANDLE

            # Direction based on impulse
            if impulse_result.value > 0:
                direction = "BUY_YES"  # Price going up, bet YES
            else:
                direction = "BUY_NO"   # Price going down, bet NO

            # Confidence based on edge size
            confidence = min(1.0, edge / 0.10)  # Max confidence at 10% edge

        return ScanResult(
            timestamp=timestamp,
            impulse_gate=impulse_result,
            trap_gate=trap_result,
            fee_gate=fee_result,
            all_passed=all_passed,
            reject_reason=reject_reason,
            binance_price=binance_price,
            poly_price=poly_implied,
            price_delta_percent=price_delta * 100,
            spread=spread,
            edge_percent=edge * 100,
            signal_type=signal_type,
            direction=direction,
            confidence=confidence
        )

    def get_stats(self) -> dict:
        """Get scanner statistics"""
        return {
            "scans_total": self.scans_total,
            "impulses_detected": self.impulses_detected,
            "traps_detected": self.traps_detected,
            "low_margin_count": self.low_margin_count,
            "valid_signals": self.valid_signals,
            "price_history_size": len(self.price_history)
        }


# === Legacy FairValueCalculator for backwards compatibility ===

class SignalDirection(Enum):
    """Trade direction"""
    BUY_YES = "BUY_YES"
    BUY_NO = "BUY_NO"
    BUY_BOTH = "BUY_BOTH"


@dataclass
class TradeSignal:
    """Legacy trade signal for backwards compatibility"""
    id: str
    timestamp: float
    signal_type: str
    direction: str
    market: str
    binance_price: float
    fair_value: float
    market_price: float
    edge_percent: float
    ev_dollars: float
    confidence: float
    status: str = "PENDING"

    # Gate info
    impulse_status: str = "N/A"
    trap_status: str = "N/A"
    fee_status: str = "N/A"
    reject_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp / 1000).strftime("%H:%M:%S"),
            "signal_type": self.signal_type,
            "direction": self.direction,
            "market": self.market,
            "binance_price": self.binance_price,
            "fair_value": round(self.fair_value, 4),
            "market_price": round(self.market_price, 4),
            "edge_percent": round(self.edge_percent, 2),
            "ev_dollars": round(self.ev_dollars, 2),
            "confidence": round(self.confidence, 2),
            "status": self.status,
            "impulse_status": self.impulse_status,
            "trap_status": self.trap_status,
            "fee_status": self.fee_status,
            "reject_reason": self.reject_reason
        }


class FairValueCalculator:
    """
    Legacy calculator - now wraps OpportunityScanner
    """

    def __init__(self):
        self.scanner = OpportunityScanner()
        self.signal_counter = 0

    def scan_opportunity(
        self,
        binance_price: float,
        poly_implied: float,
        best_bid: float,
        best_ask: float,
        timestamp: float,
        market_name: str = "BTC-100K"
    ) -> Optional[TradeSignal]:
        """
        Scan for opportunity using the $912k strategy.
        Returns a TradeSignal if all gates pass, None otherwise.
        """
        result = self.scanner.scan(
            binance_price=binance_price,
            poly_implied=poly_implied,
            best_bid=best_bid,
            best_ask=best_ask,
            timestamp=timestamp
        )

        self.signal_counter += 1

        # Create signal with gate statuses
        signal = TradeSignal(
            id=f"SIG-{self.signal_counter:04d}",
            timestamp=timestamp,
            signal_type=result.signal_type.value if result.signal_type else "SCAN",
            direction=result.direction or "NONE",
            market=market_name,
            binance_price=binance_price,
            fair_value=binance_price,  # Simplified
            market_price=poly_implied,
            edge_percent=result.edge_percent,
            ev_dollars=result.edge_percent,  # Simplified: edge% ~= EV
            confidence=result.confidence,
            status="VALID" if result.all_passed else "REJECTED",
            impulse_status=result.impulse_gate.status.value,
            trap_status=result.trap_gate.status.value,
            fee_status=result.fee_gate.status.value,
            reject_reason=result.reject_reason.value if result.reject_reason else None
        )

        return signal

    def get_scanner_stats(self) -> dict:
        return self.scanner.get_stats()
