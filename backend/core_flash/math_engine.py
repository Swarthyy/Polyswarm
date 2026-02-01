"""
PolySwarm 2.0 - Math Engine
Fair Value Calculator and Arbitrage Signal Detection

Strategy A: Latency-Lag Arbitrage (Fair Value vs Market Price)
Strategy B: Negative Risk Detection (YES + NO < $1.00)
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from datetime import datetime


class SignalType(Enum):
    """Types of arbitrage opportunities"""
    LAT_LAG = "Lat-Lag"      # Latency arbitrage - market mispriced vs fair value
    NEG_RISK = "Neg-Risk"    # Negative risk - guaranteed profit from order book


class SignalDirection(Enum):
    """Trade direction"""
    BUY_YES = "BUY_YES"
    BUY_NO = "BUY_NO"
    BUY_BOTH = "BUY_BOTH"  # For negative risk


@dataclass
class TradeSignal:
    """Represents a detected arbitrage opportunity"""
    id: str
    timestamp: float
    signal_type: SignalType
    direction: SignalDirection
    market: str

    # Prices
    binance_price: float
    fair_value: float
    market_price: float  # Current Polymarket price

    # Opportunity metrics
    edge_percent: float  # Expected edge in %
    ev_dollars: float    # Expected value in $ per $100 bet
    confidence: float    # 0-1 confidence score

    # For negative risk
    yes_ask: Optional[float] = None
    no_ask: Optional[float] = None
    cost_basis: Optional[float] = None

    # Execution status
    status: str = "PENDING"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp / 1000).strftime("%H:%M:%S"),
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "market": self.market,
            "binance_price": self.binance_price,
            "fair_value": round(self.fair_value, 4),
            "market_price": round(self.market_price, 4),
            "edge_percent": round(self.edge_percent, 2),
            "ev_dollars": round(self.ev_dollars, 2),
            "confidence": round(self.confidence, 2),
            "yes_ask": self.yes_ask,
            "no_ask": self.no_ask,
            "cost_basis": round(self.cost_basis, 4) if self.cost_basis else None,
            "status": self.status
        }


@dataclass
class MarketConfig:
    """Configuration for a prediction market"""
    market_id: str
    name: str
    strike_price: float      # e.g., 100000 for "BTC > $100k"
    expiry_timestamp: float  # Unix timestamp
    volatility_factor: float = 2000  # Tunable parameter for sigmoid steepness


class FairValueCalculator:
    """
    The Math Brain of Core A

    Calculates fair value of binary options and detects arbitrage opportunities.
    """

    # Thresholds
    MIN_EDGE_PERCENT = 2.0      # Minimum edge to signal (2%)
    NEG_RISK_THRESHOLD = 0.99   # YES + NO must be < this for neg risk
    MIN_CONFIDENCE = 0.6        # Minimum confidence to signal

    def __init__(self):
        self.signal_counter = 0
        self.active_markets: dict[str, MarketConfig] = {}
        self.signal_history: List[TradeSignal] = []

        # Initialize default BTC market
        self._init_default_markets()

    def _init_default_markets(self):
        """Initialize default prediction markets to track"""
        # BTC $100k market (example)
        self.add_market(MarketConfig(
            market_id="btc-100k-2024",
            name="BTC-100K",
            strike_price=100000,
            expiry_timestamp=time.time() + 86400 * 30,  # 30 days from now
            volatility_factor=2000
        ))

        # BTC $95k market
        self.add_market(MarketConfig(
            market_id="btc-95k-2024",
            name="BTC-95K",
            strike_price=95000,
            expiry_timestamp=time.time() + 86400 * 30,
            volatility_factor=1500
        ))

        # BTC $105k market
        self.add_market(MarketConfig(
            market_id="btc-105k-2024",
            name="BTC-105K",
            strike_price=105000,
            expiry_timestamp=time.time() + 86400 * 30,
            volatility_factor=2500
        ))

    def add_market(self, config: MarketConfig):
        """Register a market to track"""
        self.active_markets[config.market_id] = config

    @staticmethod
    def sigmoid(x: float) -> float:
        """Sigmoid function for probability mapping"""
        return 1 / (1 + math.exp(-x))

    def calculate_fair_value(
        self,
        binance_price: float,
        strike_price: float,
        volatility_factor: float,
        time_to_expiry: Optional[float] = None
    ) -> float:
        """
        Calculate fair value of a binary YES share.

        Uses simplified linear probability model:
        Distance = (Binance - Strike) / Volatility
        FairValue = Sigmoid(Distance)

        Args:
            binance_price: Current BTC spot price from Binance
            strike_price: The binary strike (e.g., $100,000)
            volatility_factor: Controls sigmoid steepness (higher = flatter curve)
            time_to_expiry: Optional time adjustment (not used in MVP)

        Returns:
            Fair value between 0.01 and 0.99
        """
        # Calculate distance from strike normalized by volatility
        distance = (binance_price - strike_price) / volatility_factor

        # Apply sigmoid for probability
        raw_probability = self.sigmoid(distance)

        # Clamp between 0.01 and 0.99 (never 0 or 1)
        fair_value = max(0.01, min(0.99, raw_probability))

        return fair_value

    def detect_lat_lag_opportunity(
        self,
        binance_price: float,
        market_price: float,  # Current YES price on Polymarket
        market_config: MarketConfig
    ) -> Optional[TradeSignal]:
        """
        Strategy A: Latency-Lag Arbitrage

        Detects when Polymarket price diverges from calculated fair value.

        Args:
            binance_price: Real-time BTC price from Binance
            market_price: Current YES share price on Polymarket
            market_config: Market configuration

        Returns:
            TradeSignal if opportunity detected, None otherwise
        """
        # Calculate fair value
        fair_value = self.calculate_fair_value(
            binance_price=binance_price,
            strike_price=market_config.strike_price,
            volatility_factor=market_config.volatility_factor
        )

        # Calculate edge
        edge = fair_value - market_price
        edge_percent = (edge / market_price) * 100 if market_price > 0 else 0

        # Determine direction and check threshold
        if edge_percent > self.MIN_EDGE_PERCENT:
            # Underpriced YES - BUY YES
            direction = SignalDirection.BUY_YES
            confidence = min(1.0, edge_percent / 10)  # Scale confidence
        elif edge_percent < -self.MIN_EDGE_PERCENT:
            # Overpriced YES - BUY NO (equivalent to selling YES)
            direction = SignalDirection.BUY_NO
            edge_percent = abs(edge_percent)
            confidence = min(1.0, edge_percent / 10)
        else:
            return None  # No significant edge

        if confidence < self.MIN_CONFIDENCE:
            return None

        # Calculate EV per $100 bet
        ev_dollars = edge_percent  # Simplified: edge% ~= EV%

        self.signal_counter += 1
        signal = TradeSignal(
            id=f"LAT-{self.signal_counter:04d}",
            timestamp=time.time() * 1000,
            signal_type=SignalType.LAT_LAG,
            direction=direction,
            market=market_config.name,
            binance_price=binance_price,
            fair_value=fair_value,
            market_price=market_price,
            edge_percent=edge_percent,
            ev_dollars=ev_dollars,
            confidence=confidence,
            status="PENDING"
        )

        self.signal_history.append(signal)
        return signal

    def detect_negative_risk(
        self,
        yes_ask: float,
        no_ask: float,
        market_name: str = "UNKNOWN"
    ) -> Optional[TradeSignal]:
        """
        Strategy B: Negative Risk Detection

        Detects when YES_ask + NO_ask < $1.00 (guaranteed profit).

        Args:
            yes_ask: Best ask price for YES shares
            no_ask: Best ask price for NO shares
            market_name: Name of the market

        Returns:
            TradeSignal if guaranteed profit detected, None otherwise
        """
        cost_basis = yes_ask + no_ask

        if cost_basis >= self.NEG_RISK_THRESHOLD:
            return None  # No arbitrage

        # Calculate guaranteed profit
        profit_percent = ((1.0 - cost_basis) / cost_basis) * 100
        ev_dollars = profit_percent  # Per $100 invested

        self.signal_counter += 1
        signal = TradeSignal(
            id=f"NEG-{self.signal_counter:04d}",
            timestamp=time.time() * 1000,
            signal_type=SignalType.NEG_RISK,
            direction=SignalDirection.BUY_BOTH,
            market=market_name,
            binance_price=0,  # Not relevant for neg risk
            fair_value=1.0,   # Always worth $1 at expiry
            market_price=cost_basis,
            edge_percent=profit_percent,
            ev_dollars=ev_dollars,
            confidence=1.0,  # Guaranteed profit = 100% confidence
            yes_ask=yes_ask,
            no_ask=no_ask,
            cost_basis=cost_basis,
            status="PENDING"
        )

        self.signal_history.append(signal)
        return signal

    def scan_all_markets(
        self,
        binance_price: float,
        poly_implied: float,
        yes_ask: Optional[float] = None,
        no_ask: Optional[float] = None
    ) -> List[TradeSignal]:
        """
        Scan all registered markets for opportunities.

        Args:
            binance_price: Current BTC spot price
            poly_implied: Current Polymarket implied price (used as YES price proxy)
            yes_ask: Order book YES ask (if available)
            no_ask: Order book NO ask (if available)

        Returns:
            List of detected signals
        """
        signals = []

        # Strategy A: Check each market for lat-lag opportunities
        for market_id, config in self.active_markets.items():
            # Derive market price from poly_implied relative to strike
            # This is a simplification - in production we'd have actual market prices
            market_yes_price = self._estimate_market_price(poly_implied, config)

            signal = self.detect_lat_lag_opportunity(
                binance_price=binance_price,
                market_price=market_yes_price,
                market_config=config
            )
            if signal:
                signals.append(signal)

        # Strategy B: Check for negative risk if we have order book data
        if yes_ask is not None and no_ask is not None:
            signal = self.detect_negative_risk(
                yes_ask=yes_ask,
                no_ask=no_ask,
                market_name="BTC-BINARY"
            )
            if signal:
                signals.append(signal)

        return signals

    def _estimate_market_price(
        self,
        poly_implied: float,
        config: MarketConfig
    ) -> float:
        """
        Estimate YES share price based on Polymarket's implied BTC price.

        This is a simplification for the MVP. In production, we'd fetch
        actual order book prices for each market.
        """
        # Calculate how far poly_implied is from strike
        distance = (poly_implied - config.strike_price) / config.volatility_factor

        # Add some "lag" to simulate Polymarket being behind
        # This makes the market price slightly stale compared to fair value
        lagged_distance = distance * 0.85  # 15% lag factor

        return max(0.01, min(0.99, self.sigmoid(lagged_distance)))

    def get_recent_signals(self, limit: int = 10) -> List[dict]:
        """Get most recent signals as dictionaries"""
        recent = self.signal_history[-limit:]
        return [s.to_dict() for s in reversed(recent)]
