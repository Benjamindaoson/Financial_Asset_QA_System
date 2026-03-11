# 代码质量检查 - 问题修复清单

**生成日期**: 2026-03-11
**项目**: Financial Asset QA System (Backend)

---

## 需要修复的问题

### P0 - 阻塞性问题（必须立即修复）

#### 问题1: 知识库路径错误

**文件**: `app/rag/pipeline.py`
**行号**: 172
**严重程度**: P0 - 阻塞性

**当前代码**:
```python
def _load_source_documents(self) -> List[Dict[str, Any]]:
    knowledge_dir = Path(__file__).resolve().parents[3] / "data" / "knowledge"
```

**修复代码**:
```python
def _load_source_documents(self) -> List[Dict[str, Any]]:
    knowledge_dir = Path(__file__).resolve().parents[2] / "data" / "knowledge"
```

**说明**: 将 `parents[3]` 改为 `parents[2]`，使路径指向正确的知识库目录

**影响**:
- 修复后将加载11个知识库文档
- 生成200-300个文本块
- bm25_index 将正常初始化
- RAG搜索功能恢复

**验证命令**:
```bash
cd backend
python -c "from app.rag.pipeline import RAGPipeline; p = RAGPipeline(); print(f'Documents: {len(p.source_documents)}'); print(f'Chunks: {len(p.knowledge_chunks)}')"
```

**预期输出**: `Documents: 11, Chunks: 200-300`

---

### P1 - 高优先级问题

#### 问题2: LLM路由器方法缺失

**文件**: `app/routing/llm_router.py`
**行号**: 186
**严重程度**: P1 - 高优先级

**当前代码**:
```python
# 第185-186行
model_id = self.model_manager.select_model("medium")
adapter = self.model_manager.get_adapter(model_id)  # ❌ 方法不存在
```

**修复代码**:
```python
# 在文件顶部添加导入
from app.models.model_adapter import ModelAdapterFactory

# 第185-190行修改为：
model_id = self.model_manager.select_model("medium")
if not model_id:
    return self._fallback_route(query)

model_config = self.model_manager.models.get(model_id)
if not model_config:
    return self._fallback_route(query)

adapter = ModelAdapterFactory.create_adapter(model_config)
```

**说明**: 使用 `ModelAdapterFactory.create_adapter()` 替代不存在的 `get_adapter()` 方法

**影响**:
- LLM路由功能将正常工作
- 3个失败的测试将通过
- Agent可以使用智能路由

**验证命令**:
```bash
cd backend
python -m pytest tests/test_agent_core.py::TestAgentRun -v
```

**预期输出**: 所有测试通过

---

### P2 - 中优先级问题

#### 问题3: 数据源优先级测试过时

**文件**: `tests/test_hardening.py`
**行号**: 35, 57
**严重程度**: P2 - 中优先级

**当前代码**:
```python
# 第35行
def test_get_price_uses_alpha_vantage_fallback(self, mock_yfinance_fail):
    # ...
    assert result.source == "alpha_vantage"  # ❌ 实际是 stooq

# 第57行
def test_get_history_uses_alpha_vantage_fallback(self, mock_yfinance_fail):
    # ...
    assert result.source == "alpha_vantage"  # ❌ 实际是 stooq
```

**修复代码**:
```python
# 第35行
def test_get_price_uses_alpha_vantage_fallback(self, mock_yfinance_fail):
    # ...
    assert result.source == "stooq"  # ✓ 匹配新的数据源优先级

# 第57行
def test_get_history_uses_alpha_vantage_fallback(self, mock_yfinance_fail):
    # ...
    assert result.source == "stooq"  # ✓ 匹配新的数据源优先级
```

**说明**: 更新测试以匹配新的数据源优先级（yfinance → stooq → alpha_vantage）

**影响**:
- 2个失败的测试将通过
- 测试将正确验证故障切换逻辑

**验证命令**:
```bash
cd backend
python -m pytest tests/test_hardening.py::TestMarketFallback -v
```

**预期输出**: 所有测试通过

---

## 修复步骤

### 步骤1: 修复知识库路径（5分钟）

```bash
# 1. 打开文件
# 编辑 app/rag/pipeline.py

# 2. 找到第172行
# 将 parents[3] 改为 parents[2]

# 3. 验证修复
cd backend
python -c "from app.rag.pipeline import RAGPipeline; p = RAGPipeline(); print(f'Documents: {len(p.source_documents)}'); print(f'Chunks: {len(p.knowledge_chunks)}')"

# 4. 运行相关测试
python -m pytest tests/test_hybrid_pipeline.py -v
```

### 步骤2: 修复LLM路由器（30分钟）

```bash
# 1. 打开文件
# 编辑 app/routing/llm_router.py

# 2. 在文件顶部添加导入（约第10行）
# from app.models.model_adapter import ModelAdapterFactory

# 3. 修改第185-190行
# 使用 ModelAdapterFactory.create_adapter()

# 4. 验证修复
cd backend
python -m pytest tests/test_agent_core.py::TestAgentRun -v
```

### 步骤3: 更新测试用例（15分钟）

```bash
# 1. 打开文件
# 编辑 tests/test_hardening.py

# 2. 修改第35行和第57行
# 将 "alpha_vantage" 改为 "stooq"

# 3. 验证修复
cd backend
python -m pytest tests/test_hardening.py::TestMarketFallback -v
```

### 步骤4: 运行完整测试套件（5分钟）

```bash
cd backend
python -m pytest tests/ -v

# 预期结果：220个测试全部通过
```

---

## 修复后验证清单

- [ ] 知识库文档加载正常（11个文档）
- [ ] 知识库文本块生成正常（200-300个）
- [ ] bm25索引初始化成功
- [ ] LLM路由功能正常工作
- [ ] 所有Agent测试通过
- [ ] 数据源故障切换测试通过
- [ ] 完整测试套件通过（220/220）

---

## 预期结果

### 修复前
- 测试通过: 214/220 (97.3%)
- 测试失败: 6/220 (2.7%)
- 代码质量: 8.8/10

### 修复后
- 测试通过: 220/220 (100%)
- 测试失败: 0/220 (0%)
- 代码质量: 9.2/10

---

## 总修复时间

- P0问题: 5分钟
- P1问题: 30分钟
- P2问题: 15分钟
- 验证测试: 5分钟

**总计**: 约55分钟

---

## 联系信息

如有问题，请参考：
- 详细报告: `CODE_QUALITY_REPORT_FINAL.md`
- 分部报告: `CODE_QUALITY_REPORT_PART1-4.md`
- 市场数据修复: `MARKET_DATA_FIX_SUMMARY.md`
