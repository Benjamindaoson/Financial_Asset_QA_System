# 金融数据 API 功能对比与调用策略

## 📊 各 API 功能对比

### 1. **Finnhub** (已集成)
- **主要功能**:
  - ✅ 实时股票报价
  - ✅ 公司资料
  - ✅ 专业金融新闻（大量）
  - ✅ 技术指标
- **优势**: 专业金融数据，新闻质量高
- **限制**: 60 请求/分钟
- **适用场景**: 新闻、公司信息、实时报价

### 2. **NewsAPI** (已集成)
- **主要功能**:
  - ✅ 广泛媒体新闻
  - ✅ 多来源聚合
- **优势**: 覆盖面广，来源多样
- **限制**: 100 请求/天
- **适用场景**: 补充新闻视角

### 3. **TwelveData** (待集成)
- **主要功能**:
  - ✅ 历史价格数据（OHLCV）
  - ✅ 技术指标（RSI, MACD, EMA等）
  - ✅ 实时报价
  - ✅ 外汇、加密货币
- **优势**: 技术分析数据丰富，支持多种资产类型
- **限制**: 免费版有限额度
- **适用场景**: 历史数据、技术分析、图表

### 4. **yfinance** (当前主力)
- **主要功能**:
  - ✅ 历史价格数据
  - ✅ 公司基本面
  - ✅ 财务报表
- **优势**: 免费无限制，数据全面
- **限制**: 非官方 API，可能不稳定
- **适用场景**: 主要数据源

## 🎯 调用策略设计

### 策略 1: 分层调用（推荐）

```
用户查询
    ↓
┌─────────────────────────────────────┐
│  第一层：基础数据（并行）            │
├─────────────────────────────────────┤
│  • yfinance: 价格、历史、基本面      │
│  • Finnhub: 实时报价、公司资料       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  第二层：增强数据（并行）            │
├─────────────────────────────────────┤
│  • Finnhub: 专业金融新闻             │
│  • NewsAPI: 广泛媒体新闻             │
│  • TwelveData: 技术指标（如需要）    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  第三层：AI 分析（流式）             │
├─────────────────────────────────────┤
│  • DeepSeek: 综合分析                │
└─────────────────────────────────────┘
```

### 策略 2: 按查询类型调用

#### 查询类型 A: 价格查询
```
"AAPL 今天价格"
→ yfinance (主) + Finnhub (辅助验证)
```

#### 查询类型 B: 历史走势
```
"AAPL 过去30天走势"
→ yfinance (主) + TwelveData (技术指标)
```

#### 查询类型 C: 新闻查询
```
"AAPL 最近新闻"
→ Finnhub (专业) + NewsAPI (广泛) 并行
```

#### 查询类型 D: 技术分析
```
"AAPL RSI 指标"
→ TwelveData (技术指标) + yfinance (历史数据)
```

#### 查询类型 E: 综合分析
```
"分析 AAPL"
→ 全部 API 并行调用
```

## 🔧 实现方案

### 方案 1: 智能路由（推荐）

```python
class DataSourceRouter:
    """根据查询类型智能选择数据源"""

    def route(self, query_type: str, symbols: List[str]):
        if query_type == "price":
            return {
                "primary": ["yfinance", "finnhub"],
                "news": [],
                "technical": []
            }
        elif query_type == "news":
            return {
                "primary": ["yfinance"],  # 基础数据
                "news": ["finnhub", "newsapi"],  # 并行新闻
                "technical": []
            }
        elif query_type == "technical":
            return {
                "primary": ["yfinance"],
                "news": [],
                "technical": ["twelvedata"]  # 技术指标
            }
        elif query_type == "comprehensive":
            return {
                "primary": ["yfinance", "finnhub"],
                "news": ["finnhub", "newsapi"],
                "technical": ["twelvedata"]
            }
```

### 方案 2: 容错降级

```python
async def get_price_with_fallback(symbol: str):
    """价格查询带降级"""
    # 1. 尝试 yfinance（主）
    price = await yfinance_get_price(symbol)
    if price:
        return price

    # 2. 降级到 Finnhub
    price = await finnhub_get_price(symbol)
    if price:
        return price

    # 3. 降级到 TwelveData
    price = await twelvedata_get_price(symbol)
    return price
```

### 方案 3: 数据融合

```python
async def get_comprehensive_data(symbol: str):
    """融合多个数据源"""

    # 并行调用
    yf_data, fh_data, td_data = await asyncio.gather(
        yfinance_get_data(symbol),
        finnhub_get_data(symbol),
        twelvedata_get_data(symbol),
        return_exceptions=True
    )

    # 融合数据
    return {
        "price": yf_data.price or fh_data.price or td_data.price,
        "volume": yf_data.volume or fh_data.volume,
        "technical": td_data.indicators,
        "fundamentals": yf_data.fundamentals,
        "news": fh_data.news
    }
```

## 📝 TwelveData 集成计划

### 1. 配置 API Key
```env
TWELVEDATA_API_KEY=3a3eaa9ecb454b28b9efccd4036646e6
```

### 2. 使用场景
- **技术指标**: RSI, MACD, EMA, SMA, Bollinger Bands
- **历史数据备份**: 当 yfinance 失败时
- **外汇和加密货币**: 扩展资产类型

### 3. 调用时机
- 用户明确要求技术指标时
- 需要更精确的历史数据时
- yfinance 数据不可用时（降级）

## 🎯 推荐的最终方案

### 核心原则
1. **yfinance 为主**: 免费无限制，作为主要数据源
2. **Finnhub 为辅**: 新闻 + 实时报价验证
3. **TwelveData 按需**: 技术指标 + 降级备份
4. **NewsAPI 补充**: 广泛新闻视角

### 执行流程
```
1. 解析查询 → 确定查询类型
2. 并行调用:
   - 基础数据: yfinance + Finnhub
   - 新闻数据: Finnhub + NewsAPI (如需要)
   - 技术指标: TwelveData (如需要)
3. 立即发送: 数据 + 新闻
4. 流式输出: DeepSeek AI 分析
```

### API 调用优先级
```
价格数据: yfinance > Finnhub > TwelveData
历史数据: yfinance > TwelveData
新闻数据: Finnhub + NewsAPI (并行)
技术指标: TwelveData > 自己计算
公司信息: yfinance > Finnhub
```

## ✅ 下一步实现

1. ✅ 配置 TwelveData API Key
2. ⬜ 实现 TwelveData 技术指标调用
3. ⬜ 实现智能路由逻辑
4. ⬜ 实现容错降级机制
5. ⬜ 添加 DeepSeek AI 分析
6. ⬜ 实现流式输出

---

**设计原则**:
- 并行优先（提升速度）
- 容错降级（提升可靠性）
- 按需调用（节省配额）
- 数据融合（提升准确性）
