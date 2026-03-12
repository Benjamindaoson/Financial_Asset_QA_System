"""Compatibility exports for API routes."""

from app.api import routes_module

router = routes_module.router
agent = routes_module.agent
enricher = routes_module.enricher
market_service = routes_module.market_service
settings = routes_module.settings

__all__ = ["agent", "enricher", "market_service", "router", "settings"]
