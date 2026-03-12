"""Market data service with cache, analytics, and provider fallback."""

from __future__ import annotations

import asyncio
import csv
import os

# Clear proxy env vars so httpx connects directly (VPN proxy may be unavailable)
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    _v = os.environ.pop(_k, None)
    if _v:
        print(f"[market-service] Cleared proxy: {_k}={_v}")
import json
import math
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx
import numpy as np
import redis
import yfinance as yf
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

from app.cache.popular_stocks import get_popular_stocks
from app.config import settings
from app.market.api_providers import NewsAPIProvider, FinnhubProvider
from app.models import (
    ChangeData,
    CompanyInfo,
    ComparisonData,
    ComparisonPoint,
    ComparisonRow,
    HistoryData,
    MarketData,
    MarketIndexSnapshot,
    MarketOverviewResponse,
    MarketSignal,
    MarketSummary,
    PricePoint,
    RiskMetrics,
    SectorSnapshot,
)


TREND_UP = "上涨"
TREND_DOWN = "下跌"
TREND_FLAT = "震荡"

RANGE_TO_DAYS = {
    "1d": 1,
    "5d": 5,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "ytd": 365,
    "1y": 365,
    "5y": 365 * 5,
}

# yfinance period 映射
RANGE_TO_YFINANCE_PERIOD = {
    "1d": "1d",
    "5d": "5d",
    "1m": "1mo",
    "3m": "3mo",
    "6m": "6mo",
    "ytd": "ytd",
    "1y": "1y",
    "5y": "5y",
}

INDEX_WATCHLIST = [
    ("SPY", "标普 500"),
    ("QQQ", "纳斯达克"),
    ("DIA", "道琼斯"),
    ("VIXY", "恐慌指数"),
    ("BND", "美债 ETF"),
]

SECTOR_WATCHLIST = [
    ("XLK", "科技"),
    ("XLF", "金融"),
    ("XLE", "能源"),
    ("XLV", "医疗"),
    ("XLY", "可选消费"),
    ("XLI", "工业"),
]


class TickerMapper:
    """Maps company names and common aliases to ticker symbols."""

    EXACT_MAP = {
        "阿里巴巴": "9988.HK",
        "苹果": "AAPL",
        "腾讯": "0700.HK",
        "特斯拉": "TSLA",
        "英伟达": "NVDA",
        "微软": "MSFT",
        "亚马逊": "AMZN",
        "谷歌": "GOOGL",
        "茅台": "600519.SS",
        "贵州茅台": "600519.SS",
        "比亚迪": "002594.SZ",
        "纳指": "^IXIC",
        "标普500": "^GSPC",
        "道琼斯": "^DJI",
        "波动率指数": "^VIX",
        "vix": "^VIX",
        "比特币": "BTC-USD",
        "以太坊": "ETH-USD",
        "黄金etf": "GLD",
        "原油etf": "USO",
        "债券": "BND",
        "债券etf": "BND",
        "美国国债": "TLT",
        "10年期美债": "^TNX",
        "20年期美债": "TLT",
        "7-10年美债": "IEF",
        "短债": "SHY",
        "总债券市场": "BND",
        "纳斯达克100": "QQQ",
        "标普etf": "SPY",
    }

    @classmethod
    def normalize(cls, symbol: str) -> str:
        if not symbol:
            return ""

        normalized = symbol.strip()
        if not normalized:
            return ""

        lowered = normalized.lower()
        if lowered in cls.EXACT_MAP:
            return cls.EXACT_MAP[lowered]
        if normalized in cls.EXACT_MAP:
            return cls.EXACT_MAP[normalized]

        if normalized.isdigit() and len(normalized) == 6:
            if normalized.startswith("6"):
                return f"{normalized}.SS"
            if normalized.startswith(("0", "3")):
                return f"{normalized}.SZ"

        return normalized.upper()


class MarketDataService:
    """市场数据服务，支持多数据源故障切换和内存缓存。

    数据源优先级：
    - 美股/ETF/指数：yfinance (主) -> stooq (备) -> alpha_vantage (兜底)
    - A股：akshare (主) -> yfinance (备)
    - 港股：yfinance (主) -> akshare (备)
    """

    # 数据源超时设置（秒）
    TIMEOUT_YFINANCE = 3
    TIMEOUT_AKSHARE = 3
    TIMEOUT_STOOQ = 3
    TIMEOUT_ALPHA_VANTAGE = 3

    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
        except Exception:
            self.redis_client = None

        # 内存缓存（当 Redis 不可用时使用）
        self._memory_cache: Dict[str, tuple[Any, float]] = {}  # key -> (value, expire_time)

        self.ticker_mapper = TickerMapper()
        self.news_provider = NewsAPIProvider()
        self.finnhub_provider = FinnhubProvider()
        self._stooq_semaphore = asyncio.Semaphore(3)
        self._market_timezones = {
            "US": "US/Eastern",
            "HK": "Asia/Hong_Kong",
            "CN": "Asia/Shanghai"
        }

    def _get_cache(self, key: str) -> Optional[dict]:
        """从缓存获取数据，优先使用 Redis，不可用时使用内存缓存。"""
        # 尝试 Redis
        if self.redis_client:
            try:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # 回退到内存缓存
        if key in self._memory_cache:
            value, expire_time = self._memory_cache[key]
            if datetime.utcnow().timestamp() < expire_time:
                return value
            else:
                del self._memory_cache[key]

        return None

    def _set_cache(self, key: str, value: dict, ttl: int) -> None:
        """设置缓存，优先使用 Redis，不可用时使用内存缓存。"""
        # 尝试 Redis
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass

        # 回退到内存缓存
        expire_time = datetime.utcnow().timestamp() + ttl
        self._memory_cache[key] = (value, expire_time)

        # 清理过期的内存缓存条目（简单策略：每100次写入清理一次）
        if len(self._memory_cache) > 100:
            now = datetime.utcnow().timestamp()
            expired_keys = [k for k, (_, exp) in self._memory_cache.items() if exp < now]
            for k in expired_keys:
                del self._memory_cache[k]
 
    def _get_market_status(self, symbol: str) -> str:
        """Determines if the market for a given symbol is currently open."""
        now = datetime.utcnow()
        
        # Simple heuristic for timezones and hours
        if self._is_china_a_stock(symbol):
            # CN: 9:30-11:30, 13:00-15:00 CST (UTC+8)
            cn_now = now + timedelta(hours=8)
            if cn_now.weekday() >= 5: return "closed"
            h, m = cn_now.hour, cn_now.minute
            if (9, 30) <= (h, m) <= (11, 30) or (13, 0) <= (h, m) <= (15, 0):
                return "open"
        elif self._is_hk_stock(symbol):
            # HK: 9:30-12:00, 13:00-16:00 HKT (UTC+8)
            hk_now = now + timedelta(hours=8)
            if hk_now.weekday() >= 5: return "closed"
            h, m = hk_now.hour, hk_now.minute
            if (9, 30) <= (h, m) <= (12, 0) or (13, 0) <= (h, m) <= (16, 0):
                return "open"
        else:
            # US: 9:30-16:00 ET (UTC-5/UTC-4) - Simplified to UTC-5
            us_now = now - timedelta(hours=5)
            if us_now.weekday() >= 5: return "closed"
            h, m = us_now.hour, us_now.minute
            if (9, 30) <= (h, m) <= (16, 0):
                return "open"
        
        return "closed"

    def _get_dynamic_ttl(self, symbol: str, data_type: str) -> int:
        """Returns TTL in seconds based on market status and data type."""
        status = self._get_market_status(symbol)
        
        if data_type == "price":
            return 60 if status == "open" else 3600
        if data_type == "history":
            return 3600 if status == "open" else 86400
        if data_type == "info":
            return 86400 * 7  # 1 week
        if data_type == "news":
            return 300 if status == "open" else 3600
            
        return settings.CACHE_TTL_PRICE

    @staticmethod
    def _utc_now() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _safe_days(days: Optional[int], default: int = 30) -> int:
        try:
            normalized = abs(int(days or default))
        except (TypeError, ValueError):
            normalized = default
        return normalized if normalized > 0 else default

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            if value in (None, "", "-", "None", "N/D"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            if value in (None, "", "-", "None", "N/D"):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _range_to_period(range_key: Optional[str], days: int) -> tuple[str, int]:
        """将 range_key 转换为 yfinance period 和天数。"""
        if not range_key:
            safe_days = max(7, days)
            return f"{safe_days}d", safe_days

        normalized = range_key.lower()
        if normalized not in RANGE_TO_YFINANCE_PERIOD:
            safe_days = max(7, days)
            return f"{safe_days}d", safe_days

        return RANGE_TO_YFINANCE_PERIOD[normalized], RANGE_TO_DAYS.get(normalized, days)

    @staticmethod
    def _infer_asset_type(info: Optional[dict], symbol: str) -> str:
        if not info:
            if symbol.endswith("-USD"):
                return "crypto"
            if symbol.startswith("^"):
                return "index"
            return "equity"

        quote_type = str(info.get("quoteType") or info.get("instrumentType") or "").lower()
        if "etf" in quote_type:
            return "etf"
        if "bond" in quote_type or symbol in {"BND", "TLT", "IEF", "SHY"}:
            return "bond"
        if "index" in quote_type or symbol.startswith("^"):
            return "index"
        if "currency" in quote_type or symbol.endswith("-USD"):
            return "crypto"
        return "equity"

    @staticmethod
    def _is_china_a_stock(symbol: str) -> bool:
        """判断是否为A股代码。"""
        if symbol.endswith((".SS", ".SZ")):
            return True
        # 纯数字6位代码
        if symbol.isdigit() and len(symbol) == 6:
            return True
        return False

    @staticmethod
    def _is_hk_stock(symbol: str) -> bool:
        """判断是否为港股代码。"""
        return symbol.endswith(".HK")

    async def _fetch_yfinance(self, symbol: str) -> Optional[yf.Ticker]:
        """获取 yfinance Ticker 对象，带超时控制。"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(yf.Ticker, symbol),
                timeout=self.TIMEOUT_YFINANCE
            )
        except (asyncio.TimeoutError, Exception):
            return None

    async def _fetch_yfinance_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取 yfinance 股票信息，带超时控制。"""
        ticker = await self._fetch_yfinance(symbol)
        if not ticker:
            return None
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(lambda: ticker.info),
                timeout=self.TIMEOUT_YFINANCE
            )
        except (asyncio.TimeoutError, Exception):
            return None

    async def _fetch_yfinance_history(self, symbol: str, period: str):
        """获取 yfinance 历史数据，带超时控制。"""
        ticker = await self._fetch_yfinance(symbol)
        if not ticker:
            return None
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(lambda: ticker.history(period=period, auto_adjust=False)),
                timeout=self.TIMEOUT_YFINANCE
            )
        except (asyncio.TimeoutError, Exception):
            return None

    async def _fetch_akshare_price(self, symbol: str) -> Optional[MarketData]:
        """使用 akshare 获取A股实时价格，带超时控制。"""
        if not AKSHARE_AVAILABLE:
            return None

        try:
            # 提取纯数字代码
            if symbol.endswith(".SS") or symbol.endswith(".SZ"):
                code = symbol[:-3]
            elif symbol.isdigit() and len(symbol) == 6:
                code = symbol
            else:
                return None

            # 获取实时行情
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.stock_zh_a_spot_em),
                timeout=self.TIMEOUT_AKSHARE
            )

            # 查找对应股票
            row = df[df['代码'] == code]
            if row.empty:
                return None

            price = self._coerce_float(row.iloc[0]['最新价'])
            if price is None:
                return None

            return MarketData(
                symbol=symbol,
                price=price,
                currency="CNY",
                name=str(row.iloc[0].get('名称', symbol)),
                asset_type="equity",
                source="akshare",
                timestamp=self._utc_now(),
            )
        except (asyncio.TimeoutError, Exception):
            return None

    async def _fetch_akshare_history(self, symbol: str, days: int, range_key: Optional[str] = None) -> Optional[HistoryData]:
        """使用 akshare 获取A股历史数据，带超时控制。"""
        if not AKSHARE_AVAILABLE:
            return None

        try:
            # 提取纯数字代码
            if symbol.endswith(".SS") or symbol.endswith(".SZ"):
                code = symbol[:-3]
            elif symbol.isdigit() and len(symbol) == 6:
                code = symbol
            else:
                return None

            # 计算日期范围
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

            # 获取历史数据
            df = await asyncio.wait_for(
                asyncio.to_thread(
                    ak.stock_zh_a_hist,
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=""
                ),
                timeout=self.TIMEOUT_AKSHARE
            )

            if df.empty:
                return None

            # 转换为 PricePoint
            points: List[PricePoint] = []
            for _, row in df.iterrows():
                date_str = str(row['日期'])
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

                open_price = self._coerce_float(row.get('开盘'))
                high = self._coerce_float(row.get('最高'))
                low = self._coerce_float(row.get('最低'))
                close = self._coerce_float(row.get('收盘'))
                volume = self._coerce_int(row.get('成交量')) or 0

                if None in {open_price, high, low, close}:
                    continue

                points.append(
                    PricePoint(
                        date=date_str,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                    )
                )

            if not points:
                return None

            # 限制返回的数据点数量
            if len(points) > days:
                points = points[-days:]

            return HistoryData(
                symbol=symbol,
                days=len(points),
                range_key=range_key,
                data=points,
                source="akshare",
                timestamp=self._utc_now(),
            )
        except (asyncio.TimeoutError, Exception):
            return None

    async def _request_alpha_vantage(self, function: str, symbol: str, **extra_params) -> Optional[dict]:
        if not settings.ALPHA_VANTAGE_API_KEY:
            return None

        params = {
            "function": function,
            "symbol": symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY,
        }
        params.update(extra_params)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://www.alphavantage.co/query", params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                if "Error Message" in data or "Note" in data or "Information" in data:
                    return None
                return data
        except Exception:
            return None

    def _to_stooq_symbol(self, symbol: str) -> Optional[str]:
        normalized = symbol.upper()
        index_map = {
            "^GSPC": "^spx",
            "^IXIC": "^ndq",
            "^DJI": "^dji",
            "^VIX": "^vix",
        }
        if normalized in index_map:
            return index_map[normalized]
        if normalized.endswith(".HK"):
            # Check for 4-digit numeric symbols (common in HK)
            base = normalized[:-3]
            if base.isdigit():
                return f"{int(base)}.hk"
            return f"{base.lower()}.hk"
        if normalized.endswith(".SS") or normalized.endswith(".SZ"):
            return f"{normalized[:6].lower()}.cn"
        if normalized.endswith("-USD"):
            return None
        if normalized.startswith("^"):
            return normalized.lower()
        return f"{normalized.lower()}.us"

    async def _request_stooq(self, endpoint: str, symbol: str) -> Optional[str]:
        stooq_symbol = self._to_stooq_symbol(symbol)
        if not stooq_symbol:
            return None

        async with self._stooq_semaphore:
            for _ in range(2):
                try:
                    async with httpx.AsyncClient(timeout=8) as client:
                        response = await client.get(
                            f"https://stooq.com/{endpoint}?s={stooq_symbol}&i=d",
                            follow_redirects=True,
                        )
                        if response.status_code == 200 and response.text.strip():
                            return response.text
                except Exception as e:
                    print(f"Stooq request failed for {symbol}: {type(e).__name__}: {e}")
                    await asyncio.sleep(1)
                    continue
        return None

    async def _fetch_stooq_quote(self, symbol: str) -> Optional[MarketData]:
        raw = await self._request_stooq("q/l/", symbol)
        if not raw:
            return None

        rows = list(csv.reader(StringIO(raw)))
        if not rows:
            return None
        row = rows[0]
        if len(row) < 8 or row[1] == "N/D":
            return None

        price = self._coerce_float(row[6])
        if price is None:
            return None

        return MarketData(
            symbol=symbol,
            price=price,
            currency="USD",
            name=symbol,
            asset_type=self._infer_asset_type(None, symbol),
            source="stooq",
            timestamp=self._utc_now(),
        )

    async def _fetch_stooq_history(self, symbol: str, days: int, range_key: Optional[str] = None) -> Optional[HistoryData]:
        raw = await self._request_stooq("q/d/l/", symbol)
        if not raw:
            return None

        rows = list(csv.DictReader(StringIO(raw)))
        rows = [row for row in rows if row.get("Date")]
        if not rows:
            return None

        if range_key == "5y":
            limit = 365 * 5
        elif range_key == "1y":
            limit = 365
        elif range_key == "ytd":
            current_year = datetime.utcnow().year
            rows = [row for row in rows if row["Date"].startswith(str(current_year))]
            limit = len(rows)
        else:
            limit = days

        selected = rows[-max(limit, 1):]
        points: List[PricePoint] = []
        for row in selected:
            open_price = self._coerce_float(row.get("Open"))
            high = self._coerce_float(row.get("High"))
            low = self._coerce_float(row.get("Low"))
            close = self._coerce_float(row.get("Close"))
            volume = self._coerce_int(row.get("Volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=row["Date"],
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

        if not points:
            return None

        return HistoryData(
            symbol=symbol,
            days=days,
            range_key=range_key,
            data=points,
            source="stooq",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_quote(self, symbol: str) -> Optional[MarketData]:
        data = await self._request_alpha_vantage("GLOBAL_QUOTE", symbol)
        quote = data.get("Global Quote") if data else None
        if not quote:
            return None

        price = self._coerce_float(quote.get("05. price"))
        if price is None:
            return None

        return MarketData(
            symbol=symbol,
            price=price,
            currency="USD",
            name=symbol,
            asset_type="equity",
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_history(self, symbol: str, days: int, range_key: Optional[str] = None) -> Optional[HistoryData]:
        outputsize = "full" if (range_key or "").lower() == "5y" or days > 100 else "compact"
        data = await self._request_alpha_vantage("TIME_SERIES_DAILY", symbol, outputsize=outputsize)
        series = data.get("Time Series (Daily)") if data else None
        if not series:
            return None

        sorted_rows = sorted(series.items())[-days:]
        points: List[PricePoint] = []
        for trade_date, values in sorted_rows:
            open_price = self._coerce_float(values.get("1. open"))
            high = self._coerce_float(values.get("2. high"))
            low = self._coerce_float(values.get("3. low"))
            close = self._coerce_float(values.get("4. close"))
            volume = self._coerce_int(values.get("5. volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

        if not points:
            return None

        return HistoryData(
            symbol=symbol,
            days=len(points),
            range_key=range_key,
            data=points,
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    async def _fetch_alpha_vantage_info(self, symbol: str) -> Optional[CompanyInfo]:
        data = await self._request_alpha_vantage("OVERVIEW", symbol)
        if not data or not data.get("Symbol"):
            return None

        return CompanyInfo(
            symbol=symbol,
            name=data.get("Name") or symbol,
            sector=data.get("Sector"),
            industry=data.get("Industry"),
            market_cap=self._coerce_int(data.get("MarketCapitalization")),
            pe_ratio=self._coerce_float(data.get("PERatio")),
            week_52_high=self._coerce_float(data.get("52WeekHigh")),
            week_52_low=self._coerce_float(data.get("52WeekLow")),
            description=(data.get("Description") or "")[:300],
            source="alpha_vantage",
            timestamp=self._utc_now(),
        )

    def _history_to_points(self, history_frame: Any) -> List[PricePoint]:
        points: List[PricePoint] = []
        if history_frame is None or getattr(history_frame, "empty", True):
            return points

        for index, row in history_frame.iterrows():
            open_price = self._coerce_float(row.get("Open"))
            high = self._coerce_float(row.get("High"))
            low = self._coerce_float(row.get("Low"))
            close = self._coerce_float(row.get("Close"))
            volume = self._coerce_int(row.get("Volume")) or 0
            if None in {open_price, high, low, close}:
                continue
            points.append(
                PricePoint(
                    date=index.strftime("%Y-%m-%d"),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        return points

    async def get_price(self, symbol: str) -> MarketData:
        """获取实时价格，优先使用 yfinance，A股使用 akshare。

        数据源优先级：
        - A股：akshare -> yfinance -> stooq -> alpha_vantage
        - 港股/美股：yfinance -> stooq -> alpha_vantage
        """
        start_time = datetime.utcnow()
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return MarketData(symbol="", source="unavailable", timestamp=self._utc_now(), error="Invalid symbol")

        cache_key = f"price:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            result = MarketData(**cached)
            result.cache_hit = True
            result.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return result

        attempted_sources = []

        # A股优先使用 akshare
        if self._is_china_a_stock(normalized):
            akshare_result = await self._fetch_akshare_price(normalized)
            attempted_sources.append("akshare")
            if akshare_result:
                akshare_result.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._set_cache(cache_key, akshare_result.model_dump(exclude={"cache_hit", "latency_ms"}), self._get_dynamic_ttl(normalized, "price"))
                return akshare_result

        # 主数据源：yfinance
        info = await self._fetch_yfinance_info(normalized)
        attempted_sources.append("yfinance")
        if info:
            price = self._coerce_float(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
            if price is not None:
                result = MarketData(
                    symbol=normalized,
                    price=price,
                    currency=info.get("currency", "USD"),
                    name=info.get("longName") or info.get("shortName") or normalized,
                    asset_type=self._infer_asset_type(info, normalized),
                    source="yfinance",
                    timestamp=self._utc_now(),
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )
                self._set_cache(cache_key, result.model_dump(exclude={"cache_hit", "latency_ms"}), self._get_dynamic_ttl(normalized, "price"))
                return result

        # 备用数据源：stooq
        stooq_result = await self._fetch_stooq_quote(normalized)
        attempted_sources.append("stooq")
        if stooq_result:
            stooq_result.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._set_cache(cache_key, stooq_result.model_dump(exclude={"cache_hit", "latency_ms"}), self._get_dynamic_ttl(normalized, "price"))
            return stooq_result

        # 兜底数据源：alpha_vantage
        av_result = await self._fetch_alpha_vantage_quote(normalized)
        attempted_sources.append("alpha_vantage")
        if av_result:
            av_result.latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._set_cache(cache_key, av_result.model_dump(exclude={"cache_hit", "latency_ms"}), self._get_dynamic_ttl(normalized, "price"))
            return av_result

        # 所有数据源都失败
        return MarketData(
            symbol=normalized,
            source="unavailable",
            timestamp=self._utc_now(),
            error=f"all_sources_failed: {', '.join(attempted_sources)}",
            latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
        )

    async def get_history(self, symbol: str, days: int = 30, range_key: Optional[str] = None) -> HistoryData:
        """获取历史数据，优先使用 yfinance，A股使用 akshare。

        数据源优先级：
        - A股：akshare -> yfinance -> stooq -> alpha_vantage
        - 港股/美股：yfinance -> stooq -> alpha_vantage
        """
        normalized = self.ticker_mapper.normalize(symbol)
        period, normalized_days = self._range_to_period(range_key, self._safe_days(days))
        cache_key = f"history:{normalized}:{range_key or normalized_days}"
        cached = self._get_cache(cache_key)
        if cached:
            return HistoryData(**cached)

        attempted_sources = []

        # A股优先使用 akshare
        if self._is_china_a_stock(normalized):
            akshare_result = await self._fetch_akshare_history(normalized, normalized_days, range_key=range_key)
            attempted_sources.append("akshare")
            if akshare_result and len(akshare_result.data) >= 2:
                self._set_cache(cache_key, akshare_result.model_dump(), self._get_dynamic_ttl(normalized, "history"))
                return akshare_result

        # 主数据源：yfinance
        hist = await self._fetch_yfinance_history(normalized, period)
        attempted_sources.append("yfinance")
        points = self._history_to_points(hist)
        if points and len(points) >= 2:
            result = HistoryData(
                symbol=normalized,
                days=normalized_days,
                range_key=range_key,
                data=points,
                source="yfinance",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(), self._get_dynamic_ttl(normalized, "history"))
            return result

        # 备用数据源：stooq
        stooq_result = await self._fetch_stooq_history(normalized, normalized_days, range_key=range_key)
        attempted_sources.append("stooq")
        if stooq_result and len(stooq_result.data) >= 2:
            self._set_cache(cache_key, stooq_result.model_dump(), self._get_dynamic_ttl(normalized, "history"))
            return stooq_result

        # 兜底数据源：alpha_vantage
        av_result = await self._fetch_alpha_vantage_history(normalized, normalized_days, range_key=range_key)
        attempted_sources.append("alpha_vantage")
        if av_result and len(av_result.data) >= 2:
            self._set_cache(cache_key, av_result.model_dump(), self._get_dynamic_ttl(normalized, "history"))
            return av_result

        # 所有数据源都失败
        return HistoryData(
            symbol=normalized,
            days=normalized_days,
            range_key=range_key,
            data=[],
            source=f"unavailable ({', '.join(attempted_sources)})",
            timestamp=self._utc_now(),
        )

    async def get_change(self, symbol: str, days: int = 7, range_key: Optional[str] = None) -> ChangeData:
        normalized = self.ticker_mapper.normalize(symbol)
        history = await self.get_history(normalized, days=days, range_key=range_key)
        if len(history.data) >= 2:
            start_price = history.data[0].close
            end_price = history.data[-1].close
            change_pct = ((end_price - start_price) / start_price) * 100 if start_price else 0.0
            if change_pct > 1:
                trend = TREND_UP
            elif change_pct < -1:
                trend = TREND_DOWN
            else:
                trend = TREND_FLAT
            return ChangeData(
                symbol=normalized,
                days=self._safe_days(days, default=7),
                start_price=start_price,
                end_price=end_price,
                change_pct=round(change_pct, 2),
                trend=trend,
                source=history.source,
                timestamp=self._utc_now(),
            )

        return ChangeData(
            symbol=normalized,
            days=days,
            start_price=0,
            end_price=0,
            change_pct=0,
            trend=TREND_FLAT,
            source="unavailable",
            timestamp=self._utc_now(),
        )

    async def get_info(self, symbol: str) -> CompanyInfo:
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"info:{normalized}"
        cached = self._get_cache(cache_key)
        if cached:
            return CompanyInfo(**cached)

        # Try Alpha Vantage first, then yfinance as fallback
        fallback = await self._fetch_alpha_vantage_info(normalized)
        if fallback:
            self._set_cache(cache_key, fallback.model_dump(by_alias=True), self._get_dynamic_ttl(normalized, "info"))
            return fallback

        info = await self._fetch_yfinance_info(normalized)
        if info:
            result = CompanyInfo(
                symbol=normalized,
                name=info.get("longName") or info.get("shortName") or normalized,
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=self._coerce_int(info.get("marketCap")),
                pe_ratio=self._coerce_float(info.get("trailingPE")),
                week_52_high=self._coerce_float(info.get("fiftyTwoWeekHigh")),
                week_52_low=self._coerce_float(info.get("fiftyTwoWeekLow")),
                description=(info.get("longBusinessSummary") or "")[:300],
                source="yfinance",
                timestamp=self._utc_now(),
            )
            self._set_cache(cache_key, result.model_dump(by_alias=True), self._get_dynamic_ttl(normalized, "info"))
            return result

        return CompanyInfo(symbol=normalized, name=normalized or symbol, source="unavailable", timestamp=self._utc_now())

    async def get_metrics(self, symbol: str, range_key: str = "1y") -> RiskMetrics:
        """计算风险指标：总收益、波动率、最大回撤、夏普比率。

        计算方法：
        - total_return: (终值 - 初值) / 初值 * 100
        - volatility: 日收益率标准差 * √252 * 100 (年化)
        - max_drawdown: 区间内最大的峰谷跌幅
        - sharpe_ratio: (年化收益率 - 4%) / 年化波动率
        """
        normalized = self.ticker_mapper.normalize(symbol)
        cache_key = f"metrics:{normalized}:{range_key}"
        cached = self._get_cache(cache_key)
        if cached:
            return RiskMetrics(**cached)

        # 获取历史数据
        history = await self.get_history(normalized, days=RANGE_TO_DAYS.get(range_key, 365), range_key=range_key)

        # 数据不足时返回错误
        if len(history.data) < 2:
            return RiskMetrics(
                symbol=normalized,
                range_key=range_key,
                source=history.source,
                timestamp=self._utc_now(),
                error=f"数据不足：仅获取到 {len(history.data)} 个数据点，至少需要 2 个",
            )

        # 提取收盘价
        closes = np.array([point.close for point in history.data], dtype=float)

        # 计算日收益率
        returns = np.diff(closes) / closes[:-1]
        if returns.size == 0:
            return RiskMetrics(
                symbol=normalized,
                range_key=range_key,
                source=history.source,
                timestamp=self._utc_now(),
                error="无法计算收益率",
            )

        # 1. 总收益率
        total_return = ((closes[-1] / closes[0]) - 1.0) * 100

        # 2. 年化波动率
        volatility = float(np.std(returns, ddof=1)) * math.sqrt(252) * 100 if returns.size > 1 else 0.0

        # 3. 最大回撤
        cumulative = np.cumprod(1.0 + returns)
        running_peak = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative / running_peak) - 1.0
        max_drawdown = float(drawdowns.min()) * 100 if drawdowns.size else 0.0

        # 4. 年化收益率
        trading_days = len(returns)
        if trading_days > 0:
            annualized_return = (float(np.prod(1.0 + returns)) ** (252 / trading_days) - 1.0) * 100
        else:
            annualized_return = 0.0

        # 5. 夏普比率（无风险利率假设为 4%）
        risk_free_rate = 4.0
        sharpe_ratio = ((annualized_return - risk_free_rate) / volatility) if volatility > 0 else None

        result = RiskMetrics(
            symbol=normalized,
            range_key=range_key,
            annualized_volatility=round(volatility, 2),
            total_return_pct=round(total_return, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            annualized_return_pct=round(annualized_return, 2),
            sharpe_ratio=round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
            source=history.source,
            timestamp=self._utc_now(),
        )

        self._set_cache(cache_key, result.model_dump(), self._get_dynamic_ttl(normalized, "history"))
        return result

    async def compare_assets(self, symbols: Sequence[str], range_key: str = "1y") -> ComparisonData:
        """对比多个资产的表现，返回价格、收益、波动率、最大回撤等指标。"""
        normalized_symbols = [self.ticker_mapper.normalize(symbol) for symbol in symbols[:4] if symbol]
        if not normalized_symbols:
            return ComparisonData(symbols=[], range_key=range_key, rows=[], chart=[], source="unavailable", timestamp=self._utc_now())

        # 并行获取价格、指标和历史数据
        prices_task = [self.get_price(symbol) for symbol in normalized_symbols]
        metrics_task = [self.get_metrics(symbol, range_key=range_key) for symbol in normalized_symbols]
        history_task = [
            self.get_history(symbol, days=RANGE_TO_DAYS.get(range_key, 365), range_key=range_key) for symbol in normalized_symbols
        ]
        prices, metrics, histories = await asyncio.gather(
            asyncio.gather(*prices_task),
            asyncio.gather(*metrics_task),
            asyncio.gather(*history_task),
        )

        # 构建对比表格
        rows: List[ComparisonRow] = []
        for symbol, price, metric in zip(normalized_symbols, prices, metrics):
            rows.append(
                ComparisonRow(
                    symbol=symbol,
                    name=price.name if price.name else symbol,
                    price=price.price if price.price is not None else None,
                    total_return_pct=metric.total_return_pct if metric.total_return_pct is not None else None,
                    annualized_volatility=metric.annualized_volatility if metric.annualized_volatility is not None else None,
                    max_drawdown_pct=metric.max_drawdown_pct if metric.max_drawdown_pct is not None else None,
                    source=f"{price.source}/{metric.source}",
                    timestamp=metric.timestamp,
                )
            )

        # 构建对比图表
        chart = self._build_comparison_chart(normalized_symbols, histories)
        sources = {history.source for history in histories if history.source and history.source != "unavailable"}
        return ComparisonData(
            symbols=normalized_symbols,
            range_key=range_key,
            rows=rows,
            chart=chart,
            source="/".join(sorted(sources)) if sources else "unavailable",
            timestamp=self._utc_now(),
        )

    def _build_comparison_chart(self, symbols: Sequence[str], histories: Sequence[HistoryData]) -> List[ComparisonPoint]:
        valid_histories = [history for history in histories if history.data]
        if not valid_histories:
            return []

        common_dates = set(point.date for point in valid_histories[0].data)
        for history in valid_histories[1:]:
            common_dates &= {point.date for point in history.data}
        if not common_dates:
            return []

        ordered_dates = sorted(common_dates)
        per_symbol: Dict[str, Dict[str, float]] = {}
        base_price: Dict[str, float] = {}
        for symbol, history in zip(symbols, histories):
            mapping = {point.date: point.close for point in history.data if point.date in common_dates}
            if not mapping:
                continue
            first_date = ordered_dates[0]
            if first_date not in mapping:
                continue
            per_symbol[symbol] = mapping
            base_price[symbol] = mapping[first_date]

        chart: List[ComparisonPoint] = []
        for trade_date in ordered_dates:
            values: Dict[str, float] = {}
            for symbol, mapping in per_symbol.items():
                base = base_price.get(symbol) or 0
                if trade_date in mapping and base:
                    values[symbol] = round(mapping[trade_date] / base * 100, 2)
            if values:
                chart.append(ComparisonPoint(date=trade_date, values=values))
        return chart

    async def get_market_overview(self) -> MarketOverviewResponse:
        # Fetch all indices and sectors via Finnhub in parallel (fast)
        all_coros = (
            [self._build_index_snapshot(s, n) for s, n in INDEX_WATCHLIST] +
            [self._build_sector_snapshot(s, n) for s, n in SECTOR_WATCHLIST]
        )
        results = await asyncio.gather(*all_coros, return_exceptions=True)

        index_payload = [r for r in results if isinstance(r, MarketIndexSnapshot)]
        sector_payload = [r for r in results if isinstance(r, SectorSnapshot)]

        signals = await self._build_market_signals()

        summary = self._build_market_summary(index_payload, signals, sector_payload)
        return MarketOverviewResponse(indices=index_payload, signals=signals, sectors=sector_payload, summary=summary)

    async def _get_quote_with_change(self, symbol: str) -> tuple[Optional[float], Optional[float]]:
        # First try finnhub if available
        quote = await self.finnhub_provider.get_quote(symbol)
        if quote and quote.get("c"):
            return quote.get("c"), quote.get("dp")
            
        # Fallback to history (gets latest 5 days)
        history = await self.get_history(symbol, days=5)
        if history and history.data and len(history.data) >= 1:
            current_price = history.data[-1].close
            change_pct = None
            if len(history.data) >= 2:
                prev_close = history.data[-2].close
                if prev_close and prev_close > 0:
                    change_pct = ((current_price - prev_close) / prev_close) * 100.0
            elif current_price and history.data[-1].open:
                open_price = history.data[-1].open
                if open_price > 0:
                    change_pct = ((current_price - open_price) / open_price) * 100.0
            return current_price, change_pct
            
        # Last resort: just get price
        price_data = await self.get_price(symbol)
        if price_data and price_data.price:
            return price_data.price, None
            
        return None, None

    async def _build_index_snapshot(self, symbol: str, display_name: str) -> MarketIndexSnapshot:
        price, change_pct = await self._get_quote_with_change(symbol)
        return MarketIndexSnapshot(
            symbol=symbol,
            name=display_name,
            price=price,
            change_pct=change_pct,
            source="mixed",
            timestamp=self._utc_now(),
        )

    async def _build_sector_snapshot(self, symbol: str, display_name: str) -> SectorSnapshot:
        _, change_pct = await self._get_quote_with_change(symbol)
        return SectorSnapshot(
            name=display_name,
            symbol=symbol,
            change_pct=change_pct,
            source="mixed",
            timestamp=self._utc_now(),
        )

    async def _build_market_signals(self) -> List[MarketSignal]:
        candidates = get_popular_stocks(limit=10)
        # Fetch prices with history fallback
        quotes = await asyncio.gather(*[self._get_quote_with_change(s) for s in candidates])
        signals: List[MarketSignal] = []
        for symbol, (price, change_pct) in zip(candidates, quotes):
            if price is None:
                continue
            change_pct = change_pct if change_pct is not None else 0.0
            signal_type = "price_spike"
            score = min(99, int(abs(change_pct) * 10))
            if score < 5:
                continue
            signals.append(
                MarketSignal(
                    symbol=TickerMapper.normalize(symbol),
                    change_pct=round(change_pct, 2),
                    signal_type=signal_type,
                    signal_score=score,
                    volume_ratio=1.0,
                    source="finnhub",
                    timestamp=self._utc_now(),
                )
            )
        signals.sort(key=lambda item: item.signal_score, reverse=True)
        return signals[:5]

    def _build_market_summary(
        self,
        indices: Iterable[MarketIndexSnapshot],
        signals: Iterable[MarketSignal],
        sectors: Iterable[SectorSnapshot],
    ) -> MarketSummary:
        indices = list(indices)
        signals = list(signals)
        sectors = list(sectors)

        leader = max(sectors, key=lambda item: item.change_pct, default=None)
        laggard = min(sectors, key=lambda item: item.change_pct, default=None)
        strongest_index = max(indices, key=lambda item: item.change_pct or -999, default=None)
        hottest_signal = signals[0] if signals else None

        parts: List[str] = []
        if strongest_index and strongest_index.change_pct is not None:
            parts.append(f"{strongest_index.name} 近5日变动 {strongest_index.change_pct:+.2f}%。")
        if leader and laggard:
            parts.append(f"板块表现方面，{leader.name} 领先 {leader.change_pct:+.2f}%，{laggard.name} 相对偏弱 {laggard.change_pct:+.2f}%。")
        if hottest_signal:
            parts.append(
                f"个股信号中 {hottest_signal.symbol} 最活跃，区间涨跌 {hottest_signal.change_pct:+.2f}%，信号分 {hottest_signal.signal_score}。"
            )

        available = sum(1 for item in indices if item.price is not None)
        confidence = "高" if available >= 4 else "中" if available >= 2 else "低"
        text = " ".join(parts) if parts else "当前可用的市场数据有限，建议稍后刷新。"
        return MarketSummary(text=text, confidence=confidence)

    async def get_news(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get news articles for a stock symbol. Combines results from both Finnhub and NewsAPI."""
        start_time = datetime.utcnow()
        normalized = self.ticker_mapper.normalize(symbol)
        if not normalized:
            return []

        cache_key = f"news:{normalized}:{days}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        # Call both APIs in parallel
        finnhub_task = self.finnhub_provider.get_news(normalized, from_date=from_str, to_date=to_str)
        newsapi_task = self.news_provider.get_stock_news(normalized, days=days, page_size=10)

        finnhub_news, newsapi_news = await asyncio.gather(finnhub_task, newsapi_task, return_exceptions=True)

        all_news = []

        # Process Finnhub news
        if finnhub_news and not isinstance(finnhub_news, Exception):
            for article in finnhub_news[:10]:  # Limit to 10 articles
                all_news.append({
                    "title": article.get("headline"),
                    "description": article.get("summary"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "published_at": datetime.fromtimestamp(article.get("datetime", 0)).isoformat() if article.get("datetime") else None,
                    "author": None,
                    "image_url": article.get("image"),
                    "provider": "finnhub"
                })

        # Process NewsAPI news
        if newsapi_news and not isinstance(newsapi_news, Exception):
            for article in newsapi_news:
                article["provider"] = "newsapi"
                all_news.append(article)

        # Sort by published date (newest first)
        all_news.sort(key=lambda x: x.get("published_at") or "", reverse=True)

        # Cache based on market status
        if all_news:
            self._set_cache(cache_key, all_news, ttl=self._get_dynamic_ttl(normalized, "news"))

        return all_news

    def check_cache(self) -> bool:
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False
