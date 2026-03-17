# Critical Fixes Required Before Execution

## 审查结果

计划审查发现以下关键问题需要在执行前修复：

---

## 🔴 CRITICAL ISSUES (必须修复)

### 1. 文件路径错误

**问题**: 计划中引用的文件路径与实际项目结构不匹配

**需要修复的路径**:

| 计划中的路径 | 实际路径 | 影响的任务 |
|------------|---------|-----------|
| `backend/app/models.py` | `backend/app/models/schemas.py` | Task 10 |
| `backend/prompts.yaml` | `prompts.yaml` (项目根目录) | Task 4 |

**修复方案**:
- Task 10 Step 3: 修改 `backend/app/models/schemas.py` 而不是 `backend/app/models.py`
- Task 4 所有步骤: 使用 `prompts.yaml` 或 `../prompts.yaml`

---

### 2. Import 语句错误

**问题**: 所有从 `app.models` 导入的语句需要更新

**错误示例**:
```python
from app.models import Document
from app.models import StructuredAnswer
```

**正确写法**:
```python
from app.models.schemas import Document
from app.models.schemas import StructuredAnswer
```

**影响范围**: 所有新创建的文件

---

### 3. 缺少目录创建步骤

**问题**: Task 1 创建 `backend/data/financial_dictionary.txt` 但 `backend/data/` 目录不存在

**修复方案**: 在 Task 1 Step 1 之前添加:
```bash
mkdir -p backend/data
```

---

## 🟡 HIGH PRIORITY (强烈建议修复)

### 4. 缺少性能基线测量

**问题**: 没有在优化前测量当前性能指标

**建议**: 在 Task 1 之前添加 "Task 0: 建立性能基线"
- 运行现有系统的评估脚本
- 记录当前的准确率、召回率、处理时间
- 作为后续对比的基准

---

### 5. BM25 词典加载位置错误

**问题**: Task 2 中 jieba 词典在 `_tokenize` 方法中加载，应该在 `__init__` 中加载

**当前代码**:
```python
def _tokenize(self, text: str) -> List[str]:
    if dict_path.exists() and not hasattr(self, '_dict_loaded'):
        jieba.load_userdict(str(dict_path))
        self._dict_loaded = True
```

**应该改为**: 在 `HybridRAGPipeline.__init__` 中加载一次

---

### 6. 配置路径解析

**问题**: Task 1 添加的配置使用相对路径

**当前**:
```python
FINANCIAL_DICT_PATH: str = "data/financial_dictionary.txt"
```

**应该**:
```python
from pathlib import Path
FINANCIAL_DICT_PATH: str = str(Path(__file__).parent.parent / "data" / "financial_dictionary.txt")
```

---

## 🟢 MEDIUM PRIORITY (建议修复)

### 7. 置信度评分权重应该可配置

**问题**: Task 9 中权重硬编码

**建议**: 添加到 `config.py`:
```python
CONFIDENCE_RETRIEVAL_WEIGHT: float = 0.4
CONFIDENCE_ANSWER_WEIGHT: float = 0.3
CONFIDENCE_CITATION_WEIGHT: float = 0.3
```

---

### 8. 测试文件缺少完整导入

**问题**: 多个测试文件缺少必要的导入语句

**建议**: 确保每个测试文件都有完整的导入

---

### 9. MMR 相似度函数过于简化

**问题**: Task 8 中的字符级 Jaccard 相似度不适合生产环境

**建议**: 添加注释说明这是简化实现，生产环境应使用基于 embedding 的相似度

---

## 📋 执行前检查清单

在开始执行计划前，请确认：

- [ ] 已理解所有 CRITICAL 问题
- [ ] 在执行 Task 1 前创建 `backend/data/` 目录
- [ ] 在修改文件时使用正确的路径 (`models/schemas.py`, `prompts.yaml`)
- [ ] 所有新文件的 import 语句使用 `from app.models.schemas import ...`
- [ ] 考虑添加 Task 0 建立性能基线
- [ ] 验证 `requirements.txt` 中已包含 `jieba`

---

## 执行策略建议

### 方案 A: 边执行边修复 (推荐)
- 按照计划执行，遇到路径/导入错误时立即修复
- 优点: 快速开始，问题出现时解决
- 缺点: 可能需要多次修正

### 方案 B: 先修复计划文档
- 更新计划文档中的所有路径和导入语句
- 优点: 执行时更顺畅
- 缺点: 需要额外时间修改 3158 行文档

### 方案 C: 创建修复补丁
- 创建一个 "已知问题和修复" 文档（本文档）
- 执行时参考此文档进行调整
- 优点: 平衡速度和准确性
- 缺点: 需要记住修复点

**推荐**: 方案 C (当前方案)

---

## 总体评估

**计划质量**: 8.5/10
- 结构优秀，TDD 方法正确
- 技术实现合理，算法选择恰当
- 主要问题是文件路径和导入语句

**执行可行性**: 9/10 (修复 CRITICAL 问题后)
- 修复关键问题后可以顺利执行
- 预计成功率 95%+

**预期效果**: 符合目标
- 检索准确率提升 40-50%
- 召回率提升 30-40%
- 答案质量提升 35-45%

---

## 下一步行动

1. ✅ 已创建本修复文档
2. ⏭️ 开始执行 Task 1，注意应用上述修复
3. ⏭️ 每完成一个 Phase，运行集成测试验证
4. ⏭️ 完成所有任务后，运行完整评估脚本

---

**文档创建时间**: 2026-03-17
**审查者**: Plan Review Agent (ae742c11ef406c3f3)
