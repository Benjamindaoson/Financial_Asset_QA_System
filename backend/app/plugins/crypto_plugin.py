"""Example cryptocurrency plugin.

This is a demonstration plugin showing how to extend the system
with custom tools without modifying core code.
"""

from typing import Any, Dict
import logging

from app.plugins.base import ToolPlugin

logger = logging.getLogger(__name__)


class CryptoToolPlugin(ToolPlugin):
    """Example plugin for cryptocurrency price lookup.

    This plugin demonstrates the plugin system but is not enabled
    by default. To enable:

    1. Install required dependencies (e.g., ccxt for crypto exchanges)
    2. Configure API keys in settings
    3. Register plugin in AgentCore
    """

    @property
    def name(self) -> str:
        return "get_crypto_price"

    @property
    def description(self) -> str:
        return "Get cryptocurrency price from major exchanges (BTC, ETH, etc.)"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Crypto symbol (e.g., BTC, ETH, SOL)"
                },
                "exchange": {
                    "type": "string",
                    "description": "Exchange name (default: binance)",
                    "default": "binance"
                }
            },
            "required": ["symbol"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute crypto price lookup.

        Args:
            symbol: Crypto symbol (e.g., BTC, ETH)
            exchange: Exchange name (default: binance)

        Returns:
            Price data dictionary
        """
        symbol = kwargs["symbol"]
        exchange = kwargs.get("exchange", "binance")

        logger.info(f"[CryptoPlugin] Fetching {symbol} price from {exchange}")

        # This is a placeholder implementation
        # In production, would use ccxt or similar library:
        #
        # import ccxt
        # exchange_obj = getattr(ccxt, exchange)()
        # ticker = await exchange_obj.fetch_ticker(f"{symbol}/USDT")
        # return {
        #     "symbol": symbol,
        #     "price": ticker["last"],
        #     "volume_24h": ticker["quoteVolume"],
        #     "change_24h": ticker["percentage"],
        #     "source": exchange,
        #     "timestamp": ticker["timestamp"]
        # }

        # Placeholder response
        return {
            "symbol": symbol,
            "price": 50000.0,
            "volume_24h": 1000000000,
            "change_24h": 2.5,
            "source": exchange,
            "timestamp": "2024-01-01T00:00:00Z",
            "note": "This is a placeholder. Install ccxt and configure to enable."
        }
