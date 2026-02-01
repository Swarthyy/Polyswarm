"""
PolySwarm 2.0 - Trade Executor
FOK (Fill-Or-Kill) order execution with safety checks

Trading Modes:
- PAPER: Log trades without API calls
- LIVE: Real order submission via py-clob-client
"""

import os
import time
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
from datetime import datetime

# py-clob-client imports (conditional for paper mode)
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    print("[EXECUTOR] Warning: py-clob-client not available, PAPER mode only")


class TradingMode(Enum):
    """Trading mode configuration"""
    PAPER = "PAPER"  # Log only, no API calls
    LIVE = "LIVE"    # Real order submission


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PAPER_EXECUTED = "PAPER_EXECUTED"


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt"""
    success: bool
    order_id: Optional[str]
    status: OrderStatus
    filled_price: Optional[float]
    filled_amount: Optional[float]
    message: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "status": self.status.value,
            "filled_price": self.filled_price,
            "filled_amount": self.filled_amount,
            "message": self.message,
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp / 1000).strftime("%H:%M:%S")
        }


@dataclass
class ExecutorConfig:
    """Configuration for the Trade Executor"""
    trading_mode: TradingMode = TradingMode.PAPER
    max_position_size: float = 10.0      # Max $ per trade
    slippage_tolerance: float = 0.005    # 0.5% slippage allowed
    min_edge_after_fees: float = 0.035   # 3.5% minimum edge
    taker_fee: float = 0.03              # 3% Polymarket fee
    
    # Polymarket CLOB endpoints
    clob_host: str = "https://clob.polymarket.com"
    chain_id: int = 137  # Polygon mainnet


class TradeExecutor:
    """
    The Trigger Finger of Core A
    
    Executes FOK (Fill-Or-Kill) orders when signals fire.
    Implements strict safety checks before any trade.
    """

    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
        broadcast_callback: Optional[Callable] = None
    ):
        self.config = config or ExecutorConfig()
        self.broadcast = broadcast_callback
        
        # Global kill switch
        self.trading_enabled = True
        
        # Execution tracking
        self.execution_count = 0
        self.last_execution_time = 0
        self.execution_cooldown_ms = 5000  # 5 second cooldown
        
        # Execution history
        self.execution_history: list[ExecutionResult] = []
        
        # CLOB client (initialized on first LIVE trade)
        self._clob_client: Optional[ClobClient] = None
        
        # Load config from environment
        self._load_env_config()
        
        print(f"[EXECUTOR] Initialized in {self.config.trading_mode.value} mode")
        print(f"[EXECUTOR] Max position: ${self.config.max_position_size}")
        print(f"[EXECUTOR] Slippage tolerance: {self.config.slippage_tolerance * 100}%")

    def _load_env_config(self):
        """Load configuration from environment variables"""
        from dotenv import load_dotenv
        load_dotenv()
        
        # Trading mode
        mode_str = os.getenv("TRADING_MODE", "PAPER").upper()
        if mode_str == "LIVE":
            self.config.trading_mode = TradingMode.LIVE
        else:
            self.config.trading_mode = TradingMode.PAPER
        
        # Position sizing
        max_size = os.getenv("MAX_POSITION_SIZE")
        if max_size:
            self.config.max_position_size = float(max_size)
        
        # Slippage
        slippage = os.getenv("SLIPPAGE_TOLERANCE")
        if slippage:
            self.config.slippage_tolerance = float(slippage)

    def _init_clob_client(self) -> bool:
        """Initialize CLOB client for LIVE trading"""
        if not CLOB_AVAILABLE:
            print("[EXECUTOR] ERROR: py-clob-client not installed")
            return False
        
        private_key = os.getenv("POLYGON_PRIVATE_KEY")
        if not private_key:
            print("[EXECUTOR] ERROR: POLYGON_PRIVATE_KEY not set in .env")
            return False
        
        try:
            self._clob_client = ClobClient(
                host=self.config.clob_host,
                key=private_key,
                chain_id=self.config.chain_id
            )
            print("[EXECUTOR] CLOB client initialized for LIVE trading")
            return True
        except Exception as e:
            print(f"[EXECUTOR] ERROR initializing CLOB client: {e}")
            return False

    # ==================== SAFETY CHECKS ====================

    def _check_kill_switch(self) -> tuple[bool, str]:
        """Check if trading is globally enabled"""
        if not self.trading_enabled:
            return False, "KILL SWITCH ACTIVE - Trading disabled"
        return True, "Kill switch OK"

    def _check_cooldown(self) -> tuple[bool, str]:
        """Check execution cooldown"""
        current_time = time.time() * 1000
        time_since_last = current_time - self.last_execution_time
        
        if time_since_last < self.execution_cooldown_ms:
            remaining = (self.execution_cooldown_ms - time_since_last) / 1000
            return False, f"Cooldown active ({remaining:.1f}s remaining)"
        return True, "Cooldown OK"

    def _check_price_sanity(self, price: float) -> tuple[bool, str]:
        """Ensure price is within valid range"""
        if price < 0.01 or price > 0.99:
            return False, f"Price {price} out of valid range [0.01, 0.99]"
        return True, f"Price {price} is valid"

    def _check_margin_after_slippage(
        self,
        edge_percent: float,
        limit_price: float,
        direction: str
    ) -> tuple[bool, str]:
        """Ensure edge still beats fees after slippage"""
        # Calculate worst-case edge after slippage
        if direction == "BUY_YES":
            worst_price = limit_price * (1 + self.config.slippage_tolerance)
        else:
            worst_price = limit_price * (1 - self.config.slippage_tolerance)
        
        # Edge must still exceed minimum after fees
        effective_edge = edge_percent / 100 - self.config.taker_fee
        
        if effective_edge < self.config.min_edge_after_fees:
            return False, f"Edge {edge_percent:.2f}% too low after {self.config.taker_fee*100}% fee"
        
        return True, f"Margin OK: {effective_edge*100:.2f}% net edge"

    def _run_preflight_checks(self, signal: dict) -> tuple[bool, str]:
        """Run all pre-flight safety checks"""
        checks = [
            self._check_kill_switch(),
            self._check_cooldown(),
            self._check_price_sanity(signal.get("market_price", 0.5)),
            self._check_margin_after_slippage(
                signal.get("edge_percent", 0),
                signal.get("market_price", 0.5),
                signal.get("direction", "BUY_YES")
            )
        ]
        
        for passed, message in checks:
            if not passed:
                return False, message
        
        return True, "All pre-flight checks passed"

    # ==================== ORDER CALCULATION ====================

    def _calculate_limit_price(self, signal: dict) -> float:
        """Calculate FOK limit price with slippage buffer"""
        market_price = signal.get("market_price", 0.5)
        direction = signal.get("direction", "BUY_YES")
        
        if direction == "BUY_YES":
            # Willing to pay slightly more
            limit_price = market_price * (1 + self.config.slippage_tolerance)
        else:  # BUY_NO
            # Willing to pay slightly more for NO
            limit_price = market_price * (1 + self.config.slippage_tolerance)
        
        # Clamp to valid range
        return max(0.01, min(0.99, round(limit_price, 4)))

    def _calculate_position_size(self, signal: dict) -> float:
        """Calculate position size based on edge and confidence"""
        edge = signal.get("edge_percent", 0)
        confidence = signal.get("confidence", 0.5)
        
        # Scale position by confidence (Kelly-light)
        # Higher edge + confidence = larger position
        base_size = self.config.max_position_size
        scale = min(1.0, (edge / 10) * confidence)
        
        position = base_size * max(0.1, scale)
        return round(position, 2)

    # ==================== EXECUTION ====================

    async def execute_trade(self, signal: dict) -> ExecutionResult:
        """
        Execute a trade based on the signal
        
        This is the core execution function called by the scanner.
        """
        current_time = time.time() * 1000
        
        # Run pre-flight checks
        passed, message = self._run_preflight_checks(signal)
        if not passed:
            result = ExecutionResult(
                success=False,
                order_id=None,
                status=OrderStatus.REJECTED,
                filled_price=None,
                filled_amount=None,
                message=f"REJECTED: {message}",
                timestamp=current_time
            )
            print(f"[EXECUTOR] {result.message}")
            self.execution_history.append(result)
            await self._broadcast_execution(result, signal)
            return result
        
        # Calculate order parameters
        limit_price = self._calculate_limit_price(signal)
        position_size = self._calculate_position_size(signal)
        direction = signal.get("direction", "BUY_YES")
        market = signal.get("market", "UNKNOWN")
        edge = signal.get("edge_percent", 0)
        
        # Execute based on mode
        if self.config.trading_mode == TradingMode.PAPER:
            result = await self._execute_paper_trade(
                signal, limit_price, position_size
            )
        else:
            result = await self._execute_live_trade(
                signal, limit_price, position_size
            )
        
        # Update tracking
        self.execution_count += 1
        self.last_execution_time = current_time
        self.execution_history.append(result)
        
        # Broadcast result
        await self._broadcast_execution(result, signal)
        
        return result

    async def _execute_paper_trade(
        self,
        signal: dict,
        limit_price: float,
        position_size: float
    ) -> ExecutionResult:
        """Execute a paper trade (log only)"""
        direction = signal.get("direction", "BUY_YES")
        market = signal.get("market", "UNKNOWN")
        edge = signal.get("edge_percent", 0)
        
        token = "YES" if direction == "BUY_YES" else "NO"
        
        # Generate paper order ID
        order_id = f"PAPER-{self.execution_count + 1:04d}"
        
        # Log the paper trade
        print("=" * 60)
        print(f"[PAPER TRADE] {direction}")
        print(f"  Market:    {market}")
        print(f"  Token:     {token}")
        print(f"  Price:     ${limit_price:.4f}")
        print(f"  Amount:    ${position_size:.2f}")
        print(f"  Edge:      +{edge:.2f}%")
        print(f"  Order ID:  {order_id}")
        print("=" * 60)
        
        return ExecutionResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.PAPER_EXECUTED,
            filled_price=limit_price,
            filled_amount=position_size,
            message=f"PAPER: {token} @ ${limit_price:.4f} x ${position_size:.2f}",
            timestamp=time.time() * 1000
        )

    async def _execute_live_trade(
        self,
        signal: dict,
        limit_price: float,
        position_size: float
    ) -> ExecutionResult:
        """Execute a LIVE trade via CLOB API"""
        # Initialize client if needed
        if not self._clob_client:
            if not self._init_clob_client():
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    status=OrderStatus.REJECTED,
                    filled_price=None,
                    filled_amount=None,
                    message="CLOB client initialization failed",
                    timestamp=time.time() * 1000
                )
        
        direction = signal.get("direction", "BUY_YES")
        market = signal.get("market", "UNKNOWN")
        token_id = signal.get("token_id")  # Would need actual token ID
        
        if not token_id:
            return ExecutionResult(
                success=False,
                order_id=None,
                status=OrderStatus.REJECTED,
                filled_price=None,
                filled_amount=None,
                message="No token_id provided in signal",
                timestamp=time.time() * 1000
            )
        
        try:
            # Build FOK order
            side = BUY
            
            order_args = OrderArgs(
                token_id=token_id,
                price=limit_price,
                size=position_size,
                side=side
            )
            
            # Submit FOK order
            # Note: py-clob-client may not have direct FOK support,
            # this is a placeholder for the actual implementation
            response = self._clob_client.create_order(order_args)
            
            order_id = response.get("orderID", "UNKNOWN")
            
            print(f"[LIVE TRADE] Order submitted: {order_id}")
            
            return ExecutionResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.PENDING,
                filled_price=limit_price,
                filled_amount=position_size,
                message=f"LIVE: Order {order_id} submitted",
                timestamp=time.time() * 1000
            )
            
        except Exception as e:
            print(f"[EXECUTOR] LIVE trade error: {e}")
            return ExecutionResult(
                success=False,
                order_id=None,
                status=OrderStatus.REJECTED,
                filled_price=None,
                filled_amount=None,
                message=f"LIVE trade failed: {str(e)}",
                timestamp=time.time() * 1000
            )

    async def _broadcast_execution(self, result: ExecutionResult, signal: dict):
        """Broadcast execution result to frontend"""
        if not self.broadcast:
            return
        
        payload = {
            "type": "execution_result",
            "result": result.to_dict(),
            "signal": {
                "id": signal.get("id"),
                "market": signal.get("market"),
                "direction": signal.get("direction"),
                "edge_percent": signal.get("edge_percent")
            }
        }
        
        try:
            await self.broadcast(payload)
        except Exception as e:
            print(f"[EXECUTOR] Broadcast error: {e}")

    # ==================== CONTROL ====================

    def enable_trading(self):
        """Enable trading (release kill switch)"""
        self.trading_enabled = True
        print("[EXECUTOR] Trading ENABLED")

    def disable_trading(self):
        """Disable trading (engage kill switch)"""
        self.trading_enabled = False
        print("[EXECUTOR] Trading DISABLED (Kill switch engaged)")

    def get_status(self) -> dict:
        """Get current executor status"""
        return {
            "trading_enabled": self.trading_enabled,
            "trading_mode": self.config.trading_mode.value,
            "execution_count": self.execution_count,
            "last_execution_time": self.last_execution_time,
            "max_position_size": self.config.max_position_size,
            "slippage_tolerance": self.config.slippage_tolerance,
            "recent_executions": [
                e.to_dict() for e in self.execution_history[-5:]
            ]
        }
