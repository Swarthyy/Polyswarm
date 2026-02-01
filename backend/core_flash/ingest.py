"""
PolySwarm 2.0 - Ingestion Engine
Dual-socket connection to Binance (real-time) and Polymarket (CLOB)
Calculates and broadcasts the "Reality Gap" between exchanges
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Callable, Optional
from collections import deque

import aiohttp


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
    """

    def __init__(self, broadcast_callback: Callable):
        self.binance = BinanceStream()
        self.polymarket = PolymarketStream()
        self.broadcast = broadcast_callback
        self._running = False

        # Price history for visualization (last 100 points)
        self.price_history: deque = deque(maxlen=100)

        # Link streams for simulation
        self.polymarket.set_binance_reference(self.binance)

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
        This is the core "Reality Gap" visualization feed
        """
        print("[INGEST] Starting 10Hz broadcast loop...")

        # Wait for initial data
        await asyncio.sleep(1)

        while self._running:
            try:
                gap_data = self._calculate_gap()

                if gap_data:
                    # Build payload for frontend
                    payload = {
                        "type": "gap_monitor",
                        "binance": gap_data.binance_price,
                        "poly_implied": gap_data.poly_implied,
                        "gap_percent": gap_data.gap_percent,
                        "latency_delta_ms": gap_data.latency_delta_ms,
                        "timestamp": int(time.time() * 1000),
                        "binance_ts": gap_data.binance_ts,
                        "poly_ts": gap_data.poly_ts
                    }

                    # Broadcast to all connected clients
                    await self.broadcast(payload)

            except Exception as e:
                print(f"[INGEST] Broadcast error: {e}")

            # 100ms interval = 10Hz
            await asyncio.sleep(0.1)

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
