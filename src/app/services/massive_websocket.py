"""
Massive.com WebSocket service for live market data.

Provides real-time (or 15-min delayed on Starter plan) minute bar updates
via WebSocket connection to Massive.com (formerly Polygon.io).
"""

from __future__ import annotations

import os
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable
from datetime import datetime

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    import pandas as pd


class MassiveWebSocketService(QThread):
    """
    Background thread managing WebSocket connection to Massive.com.

    Emits signals when new minute bars arrive, which can be connected
    to chart update slots in the main thread.

    Usage:
        ws = MassiveWebSocketService()
        ws.bar_received.connect(on_bar_received)
        ws.start()
        ws.subscribe("AAPL")

        # When done:
        ws.stop()
        ws.wait()
    """

    # Signals (emitted in main thread via Qt's signal mechanism)
    bar_received = Signal(str, object)  # (ticker, dict with OHLCV)
    connection_status = Signal(str)  # "connected", "disconnected", "error:{msg}"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._api_key = self._load_api_key()
        self._current_ticker: Optional[str] = None
        self._ws_client = None
        self._running = False
        self._stop_event = threading.Event()

    @staticmethod
    def _load_api_key() -> Optional[str]:
        """Load API key from environment or .env file."""
        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)
        return os.getenv("POLYGON_API_KEY")

    def subscribe(self, ticker: str) -> None:
        """
        Subscribe to minute bars for a ticker.

        Automatically unsubscribes from previous ticker if any.

        Args:
            ticker: Ticker symbol in Yahoo format (e.g., "AAPL", "BTC-USD")
        """
        if self._ws_client is None:
            self._current_ticker = ticker
            return

        # Unsubscribe from previous ticker
        if self._current_ticker:
            old_sub = f"AM.{self._convert_ticker(self._current_ticker)}"
            try:
                self._ws_client.unsubscribe(old_sub)
            except Exception:
                pass

        # Subscribe to new ticker
        self._current_ticker = ticker
        new_sub = f"AM.{self._convert_ticker(ticker)}"
        try:
            self._ws_client.subscribe(new_sub)
            print(f"WebSocket subscribed to {new_sub}")
        except Exception as e:
            print(f"WebSocket subscribe error: {e}")

    def unsubscribe(self) -> None:
        """Unsubscribe from current ticker."""
        if self._ws_client and self._current_ticker:
            sub = f"AM.{self._convert_ticker(self._current_ticker)}"
            try:
                self._ws_client.unsubscribe(sub)
            except Exception:
                pass
        self._current_ticker = None

    @staticmethod
    def _convert_ticker(yahoo_ticker: str) -> str:
        """
        Convert Yahoo Finance ticker format to Massive format.

        For WebSocket subscriptions:
        - Stocks: AAPL -> AAPL
        - Crypto: BTC-USD -> X:BTCUSD (requires crypto market)
        """
        ticker = yahoo_ticker.upper().strip()

        # Crypto: BTC-USD -> X:BTCUSD
        if ticker.endswith("-USD"):
            base = ticker.replace("-USD", "")
            return f"X:{base}USD"

        return ticker

    def _handle_message(self, messages: list) -> None:
        """Handle incoming WebSocket messages."""
        for msg in messages:
            ev = msg.get("ev")

            if ev == "status":
                status = msg.get("status", "")
                if status == "connected":
                    self.connection_status.emit("connected")
                    # Subscribe to current ticker if any
                    if self._current_ticker:
                        sub = f"AM.{self._convert_ticker(self._current_ticker)}"
                        self._ws_client.subscribe(sub)
                elif status == "auth_success":
                    print("WebSocket authenticated")
                elif status == "auth_failed":
                    self.connection_status.emit("error:auth_failed")

            elif ev == "AM":
                # Aggregate Minute bar
                bar_data = {
                    "ticker": msg.get("sym", ""),
                    "open": msg.get("o"),
                    "high": msg.get("h"),
                    "low": msg.get("l"),
                    "close": msg.get("c"),
                    "volume": msg.get("v", 0),
                    "start_ts": msg.get("s"),  # Start timestamp (ms)
                    "end_ts": msg.get("e"),  # End timestamp (ms)
                }

                # Convert Massive ticker back to Yahoo format for matching
                sym = msg.get("sym", "")
                if sym.startswith("X:") and sym.endswith("USD"):
                    # X:BTCUSD -> BTC-USD
                    yahoo_ticker = sym[2:-3] + "-USD"
                else:
                    yahoo_ticker = sym

                self.bar_received.emit(yahoo_ticker, bar_data)

    def run(self) -> None:
        """Main WebSocket loop (runs in background thread)."""
        from massive import WebSocketClient
        from massive.websocket.models import Feed, Market

        if not self._api_key:
            self.connection_status.emit("error:no_api_key")
            return

        self._running = True
        self._stop_event.clear()

        try:
            # Determine market type based on current ticker
            is_crypto = (
                self._current_ticker
                and self._current_ticker.upper().endswith("-USD")
            )

            # Use delayed feed for Starter plan
            feed = Feed.Delayed

            # Create WebSocket client
            self._ws_client = WebSocketClient(
                api_key=self._api_key,
                feed=feed,
                market=Market.Crypto if is_crypto else Market.Stocks,
                subscriptions=[f"AM.{self._convert_ticker(self._current_ticker)}"]
                if self._current_ticker
                else [],
                max_reconnects=5,
                verbose=False,
            )

            print(f"WebSocket connecting to {feed.value}...")
            self.connection_status.emit("connecting")

            # Run the WebSocket (blocking)
            self._ws_client.run(handle_msg=self._handle_message)

        except Exception as e:
            print(f"WebSocket error: {e}")
            self.connection_status.emit(f"error:{e}")

        finally:
            self._running = False
            self.connection_status.emit("disconnected")

    def stop(self) -> None:
        """Stop the WebSocket connection."""
        self._running = False
        self._stop_event.set()

        if self._ws_client:
            try:
                # The close method may return a coroutine, handle both cases
                import asyncio
                result = self._ws_client.close()
                if asyncio.iscoroutine(result):
                    # If it's a coroutine, we need to run it
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Can't run in existing loop, just let it timeout
                            pass
                        else:
                            loop.run_until_complete(result)
                    except RuntimeError:
                        # No event loop, create one
                        asyncio.run(result)
            except Exception:
                pass
            self._ws_client = None

    def is_running(self) -> bool:
        """Check if WebSocket is running."""
        return self._running
