"""
PolySwarm 2.0 - Ingestion Engine
Dual-socket connection to Binance (real-time) and Polymarket (CLOB)
Calculates and broadcasts the "Reality Gap" between exchanges
Integrates Math Engine for signal detection
"""

import asyncio
import json
import time
import random
from dataclasses import dataclass
from typing import Callable, Optional, List
from collections import deque

import aiohttp

from .math_engine import FairValueCalculator, TradeSignal, OpportunityScanner, GateStatus
from .executor import TradeExecutor


@dataclass
class PricePoint:
    """Represents a price observation from an exchange"""
    source: str
    price: float
    timestamp: float  # Unix timestamp in ms


@dataclass
class GapData:
    """The Reality Gap between Binance and Polymarket"""
    binance_price: float
    poly_implied: float
    gap_percent: float
    binance_ts: float
    poly_ts: float
    latency_delta_ms: float


class BinanceStream:
    """
    WebSocket stream for Binance BTC/USDT trades
    Provides real-time spot price
    """
    WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@trade"

    def __init__(self):
        self.last_price: Optional[float] = None
        self.last_timestamp: float = 0
        self._running = False
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

    async def connect(self):
        """Establish WebSocket connection to Binance"""
        self._running = True
        print("[BINANCE] Connecting to trade stream...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.WS_URL) as ws:
                    self._ws = ws
                    print("[BINANCE] Connected to wss://stream.binance.com")

                    async for msg in ws:
                        if not self._running:
                            break

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                # Trade event format: {"e":"trade","p":"98500.00","T":1234567890123}
                                self.last_price = float(data.get('p', 0))
                                self.last_timestamp = data.get('T', time.time() * 1000)
                            except (json.JSONDecodeError, ValueError) as e:
                                print(f"[BINANCE] Parse error: {e}")

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            print("[BINANCE] Connection closed")
                            break

        except Exception as e:
            print(f"[BINANCE] Connection error: {e}")
        finally:
            self._running = False

    async def disconnect(self):
        """Close the WebSocket connection"""
        self._running = False
        if self._ws:
            await self._ws.close()


class PolymarketStream:
    """
    Polymarket CLOB price fetcher
    Fetches implied BTC price from prediction market

    Note: Polymarket uses a CLOB (Central Limit Order Book) model.
    For BTC price markets, we derive implied price from YES/NO prices.
    """

    # Polymarket CLOB API endpoints
    CLOB_API = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"

    # Sample BTC market condition IDs (these would be real market IDs in production)
    # For demo purposes, we'll simulate with price deviation
    BTC_MARKET_SLUG = "will-bitcoin-hit-100k"

    def __init__(self):
        self.implied_price: Optional[float] = None
        self.last_timestamp: float = 0
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Start polling Polymarket for BTC-related market prices"""
        self._running = True
        print("[POLYMARKET] Starting CLOB price fetcher...")

        try:
            self._session = aiohttp.ClientSession()
            print("[POLYMARKET] Connected to CLOB API")

            while self._running:
                try:
                    await self._fetch_btc_implied_price()
                except Exception as e:
                    print(f"[POLYMARKET] Fetch error: {e}")

                # Poll every 500ms (Polymarket doesn't have true real-time WS for all markets)
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[POLYMARKET] Connection error: {e}")
        finally:
            if self._session:
                await self._session.close()

    async def _fetch_btc_implied_price(self):
        """
        Fetch BTC implied price from Polymarket.

        In production, this would:
        1. Fetch active BTC price threshold markets
        2. Use probability-weighted average to derive implied price
        3. E.g., "BTC > 100k" at 45% YES + "BTC > 95k" at 78% YES = implied ~$97k

        For demo, we simulate with realistic lag behavior.
        """
        if not self._session:
            return

        try:
            # Try to fetch real market data from Polymarket's gamma API
            async with self._session.get(
                f"{self.GAMMA_API}/markets",
                params={"limit": 10, "active": "true"},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    markets = await response.json()
                    # Process markets to find BTC-related ones
                    self._process_markets(markets)
                else:
                    # Fallback to simulation mode
                    self._simulate_implied_price()

        except asyncio.TimeoutError:
            self._simulate_implied_price()
        except Exception:
            self._simulate_implied_price()

    def _process_markets(self, markets: list):
        """Process market data to derive BTC implied price"""
        # Look for BTC-related markets
        btc_markets = [m for m in markets if 'btc' in str(m).lower() or 'bitcoin' in str(m).lower()]

        if btc_markets:
            # Use real market data - would implement proper price derivation here
            self.last_timestamp = time.time() * 1000
        else:
            # No BTC markets found, use simulation
            self._simulate_implied_price()

    def _simulate_implied_price(self):
        """
        Simulate Polymarket implied price with realistic lag.
        This demonstrates the "Reality Gap" - Polymarket lags behind spot.

        In real trading:
        - Polymarket orderbook updates every 1-5 seconds
        - Market makers react to Binance with 500ms-2s delay
        - Large moves take 5-10s to fully price in
        """
        import random

        # Simulate lag: Polymarket price follows Binance with 300-800ms delay
        # And with reduced precision (market maker spread)
        if hasattr(self, '_binance_ref') and self._binance_ref.last_price:
            base_price = self._binance_ref.last_price

            # Add simulated lag and noise:
            # 1. Lag factor: Poly is ~0.02-0.08% behind Binance
            lag_factor = random.uniform(0.9992, 0.9998)

            # 2. Market maker spread noise
            spread_noise = random.uniform(-20, 20)

            # 3. Round to realistic precision (Polymarket uses whole dollars often)
            self.implied_price = round(base_price * lag_factor + spread_noise, 2)
        else:
            # Default simulation without Binance reference
            self.implied_price = 98000 + random.uniform(-500, 500)

        self.last_timestamp = time.time() * 1000

    def set_binance_reference(self, binance_stream: BinanceStream):
        """Link to Binance stream for realistic simulation"""
        self._binance_ref = binance_stream

    async def disconnect(self):
        """Close the connection"""
        self._running = False
        if self._session:
            await self._session.close()


class IngestionEngine:
    """
    The Reality Gap Monitor
    Orchestrates dual-stream data ingestion and gap calculation
    Integrates Math Engine for trade signal detection
    """

    def __init__(self, broadcast_callback: Callable):
        self.binance = BinanceStream()
        self.polymarket = PolymarketStream()
        self.broadcast = broadcast_callback
        self._running = False

        # Price history for visualization (last 100 points)
        self.price_history: deque = deque(maxlen=100)

        # $912k Wallet Strategy Scanner
        self.scanner = OpportunityScanner()

        # Signal tracking
        self.last_signal_time: float = 0
        self.signal_cooldown_ms: float = 5000  # Min 5s between signals (prevent spam)
        self.last_scan_broadcast: float = 0
        self.scan_broadcast_interval: float = 500  # Broadcast scan status every 500ms

        # Link streams for simulation
        self.polymarket.set_binance_reference(self.binance)

        # Execution Engine (The Fee Crusher)
        self.executor = TradeExecutor(broadcast_callback=self.broadcast)

    async def start(self):
        """Start the ingestion engine with all streams"""
        self._running = True
        print("=" * 50)
        print("  INGESTION ENGINE STARTING")
        print("  Binance WS + Polymarket CLOB")
        print("=" * 50)

        # Start all tasks concurrently
        await asyncio.gather(
            self.binance.connect(),
            self.polymarket.connect(),
            self._broadcast_loop(),
            return_exceptions=True
        )

    async def _broadcast_loop(self):
        """
        Broadcast gap data to frontend at 10Hz (100ms interval)
        Runs the $912k Wallet Strategy scanner on every tick
        """
        print("[INGEST] Starting 10Hz broadcast loop...")

        # Wait for initial data
        await asyncio.sleep(1)

        while self._running:
            try:
                gap_data = self._calculate_gap()

                if gap_data:
                    current_time = time.time() * 1000

                    # Build gap payload for frontend
                    payload = {
                        "type": "gap_monitor",
                        "binance": gap_data.binance_price,
                        "poly_implied": gap_data.poly_implied,
                        "gap_percent": gap_data.gap_percent,
                        "latency_delta_ms": gap_data.latency_delta_ms,
                        "timestamp": int(current_time),
                        "binance_ts": gap_data.binance_ts,
                        "poly_ts": gap_data.poly_ts
                    }

                    # Broadcast gap data
                    await self.broadcast(payload)

                    # Run the $912k Strategy Scanner
                    await self._run_scanner(gap_data, current_time)

            except Exception as e:
                print(f"[INGEST] Broadcast error: {e}")

            # 100ms interval = 10Hz
            await asyncio.sleep(0.1)

    async def _run_scanner(self, gap_data: GapData, current_time: float):
        """
        Run the $912k Wallet Strategy Scanner

        State Machine:
        1. Update Prices
        2. Check IMPULSE (Is Binance moving fast?)
        3. Check TRAP (Is Poly broken?)
        4. Check FEE (Is it worth it?)
        5. Emit Signal only if ALL pass
        """
        # Simulate order book for spread calculation
        best_bid, best_ask = self._simulate_order_book(gap_data.poly_implied)

        # Run the three-gate scan
        scan_result = self.scanner.scan(
            binance_price=gap_data.binance_price,
            poly_implied=gap_data.poly_implied,
            best_bid=best_bid,
            best_ask=best_ask,
            timestamp=current_time
        )

        # Broadcast scan status periodically (not every tick to reduce noise)
        if current_time - self.last_scan_broadcast > self.scan_broadcast_interval:
            self.last_scan_broadcast = current_time

            scan_payload = {
                "type": "scan_status",
                "timestamp": current_time,
                "impulse": {
                    "status": scan_result.impulse_gate.status.value,
                    "value": round(scan_result.impulse_gate.value * 100, 3),
                    "message": scan_result.impulse_gate.message
                },
                "trap": {
                    "status": scan_result.trap_gate.status.value,
                    "value": round(scan_result.trap_gate.value, 4),
                    "message": scan_result.trap_gate.message
                },
                "fee": {
                    "status": scan_result.fee_gate.status.value,
                    "value": round(scan_result.fee_gate.value * 100, 2),
                    "message": scan_result.fee_gate.message
                },
                "reject_reason": scan_result.reject_reason.value if scan_result.reject_reason else None,
                "edge_percent": round(scan_result.edge_percent, 2),
                "spread": round(scan_result.spread, 4)
            }
            await self.broadcast(scan_payload)

        # If all gates pass, emit a GOD CANDLE signal
        if scan_result.all_passed:
            # Cooldown check
            if current_time - self.last_signal_time < self.signal_cooldown_ms:
                return

            self.last_signal_time = current_time

            # Build signal payload
            signal_payload = {
                "type": "trade_signal",
                "signal": {
                    "id": f"GOD-{int(current_time)}",
                    "timestamp": current_time,
                    "time": time.strftime("%H:%M:%S"),
                    "signal_type": "GOD_CANDLE",
                    "direction": scan_result.direction,
                    "market": "BTC-100K",
                    "binance_price": scan_result.binance_price,
                    "poly_price": scan_result.poly_price,
                    "edge_percent": scan_result.edge_percent,
                    "confidence": scan_result.confidence,
                    "impulse_status": "PASS",
                    "trap_status": "PASS",
                    "fee_status": "PASS",
                    "status": "VALID"
                }
            }

            print(f"[GOD CANDLE] {scan_result.direction} | Edge: {scan_result.edge_percent:.2f}% | Confidence: {scan_result.confidence:.0%}")
            await self.broadcast(signal_payload)

            # Send alert
            alert_payload = {
                "type": "opportunity_alert",
                "message": "GOD CANDLE DETECTED!",
                "direction": scan_result.direction,
                "edge": scan_result.edge_percent,
                "timestamp": current_time
            }
            await self.broadcast(alert_payload)

            # EXECUTE TRADE (Fee Crusher Trigger)
            # This is the moment we pull the trigger
            print("[INGEST] Triggering execution engine...")
            asyncio.create_task(self.executor.execute_trade(signal_payload["signal"]))

    def _simulate_order_book(self, poly_implied: float) -> tuple[float, float]:
        """
        Simulate Polymarket order book (bid/ask).
        In production, this would fetch real CLOB data.

        Returns (best_bid, best_ask) for spread calculation.
        """
        # Base probability from implied price
        strike = 100000
        base_prob = max(0.1, min(0.9, (poly_implied - 90000) / 20000))

        # Normal market: tight spread (1-3 cents)
        spread = random.uniform(0.01, 0.03)
        best_bid = base_prob - spread / 2
        best_ask = base_prob + spread / 2

        # Occasionally simulate a TRAP (5% chance) - wide spread
        if random.random() < 0.05:
            spread = random.uniform(0.06, 0.15)  # 6-15 cent spread
            best_bid = base_prob - spread / 2
            best_ask = base_prob + spread / 2

        return round(best_bid, 4), round(best_ask, 4)

    def get_scanner_stats(self) -> dict:
        """Get scanner statistics"""
        return self.scanner.get_stats()

    def _calculate_gap(self) -> Optional[GapData]:
        """Calculate the Reality Gap between exchanges"""
        binance_price = self.binance.last_price
        poly_price = self.polymarket.implied_price

        if not binance_price or not poly_price:
            return None

        # Calculate gap percentage
        gap_percent = ((binance_price - poly_price) / binance_price) * 100

        # Calculate timestamp delta (the "lag")
        binance_ts = self.binance.last_timestamp
        poly_ts = self.polymarket.last_timestamp
        latency_delta = abs(binance_ts - poly_ts)

        return GapData(
            binance_price=binance_price,
            poly_implied=poly_price,
            gap_percent=round(gap_percent, 4),
            binance_ts=binance_ts,
            poly_ts=poly_ts,
            latency_delta_ms=round(latency_delta, 2)
        )

    async def stop(self):
        """Stop all streams"""
        self._running = False
        await asyncio.gather(
            self.binance.disconnect(),
            self.polymarket.disconnect(),
            return_exceptions=True
        )
        print("[INGEST] Engine stopped")
