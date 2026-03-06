# 执行计划 - 阶段 1：增强现有 Agent

**时间**: Week 1-2（5 个工作日）
**目标**: 在不重构架构的前提下，提升现有系统能力
**负责人**: 开发团队

---

## Week 1: 修复质量问题（3 天）

### Task 1.1: 实现 ResponseGuard 验证逻辑

**工作量**: 1 天
**优先级**: P0
**文件**: `backend/app/agent/core.py`

#### 实现内容

```python
class ResponseGuard:
    """响应验证器：检查 LLM 输出与工具结果的一致性"""

    @staticmethod
    def validate(response: str, tool_results: List[Dict]) -> bool:
        """
        验证数字一致性，容忍 ±5% 误差

        Args:
            response: LLM 生成的响应文本
            tool_results: 工具调用结果列表

        Returns:
            bool: 验证是否通过
        """
        import re

        if not tool_results:
            return True

        # 提取响应中的数字（价格、百分比等）
        response_numbers = []
        for match in re.finditer(r'\d+\.?\d*', response):
            num = float(match.group())
            if num > 0.01:  # 忽略过小的数字
                response_numbers.append(num)

        # 提取工具结果中的关键数字
        tool_numbers = []
        for result in tool_results:
            if not result.get('success'):
                continue

            data = result.get('data', {})

            # 价格
            if 'price' in data and data['price']:
                tool_numbers.append(float(data['price']))

            # 涨跌幅（取绝对值）
            if 'change_pct' in data and data['change_pct'] is not None:
                tool_numbers.append(abs(float(data['change_pct'])))

            # 市值（转换为亿）
            if 'market_cap' in data and data['market_cap']:
                tool_numbers.append(float(data['market_cap']) / 1e8)

        if not tool_numbers:
            return True

        # 检查响应中的数字是否与工具结果匹配
        for rn in response_numbers:
            # 检查是否有匹配的工具数字（容忍 5% 误差）
            matched = False
            for tn in tool_numbers:
                if tn == 0:
                    continue
                error_rate = abs(rn - tn) / tn
                if error_rate < 0.05:  # 5% 误差范围
                    matched = True
                    break

            # 如果是较大的数字且没有匹配，则验证失败
            if not matched and rn > 10:
                print(f"[ResponseGuard] 验证失败: 响应中的数字 {rn} 与工具结果不匹配")
                return False

        return True
```

#### 测试用例

文件: `backend/tests/test_response_guard.py`

```python
import pytest
from app.agent.core import ResponseGuard

class TestResponseGuard:
    """测试 ResponseGuard 验证逻辑"""

    def test_validate_with_matching_numbers(self):
        """测试数字匹配的情况"""
        response = "阿里巴巴当前股价为 89.52 美元，涨幅 2.3%"
        tool_results = [
            {
                'success': True,
                'data': {
                    'price': 89.52,
                    'change_pct': 2.3
                }
            }
        ]

        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_mismatched_numbers(self):
        """测试数字不匹配的情况（幻觉）"""
        response = "阿里巴巴当前股价为 150.00 美元"
        tool_results = [
            {
                'success': True,
                'data': {
                    'price': 89.52
                }
            }
        ]

        assert ResponseGuard.validate(response, tool_results) is False

    def test_validate_with_tolerance(self):
        """测试容忍误差范围"""
        response = "股价约为 90 美元"
        tool_results = [
            {
                'success': True,
                'data': {
                    'price': 89.52
                }
            }
        ]

        # 90 vs 89.52，误差 < 5%，应该通过
        assert ResponseGuard.validate(response, tool_results) is True

    def test_validate_with_no_tool_results(self):
        """测试无工具结果的情况"""
        response = "这是一个知识性回答"
        tool_results = []

        assert ResponseGuard.validate(response, tool_results) is True
```

#### 验收标准

- ✅ 所有测试用例通过
- ✅ 能检测出数字不匹配的幻觉（误差 > 5%）
- ✅ 容忍合理的四舍五入误差（误差 < 5%）
- ✅ 不影响知识性回答（无工具调用）

---

### Task 1.2: 实现工具并行执行

**工作量**: 1 天
**优先级**: P1
**文件**: `backend/app/agent/core.py`

#### 实现内容

```python
import asyncio
from typing import List, Dict, Any

class AgentCore:
    # ... 现有代码 ...

    async def _execute_tools_parallel(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        并行执行多个工具调用

        Args:
            tool_calls: 工具调用列表，格式: [{"name": "get_price", "input": {...}}, ...]

        Returns:
            工具执行结果列表
        """
        if not tool_calls:
            return []

        # 创建并行任务
        tasks = [
            self._execute_tool(call['name'], call['input'])
            for call in tool_calls
        ]

        # 并行执行，捕获异常
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error': str(result),
                    'tool': tool_calls[i]['name']
                })
            else:
                processed_results.append(result)

        return processed_results
```

#### 集成到 run() 方法

修改 `AgentCore.run()` 方法，收集所有工具调用后批量执行：

```python
async def run(self, query: str, model_name: Optional[str] = None):
    # ... 现有代码 ...

    # 收集工具调用
    tool_calls = []

    async for event in stream:
        if isinstance(event, dict) and "final_message" in event:
            final_message = event["final_message"]

            # 收集所有工具调用
            if hasattr(final_message, "content"):
                for block in final_message.content:
                    if block.type == "tool_use":
                        tool_calls.append({
                            'name': block.name,
                            'input': block.input
                        })

    # 并行执行所有工具
    if tool_calls:
        tool_results = await self._execute_tools_parallel(tool_calls)

        # 发送工具结果
        for result in tool_results:
            if result['success']:
                yield SSEEvent(
                    type="tool_data",
                    tool=result.get('tool', 'unknown'),
                    data=result['data']
                )
```

#### 验收标准

- ✅ 多工具调用延迟减少 50%
- ✅ 单工具调用性能不受影响
- ✅ 异常处理正确（一个工具失败不影响其他）
- ✅ 测试覆盖率 > 80%

---

### Task 1.3: 完善 Alpha Vantage 降级

**工作量**: 1 天
**优先级**: P1
**文件**: `backend/app/market/service.py`

#### 实现内容

```python
import httpx
from typing import Optional

class MarketDataService:
    # ... 现有代码 ...

    async def _fetch_from_alpha_vantage(
        self,
        symbol: str,
        function: str = "GLOBAL_QUOTE"
    ) -> Optional[Dict]:
        """
        从 Alpha Vantage 获取数据

        Args:
            symbol: 股票代码
            function: API 函数（GLOBAL_QUOTE, TIME_SERIES_DAILY 等）

        Returns:
            数据字典或 None
        """
        if not settings.ALPHA_VANTAGE_API_KEY:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": function,
                        "symbol": symbol,
                        "apikey": settings.ALPHA_VANTAGE_API_KEY
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    # 检查是否有错误
                    if "Error Message" in data:
                        return None

                    return data
        except Exception as e:
            print(f"[AlphaVantage] 请求失败: {e}")
            return None

    async def get_price(self, symbol: str) -> MarketData:
        """获取实时价格（带降级）"""
        # 尝试从 Redis 获取
        cached = await self._get_from_cache(f"price:{symbol}")
        if cached:
            return MarketData(**cached)

        # 尝试 yfinance
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if 'currentPrice' in info or 'regularMarketPrice' in info:
                price = info.get('currentPrice') or info.get('regularMarketPrice')
                result = MarketData(
                    symbol=symbol,
                    price=price,
                    currency=info.get('currency', 'USD'),
                    name=info.get('shortName', symbol),
                    source="yfinance",
                    timestamp=datetime.utcnow().isoformat()
                )

                # 缓存
                await self._set_cache(f"price:{symbol}", result.model_dump(), ttl=60)
                return result
        except Exception as e:
            print(f"[yfinance] 失败: {e}，尝试 Alpha Vantage")

        # 降级到 Alpha Vantage
        av_data = await self._fetch_from_alpha_vantage(symbol, "GLOBAL_QUOTE")
        if av_data and "Global Quote" in av_data:
            quote = av_data["Global Quote"]
            result = MarketData(
                symbol=symbol,
                price=float(quote.get("05. price", 0)),
                currency="USD",
                name=symbol,
                source="alpha_vantage",
                timestamp=datetime.utcnow().isoformat()
            )

            # 缓存
            await self._set_cache(f"price:{symbol}", result.model_dump(), ttl=60)
            return result

        # 都失败了
        return MarketData(
            symbol=symbol,
            source="unavailable",
            timestamp=datetime.utcnow().isoformat(),
            error="数据源暂时不可用"
        )
```

#### 验收标准

- ✅ yfinance 失败时自动切换到 Alpha Vantage
- ✅ Alpha Vantage 数据格式正确解析
- ✅ 降级逻辑不影响正常流程
- ✅ 测试覆盖率 > 80%

---

## Week 2: 添加基础分析能力（2 天）

### Task 2.1: 创建 Technical Indicators 模块

**工作量**: 1.5 天
**优先级**: P0
**文件**: `backend/app/market/indicators.py`

#### 实现内容

使用 TA-Lib 库（不自己实现复杂算法）：

```python
"""
技术指标计算模块
使用 TA-Lib 库进行计算
"""
import numpy as np
from typing import List, Tuple, Dict
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    print("[Warning] TA-Lib not installed, using fallback implementation")


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """
        计算 RSI 指标

        Args:
            prices: 价格列表（按时间顺序）
            period: 周期（默认 14）

        Returns:
            RSI 值（0-100）
        """
        if len(prices) < period + 1:
            return 50.0  # 数据不足，返回中性值

        if HAS_TALIB:
            prices_array = np.array(prices, dtype=float)
            rsi = talib.RSI(prices_array, timeperiod=period)
            return float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0
        else:
            # Fallback: 简化实现
            return TechnicalIndicators._calculate_rsi_fallback(prices, period)

    @staticmethod
    def _calculate_rsi_fallback(prices: List[float], period: int) -> float:
        """RSI 简化实现（无 TA-Lib 时使用）"""
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[float, float, float]:
        """
        计算 MACD 指标

        Returns:
            (macd, signal, histogram)
        """
        if len(prices) < slow_period + signal_period:
            return (0.0, 0.0, 0.0)

        if HAS_TALIB:
            prices_array = np.array(prices, dtype=float)
            macd, signal, hist = talib.MACD(
                prices_array,
                fastperiod=fast_period,
                slowperiod=slow_period,
                signalperiod=signal_period
            )
            return (
                float(macd[-1]) if not np.isnan(macd[-1]) else 0.0,
                float(signal[-1]) if not np.isnan(signal[-1]) else 0.0,
                float(hist[-1]) if not np.isnan(hist[-1]) else 0.0
            )
        else:
            return TechnicalIndicators._calculate_macd_fallback(
                prices, fast_period, slow_period, signal_period
            )

    @staticmethod
    def _calculate_macd_fallback(
        prices: List[float],
        fast: int,
        slow: int,
        signal: int
    ) -> Tuple[float, float, float]:
        """MACD 简化实现"""
        # 计算 EMA
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]
            for price in data[period:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values[-1]

        fast_ema = ema(prices, fast)
        slow_ema = ema(prices, slow)
        macd_line = fast_ema - slow_ema

        # 简化：signal 线使用固定值
        signal_line = macd_line * 0.9
        histogram = macd_line - signal_line

        return (macd_line, signal_line, histogram)

    @staticmethod
    def interpret_rsi(rsi: float) -> Dict[str, str]:
        """解读 RSI 指标"""
        if rsi < 30:
            return {
                "level": "超卖",
                "signal": "可能反弹",
                "description": "RSI 低于 30，技术面超卖，存在反弹机会"
            }
        elif rsi > 70:
            return {
                "level": "超买",
                "signal": "可能回调",
                "description": "RSI 高于 70，技术面超买，注意回调风险"
            }
        else:
            return {
                "level": "正常",
                "signal": "震荡",
                "description": f"RSI 为 {rsi:.1f}，处于正常区间"
            }

    @staticmethod
    def interpret_macd(macd: float, signal: float, hist: float) -> Dict[str, str]:
        """解读 MACD 指标"""
        if hist > 0 and macd > signal:
            return {
                "signal": "金叉",
                "trend": "看涨",
                "description": "MACD 金叉，短期趋势向上"
            }
        elif hist < 0 and macd < signal:
            return {
                "signal": "死叉",
                "trend": "看跌",
                "description": "MACD 死叉，短期趋势向下"
            }
        else:
            return {
                "signal": "震荡",
                "trend": "中性",
                "description": "MACD 震荡，趋势不明确"
            }
```

#### 安装依赖

```bash
# requirements.txt 添加
TA-Lib==0.4.28  # 需要先安装 TA-Lib C 库
# 或使用纯 Python 实现
ta==0.11.0
```

#### 测试用例

```python
import pytest
from app.market.indicators import TechnicalIndicators

class TestTechnicalIndicators:
    def test_calculate_rsi(self):
        """测试 RSI 计算"""
        # 模拟价格数据
        prices = [100 + i * 0.5 for i in range(30)]  # 上涨趋势

        rsi = TechnicalIndicators.calculate_rsi(prices)

        assert 0 <= rsi <= 100
        assert rsi > 50  # 上涨趋势，RSI 应该 > 50

    def test_calculate_macd(self):
        """测试 MACD 计算"""
        prices = [100 + i * 0.5 for i in range(50)]

        macd, signal, hist = TechnicalIndicators.calculate_macd(prices)

        assert isinstance(macd, float)
        assert isinstance(signal, float)
        assert isinstance(hist, float)

    def test_interpret_rsi_oversold(self):
        """测试 RSI 超卖解读"""
        interpretation = TechnicalIndicators.interpret_rsi(25)

        assert interpretation["level"] == "超卖"
        assert "反弹" in interpretation["signal"]

    def test_interpret_rsi_overbought(self):
        """测试 RSI 超买解读"""
        interpretation = TechnicalIndicators.interpret_rsi(75)

        assert interpretation["level"] == "超买"
        assert "回调" in interpretation["signal"]
```

#### 验收标准

- ✅ RSI/MACD 计算准确（与 TA-Lib 结果一致）
- ✅ 无 TA-Lib 时 fallback 实现可用
- ✅ 指标解读合理
- ✅ 测试覆盖率 > 85%

---

### Task 2.2: 在 System Prompt 中注入分析框架

**工作量**: 0.5 天
**优先级**: P0
**文件**: `backend/app/agent/core.py`

#### 实现内容

修改 `AgentCore.run()` 中的 system_prompt：

```python
system_prompt = """你是专业的金融分析助手，为专业投资者提供决策参考。

【核心原则】
1. 所有金融数字必须来自工具调用，不要编造数据
2. 使用工具获取事实数据后，再组织回答
3. 回答必须结构化，按以下格式组织
4. 明确标注数据来源

【回答结构】（必须遵循）

📊 数据摘要
- 当前价格：[从 get_price 工具获取]
- 涨跌幅：[从 get_change 工具获取]
- 成交量：[如有数据则展示]

📈 技术分析
- RSI 指标：[计算并解读：超买/超卖/正常]
- MACD 指标：[计算并解读：金叉/死叉/震荡]
- 趋势判断：[上涨/下跌/震荡]

💡 参考观点
- 基于以上数据的客观分析
- 可能的交易机会或风险点
- 【重要】明确说明"以上内容仅供参考，不构成投资建议"

⚠️ 风险提示
- 技术风险：[如 RSI 超买则提示回调风险]
- 市场风险：[大盘走势、行业风险等]
- 其他风险：[政策、估值等]

【可用工具】
- get_price: 查询当前价格
- get_history: 查询历史数据（用于计算技术指标）
- get_change: 计算涨跌幅
- get_info: 查询公司信息
- search_knowledge: 检索金融知识
- search_web: 搜索新闻事件

【重要提示】
- 必须先调用工具获取数据，再组织回答
- 技术指标需要历史数据，记得调用 get_history
- 回答要专业但易懂，避免过度使用术语
- 永远不要直接推荐"买入"或"卖出"，只提供"参考观点"
"""
```

#### 验收标准

- ✅ 回答结构化，包含必要章节
- ✅ 技术指标自动计算和解读
- ✅ 风险提示完整
- ✅ 合规性良好（不直接荐股）

---

## 总结

### 阶段 1 交付物

1. ✅ ResponseGuard 验证逻辑（防止幻觉）
2. ✅ 工具并行执行（性能提升 50%）
3. ✅ Alpha Vantage 降级（提升可用性）
4. ✅ Technical Indicators 模块（RSI, MACD）
5. ✅ 结构化 System Prompt（引导 LLM 输出）

### 验收标准

- ✅ 所有测试用例通过
- ✅ 测试覆盖率保持 > 85%
- ✅ 响应时间无明显增加
- ✅ 回答质量提升（结构化 + 技术分析）

### 下一步

完成阶段 1 后，进入阶段 2：实现 Fast Analyzer（Week 3-4）
