# Financial Intelligence Agent - 实施计划

**项目名称**: Financial Asset QA System → Financial Intelligence Agent
**计划日期**: 2024-03-06
**计划版本**: 1.0
**预计工期**: 10 周
**负责人**: Benjamin Daoson

---

## 一、项目概述

### 1.1 项目目标

将 Financial Asset QA System 从"普通 RAG Agent"升级为"Financial Intelligence Agent"，实现从"问答系统"到"金融决策智能系统"的战略转型。

### 1.2 核心交付物

1. **后端系统**
   - 升级的 AgentCore
   - 新增 Reasoning Layer（8个模块）
   - 升级的 Market Service（技术指标）
   - 完善的测试（覆盖率 > 90%）

2. **前端系统**
   - 场景化入口
   - 结构化展示
   - 新增 10+ 组件

3. **文档**
   - 架构设计文档 ✅
   - 实施计划文档（本文档）
   - API 文档
   - 用户手册

### 1.3 成功标准

**技术指标**:
- 快速模式响应时间 < 2s
- 深度模式响应时间 < 5s
- 测试覆盖率 > 90%
- 系统可用性 > 99%

**产品指标**:
- 首次提问率 > 60%
- 平均提问次数 > 3次/天
- 用户满意度 > 4/5

---

## 二、详细任务分解

### 阶段一：核心架构搭建（Week 1-2）

#### Week 1: 基础架构

**Day 1-2: 创建新模块结构**

```bash
# 任务清单
□ 创建 backend/app/reasoning/ 目录
□ 创建 8 个新模块文件
  - query_router.py
  - data_integrator.py
  - fast_analyzer.py
  - deep_analyzer.py
  - decision_engine.py
  - risk_assessor.py
  - verifier.py
  - response_generator.py
□ 创建 backend/app/market/indicators.py
□ 更新 __init__.py 文件
□ 创建测试文件结构
```

**验收标准**:
- ✅ 所有模块文件创建完成
- ✅ 导入路径正确
- ✅ 基础类定义完成

**Day 3-4: 实现 Query Router**

```python
# backend/app/reasoning/query_router.py

class QueryClassifier:
    """查询分类器"""

    async def classify(self, query: str) -> IntentResult:
        """
        使用 Haiku 快速分类
        支持多意图识别
        """
        # 实现逻辑
        pass

class ModeSelector:
    """模式选择器"""

    async def select_mode(
        self,
        query: str,
        intent: IntentResult,
        user_preference: Optional[str] = None
    ) -> str:
        """选择 FAST 或 DEEP 模式"""
        # 实现逻辑
        pass

class EntityExtractor:
    """实体提取器"""

    async def extract(self, query: str) -> List[Entity]:
        """提取股票代码、公司名称等"""
        # 实现逻辑
        pass
```

**测试**:
```python
# backend/tests/test_query_router.py

@pytest.mark.asyncio
async def test_query_classifier():
    classifier = QueryClassifier()

    # 测试市场查询
    result = await classifier.classify("阿里巴巴股价多少？")
    assert "MARKET_QUERY" in result.types

    # 测试知识查询
    result = await classifier.classify("什么是市盈率？")
    assert "KNOWLEDGE_QUERY" in result.types

    # 测试分析查询
    result = await classifier.classify("阿里巴巴现在能买吗？")
    assert "ANALYSIS_QUERY" in result.types
```

**验收标准**:
- ✅ 查询分类准确率 > 90%
- ✅ 模式选择逻辑正确
- ✅ 实体提取准确
- ✅ 测试覆盖率 > 80%

**Day 5: 实现 Data Integrator**

```python
# backend/app/reasoning/data_integrator.py

class DataIntegrator:
    """数据整合器：并行收集多个数据源"""

    async def collect_all(
        self,
        symbol: str,
        intent: IntentResult,
        mode: str
    ) -> DataCollection:
        """
        并行收集数据
        FAST 模式：价格 + 7日历史 + 基础指标
        DEEP 模式：价格 + 30日历史 + 完整指标 + 新闻 + 知识库
        """

        tasks = []

        # 必选：实时价格
        tasks.append(self.market_service.get_price(symbol))

        # 必选：历史数据
        days = 7 if mode == "FAST" else 30
        tasks.append(self.market_service.get_history(symbol, days))

        # 可选：基本面数据（仅 DEEP 模式）
        if mode == "DEEP":
            tasks.append(self.market_service.get_info(symbol))

        # 可选：新闻搜索
        if "NEWS_QUERY" in intent.types:
            tasks.append(self.search_service.search(f"{symbol} news"))

        # 可选：知识库检索
        if "KNOWLEDGE_QUERY" in intent.types:
            tasks.append(self.rag_pipeline.search(query))

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return DataCollection(results)
```

**测试**:
```python
@pytest.mark.asyncio
async def test_data_integrator_fast_mode():
    integrator = DataIntegrator()

    intent = IntentResult(types=["MARKET_QUERY"])
    data = await integrator.collect_all("BABA", intent, "FAST")

    assert data.price is not None
    assert len(data.history) == 7
    assert data.info is None  # FAST 模式不包含

@pytest.mark.asyncio
async def test_data_integrator_deep_mode():
    integrator = DataIntegrator()

    intent = IntentResult(types=["ANALYSIS_QUERY"])
    data = await integrator.collect_all("BABA", intent, "DEEP")

    assert data.price is not None
    assert len(data.history) == 30
    assert data.info is not None  # DEEP 模式包含
```

**验收标准**:
- ✅ 并行执行正常
- ✅ FAST 模式响应时间 < 1s
- ✅ DEEP 模式响应时间 < 2s
- ✅ 错误处理完善

#### Week 2: 升级 AgentCore

**Day 1-2: 升级 AgentCore**

```python
# backend/app/agent/core.py

class AgentCore:
    """升级的 Agent 核心"""

    def __init__(self):
        # 原有组件
        self.model_manager = model_manager
        self.market_service = MarketDataService()
        self.rag_pipeline = HybridRAGPipeline()
        self.search_service = WebSearchService()

        # 新增组件
        self.query_router = QueryRouter()
        self.data_integrator = DataIntegrator()
        self.fast_analyzer = FastAnalyzer()
        self.deep_analyzer = DeepAnalyzer()
        self.decision_engine = DecisionEngine()
        self.risk_assessor = RiskAssessor()
        self.verifier = Verifier()
        self.response_generator = ResponseGenerator()

    async def process_query(
        self,
        query: str,
        session_id: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        新的查询处理流程：
        1. 意图识别
        2. 数据收集（并行）
        3. 分析（FAST/DEEP）
        4. 决策建议
        5. 风险评估
        6. 验证
        7. 生成响应
        """

        # 1. 意图识别
        intent = await self.query_router.classify(query)
        mode = await self.query_router.select_mode(query, intent)
        entities = await self.query_router.extract_entities(query)

        yield SSEEvent(type="intent", data={
            "intent": intent.types,
            "mode": mode,
            "entities": entities
        })

        # 2. 数据收集
        symbol = entities[0].symbol if entities else None
        data = await self.data_integrator.collect_all(symbol, intent, mode)

        yield SSEEvent(type="data_collected", data={
            "symbol": symbol,
            "data_types": list(data.keys())
        })

        # 3. 分析
        if mode == "FAST":
            analysis = await self.fast_analyzer.analyze(data)
        else:
            analysis = await self.deep_analyzer.analyze(data)

        yield SSEEvent(type="analysis_complete", data={
            "mode": mode,
            "response_time": analysis.response_time
        })

        # 4. 决策建议
        decision = await self.decision_engine.generate(analysis, mode)

        # 5. 风险评估
        risks = await self.risk_assessor.assess(analysis, data)

        # 6. 验证
        verification = await self.verifier.verify(data)
        sources = self.verifier.track_sources(data)

        # 7. 生成响应
        response = await self.response_generator.generate(
            query=query,
            analysis=analysis,
            decision=decision,
            risks=risks,
            sources=sources,
            mode=mode
        )

        # 流式返回
        for section in response.sections:
            yield SSEEvent(type="section", data=section)

        yield SSEEvent(type="done", data={
            "request_id": session_id,
            "response_time": analysis.response_time
        })
```

**验收标准**:
- ✅ 新流程运行正常
- ✅ 向后兼容（旧功能不受影响）
- ✅ 测试覆盖率 > 85%

**Day 3-5: 集成测试**

```python
# backend/tests/test_agent_integration.py

@pytest.mark.asyncio
async def test_full_pipeline_fast_mode():
    """测试完整流程：快速模式"""
    agent = AgentCore()

    query = "阿里巴巴股价多少？"
    events = []

    async for event in agent.process_query(query, "test-session"):
        events.append(event)

    # 验证事件顺序
    assert events[0].type == "intent"
    assert events[1].type == "data_collected"
    assert events[2].type == "analysis_complete"
    assert events[-1].type == "done"

    # 验证响应时间
    done_event = events[-1]
    assert float(done_event.data["response_time"].rstrip("s")) < 2.0

@pytest.mark.asyncio
async def test_full_pipeline_deep_mode():
    """测试完整流程：深度模式"""
    agent = AgentCore()

    query = "阿里巴巴现在能买吗？"
    events = []

    async for event in agent.process_query(query, "test-session"):
        events.append(event)

    # 验证深度分析
    analysis_event = next(e for e in events if e.type == "analysis_complete")
    assert analysis_event.data["mode"] == "DEEP"

    # 验证响应时间
    done_event = events[-1]
    assert float(done_event.data["response_time"].rstrip("s")) < 5.0
```

**验收标准**:
- ✅ 端到端测试通过
- ✅ 快速模式 < 2s
- ✅ 深度模式 < 5s
- ✅ 无内存泄漏

---

### 阶段二：快速分析模式（Week 3-4）

#### Week 3: 实现 Fast Analyzer

**Day 1-2: Signal Detector**

```python
# backend/app/reasoning/fast_analyzer.py

class SignalDetector:
    """技术信号识别器"""

    def detect(self, history: List[PricePoint]) -> TechnicalSignals:
        """
        识别技术信号：
        - RSI 超买/超卖
        - MACD 金叉/死叉
        - 趋势反转
        """

        # 计算 RSI
        rsi = self._calculate_rsi(history, period=14)

        # 计算 MACD
        macd, signal, histogram = self._calculate_macd(history)

        # 识别信号
        signals = TechnicalSignals(
            rsi=rsi,
            rsi_signal="超卖" if rsi < 30 else "超买" if rsi > 70 else "正常",
            macd=macd,
            macd_signal="金叉" if self._is_golden_cross(macd, signal) else "死叉" if self._is_death_cross(macd, signal) else "正常"
        )

        return signals

    def _calculate_rsi(self, history: List[PricePoint], period: int = 14) -> float:
        """计算 RSI 指标"""
        # 实现 RSI 计算
        pass

    def _calculate_macd(
        self,
        history: List[PricePoint],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[float, float, float]:
        """计算 MACD 指标"""
        # 实现 MACD 计算
        pass
```

**测试**:
```python
@pytest.mark.asyncio
async def test_signal_detector():
    detector = SignalDetector()

    # 模拟历史数据
    history = generate_mock_history(days=30)

    signals = detector.detect(history)

    assert 0 <= signals.rsi <= 100
    assert signals.rsi_signal in ["超卖", "超买", "正常"]
    assert signals.macd_signal in ["金叉", "死叉", "正常"]
```

**Day 3: Trend Analyzer**

```python
class TrendAnalyzer:
    """趋势分析器"""

    def analyze(self, history: List[PricePoint]) -> TrendAnalysis:
        """
        分析趋势：
        - 7日涨跌幅
        - 趋势方向（上涨/下跌/震荡）
        - 趋势强度
        """

        # 计算涨跌幅
        change_7d = self._calculate_change(history, days=7)
        change_30d = self._calculate_change(history, days=30)

        # 判断趋势
        if change_7d > 5:
            trend = "强势上涨"
        elif change_7d < -5:
            trend = "强势下跌"
        else:
            trend = "震荡整理"

        return TrendAnalysis(
            change_7d=change_7d,
            change_30d=change_30d,
            trend=trend,
            strength=abs(change_7d)
        )
```

**Day 4-5: Quick Reasoner + 集成**

```python
class FastAnalyzer:
    """快速分析器：1-2秒响应"""

    def __init__(self):
        self.signal_detector = SignalDetector()
        self.trend_analyzer = TrendAnalyzer()
        self.quick_reasoner = QuickReasoner()

    async def analyze(self, data: DataCollection) -> FastAnalysisResult:
        """快速分析流程"""

        start_time = time.time()

        # 1. 技术信号
        signals = self.signal_detector.detect(data.history)

        # 2. 趋势判断
        trend = self.trend_analyzer.analyze(data.history)

        # 3. 关键事件（如果有）
        key_events = []
        if data.news:
            key_events = self._extract_key_events(data.news, top_k=2)

        # 4. 快速推理（使用 Haiku）
        reasoning = await self.quick_reasoner.reason(
            signals=signals,
            trend=trend,
            events=key_events
        )

        response_time = f"{time.time() - start_time:.1f}s"

        return FastAnalysisResult(
            signals=signals,
            trend=trend,
            key_events=key_events,
            reasoning=reasoning,
            response_time=response_time
        )
```

**验收标准**:
- ✅ 技术指标计算准确
- ✅ 趋势判断合理
- ✅ 响应时间 < 2s
- ✅ 测试覆盖率 > 85%

#### Week 4: Decision Engine + Response Generator

**Day 1-2: Decision Engine**

```python
# backend/app/reasoning/decision_engine.py

class DecisionEngine:
    """决策引擎"""

    async def generate(
        self,
        analysis: Union[FastAnalysisResult, DeepAnalysisResult],
        mode: str
    ) -> DecisionResult:
        """生成决策建议"""

        if mode == "FAST":
            return await self._generate_fast_decision(analysis)
        else:
            return await self._generate_deep_decision(analysis)

    async def _generate_fast_decision(
        self,
        analysis: FastAnalysisResult
    ) -> DecisionResult:
        """
        快速决策建议：
        - 交易信号
        - 仓位建议
        - 止损位、止盈位
        """

        # 基于技术信号生成建议
        if analysis.signals.rsi < 30 and analysis.trend.trend == "强势下跌":
            signal = "短线反弹机会"
            position = "轻仓试探"
            rationale = "技术面超卖，可能出现反弹"
        elif analysis.signals.rsi > 70 and analysis.trend.trend == "强势上涨":
            signal = "短期超买"
            position = "建议观望或减仓"
            rationale = "技术面超买，注意回调风险"
        else:
            signal = "震荡整理"
            position = "观望为主"
            rationale = "趋势不明确，等待信号"

        return DecisionResult(
            signal=signal,
            position=position,
            rationale=rationale,
            stop_loss=self._calculate_stop_loss(analysis),
            take_profit=self._calculate_take_profit(analysis)
        )
```

**Day 3-4: Response Generator**

```python
# backend/app/reasoning/response_generator.py

class ResponseGenerator:
    """响应生成器"""

    async def generate(
        self,
        query: str,
        analysis: Union[FastAnalysisResult, DeepAnalysisResult],
        decision: DecisionResult,
        risks: RiskAssessment,
        sources: List[Source],
        mode: str
    ) -> StructuredResponse:
        """生成结构化响应"""

        if mode == "FAST":
            return await self._generate_fast_response(
                query, analysis, decision, risks, sources
            )
        else:
            return await self._generate_deep_response(
                query, analysis, decision, risks, sources
            )

    async def _generate_fast_response(
        self,
        query: str,
        analysis: FastAnalysisResult,
        decision: DecisionResult,
        risks: RiskAssessment,
        sources: List[Source]
    ) -> StructuredResponse:
        """快速模式响应"""

        sections = [
            Section(
                type="DATA_SUMMARY",
                title="📊 数据摘要",
                content=self._format_data_summary(analysis)
            ),
            Section(
                type="SIGNAL_ANALYSIS",
                title="📈 技术信号",
                content=self._format_signals(analysis.signals)
            ),
            Section(
                type="TREND_ANALYSIS",
                title="📊 趋势判断",
                content=self._format_trend(analysis.trend)
            ),
            Section(
                type="DECISION",
                title="💡 交易建议",
                content=self._format_decision(decision)
            ),
            Section(
                type="RISK_WARNING",
                title="⚠️ 风险提示",
                content=self._format_risks(risks)
            ),
            Section(
                type="SOURCES",
                title="📌 数据来源",
                content=self._format_sources(sources)
            ),
            Section(
                type="DISCLAIMER",
                title="⚠️ 免责声明",
                content="以上内容仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
            )
        ]

        return StructuredResponse(
            sections=sections,
            response_time=analysis.response_time
        )
```

**Day 5: 前端场景化入口**

```jsx
// frontend/src/components/ScenarioEntrance.jsx

const ScenarioEntrance = () => {
  return (
    <div className="scenario-entrance">
      {/* 全球市场概览 */}
      <MarketOverview />

      {/* 热门资产 */}
      <HotAssets />

      {/* 快捷问题 */}
      <QuickQuestions />
    </div>
  );
};

// frontend/src/components/MarketOverview.jsx
const MarketOverview = () => {
  const [markets, setMarkets] = useState([]);

  useEffect(() => {
    // 获取市场数据
    fetchMarketData().then(setMarkets);
  }, []);

  return (
    <section className="market-overview">
      <h3>🌍 全球市场概览</h3>
      <div className="market-grid">
        {markets.map(market => (
          <MarketCard key={market.symbol} data={market} />
        ))}
      </div>
    </section>
  );
};

// frontend/src/components/HotAssets.jsx
const HotAssets = ({ onQuickQuestion }) => {
  const hotAssets = [
    { symbol: "NVDA", name: "英伟达", price: 850, change: 3.2 },
    { symbol: "TSLA", name: "特斯拉", price: 185, change: 8.4 },
    { symbol: "BABA", name: "阿里巴巴", price: 89.52, change: -2.3 }
  ];

  return (
    <section className="hot-assets">
      <h3>🔥 热门资产</h3>
      {hotAssets.map(asset => (
        <div key={asset.symbol} className="asset-card">
          <div className="asset-info">
            <span className="symbol">{asset.symbol}</span>
            <span className="name">{asset.name}</span>
            <span className="price">${asset.price}</span>
            <span className={`change ${asset.change > 0 ? 'positive' : 'negative'}`}>
              {asset.change > 0 ? '+' : ''}{asset.change}%
            </span>
          </div>
          <div className="quick-actions">
            <button onClick={() => onQuickQuestion(`${asset.name}为什么${asset.change > 0 ? '上涨' : '下跌'}？`)}>
              💬 为什么{asset.change > 0 ? '上涨' : '下跌'}？
            </button>
            <button onClick={() => onQuickQuestion(`${asset.name}现在能买吗？`)}>
              💬 现在能买吗？
            </button>
          </div>
        </div>
      ))}
    </section>
  );
};
```

**验收标准**:
- ✅ 决策建议合理
- ✅ 响应结构清晰
- ✅ 前端场景化入口可用
- ✅ 端到端测试通过

---

// __CONTINUE_HERE__
