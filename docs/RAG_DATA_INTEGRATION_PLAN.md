# RAG 数据集成与处理计划

## 📊 数据现状分析

### 数据统计
- **总文件数**: 89 个
- **Markdown 文件**: 73 个
- **PDF 文件**: 8 个
- **JSON 文件**: 2 个
- **HTML 文件**: 6 个

### 目录结构
```
F:\Financial_Asset_QA_System_cyx-master\data\
├── raw_data/              # 原始数据
│   ├── knowledge/         # 原始知识文档
│   └── finance_report/    # 财务报告 (PDF)
├── dealed_data/           # 已处理数据 (MinerU 解析后)
│   ├── *.md              # Markdown 格式 (2个)
│   ├── *.html            # HTML 格式 (2个)
│   └── *.json            # JSON 元数据 (2个)
└── knowledge/             # 结构化知识库 (39个 MD 文件)
    ├── 教材_证券投资基金基础知识_*.md
    └── 教材_金融市场基础知识_*.md
```

---

## 🎯 集成目标

将所有数据源整合到统一的 RAG 系统中，实现：
1. ✅ 多格式数据统一处理
2. ✅ 完整的 RAG Pipeline 流程
3. ✅ 高质量的向量索引
4. ✅ 可追溯的数据来源

---

## 📋 实施计划

### 阶段 1: 数据预处理与清洗 (1-2天)

#### 任务 1.1: 创建统一数据加载器
**目标**: 支持多种格式的数据加载

**实现**:
```python
# backend/app/rag/data_loader.py
class UnifiedDataLoader:
    """统一数据加载器"""

    def load_markdown(self, file_path: str) -> Document
    def load_pdf(self, file_path: str) -> Document  # 使用 MinerU
    def load_json(self, file_path: str) -> Document
    def load_html(self, file_path: str) -> Document

    def load_directory(self, dir_path: str) -> List[Document]
```

**优先级**: 🔴 高
**预计工时**: 4 小时

---

#### 任务 1.2: 数据清洗与标准化
**目标**: 清洗重复内容、标准化格式

**处理步骤**:
1. 去除版权信息、页眉页脚
2. 合并重复的标题
3. 标准化章节结构
4. 提取元数据（书名、章节、页码）

**优先级**: 🔴 高
**预计工时**: 6 小时

---

#### 任务 1.3: 数据去重
**目标**: 识别并合并重复内容

**策略**:
- 基于内容哈希去重
- 基于相似度去重（cosine similarity > 0.95）
- 保留最完整的版本

**优先级**: 🟡 中
**预计工时**: 4 hours

---

### 阶段 2: RAG Pipeline 集成 (2-3天)

#### 任务 2.1: 文档切分优化
**目标**: 针对不同数据源优化切分策略

**策略**:
- **教材类**: 按章节切分（保留层级结构）
- **财报类**: 按表格/段落切分
- **习题类**: 按题目切分

**配置**:
```python
CHUNK_STRATEGIES = {
    "textbook": {
        "chunk_size": 800,
        "overlap": 150,
        "split_by": "section"
    },
    "report": {
        "chunk_size": 600,
        "overlap": 100,
        "split_by": "paragraph"
    },
    "exercise": {
        "chunk_size": 400,
        "overlap": 50,
        "split_by": "question"
    }
}
```

**优先级**: 🔴 高
**预计工时**: 6 小时

---

#### 任务 2.2: 元数据增强
**目标**: 为每个 chunk 添加丰富的元数据

**元数据字段**:
```python
{
    "source_file": "教材_金融市场基础知识_第一章.md",
    "source_type": "textbook",  # textbook/report/exercise
    "book_title": "金融市场基础知识",
    "chapter": "第一章 金融市场体系",
    "section": "第一节 金融市场概述",
    "page_number": 1,
    "difficulty": "basic",  # basic/intermediate/advanced
    "tags": ["金融市场", "市场体系", "基础知识"],
    "created_at": "2026-03-11",
    "chunk_type": "text"  # text/table/formula/image
}
```

**优先级**: 🔴 高
**预计工时**: 4 小时

---

#### 任务 2.3: 向量索引构建
**目标**: 构建高质量的向量索引

**实现步骤**:
1. 使用 BGE-base-zh-v1.5 生成向量
2. 存储到 ChromaDB
3. 创建多个 collection（按数据类型分类）
4. 建立 BM25 索引

**Collection 设计**:
```python
collections = {
    "textbook_knowledge": "教材知识",
    "finance_reports": "财务报告",
    "exercises": "习题解析",
    "all_knowledge": "全部知识（主索引）"
}
```

**优先级**: 🔴 高
**预计工时**: 6 小时

---

### 阶段 3: 增强功能实现 (2-3天)

#### 任务 3.1: 多源检索融合
**目标**: 根据查询类型智能选择数据源

**策略**:
```python
query_routing = {
    "概念定义": ["textbook_knowledge"],
    "计算方法": ["textbook_knowledge", "exercises"],
    "实际案例": ["finance_reports"],
    "习题练习": ["exercises"]
}
```

**优先级**: 🟡 中
**预计工时**: 6 小时

---

#### 任务 3.2: 表格数据处理
**目标**: 特殊处理财报中的表格数据

**实现**:
- 表格转 Markdown 格式
- 保留表格结构信息
- 支持表格内容检索

**优先级**: 🟡 中
**预计工时**: 8 小时

---

#### 任务 3.3: 图片/公式处理
**目标**: 处理 MinerU 解析的图片和公式

**策略**:
- 图片：保存 OCR 文本 + 图片描述
- 公式：保存 LaTeX + 文本描述

**优先级**: 🟢 低
**预计工时**: 6 小时

---

### 阶段 4: 质量验证与优化 (1-2天)

#### 任务 4.1: 索引质量检查
**目标**: 验证索引的完整性和准确性

**检查项**:
- [ ] 所有文件都已处理
- [ ] 无重复 chunk
- [ ] 元数据完整
- [ ] 向量质量（检查异常值）

**优先级**: 🔴 高
**预计工时**: 4 小时

---

#### 任务 4.2: 检索质量测试
**目标**: 测试检索效果

**测试集**:
```python
test_queries = [
    "什么是市盈率？",
    "如何计算 ROE？",
    "金融市场的功能有哪些？",
    "证券投资基金的分类",
    "债券的久期是什么？"
]
```

**评估指标**:
- 召回率 (Recall@5)
- 精确率 (Precision@5)
- MRR (Mean Reciprocal Rank)

**优先级**: 🔴 高
**预计工时**: 4 小时

---

#### 任务 4.3: 性能优化
**目标**: 优化检索速度和内存使用

**优化点**:
- 批量索引（batch_size=100）
- 向量压缩（PQ/IVF）
- 缓存热门查询

**优先级**: 🟡 中
**预计工时**: 4 小时

---

## 🛠️ 技术实现

### 核心代码结构

```
backend/app/rag/
├── data_loader.py          # 统一数据加载器 (新增)
├── data_cleaner.py         # 数据清洗器 (新增)
├── chunk_strategy.py       # 切分策略 (新增)
├── metadata_extractor.py   # 元数据提取器 (新增)
├── index_builder.py        # 索引构建器 (已有，需增强)
├── enhanced_rag_pipeline.py # 增强 RAG 管道 (已有)
└── quality_checker.py      # 质量检查器 (新增)

backend/scripts/
├── build_unified_index.py  # 统一索引构建脚本 (新增)
├── validate_index.py       # 索引验证脚本 (新增)
└── test_retrieval.py       # 检索测试脚本 (新增)
```

---

## 📈 预期成果

### 数据处理成果
- ✅ 处理 **89 个文件**
- ✅ 生成 **~5000-8000 个 chunks**
- ✅ 构建 **4 个专业 collections**
- ✅ 完整的元数据标注

### 检索性能提升
- 召回率：70% → **90%** (+29%)
- 精确率：75% → **92%** (+23%)
- 平均检索时间：< 200ms

### 系统能力提升
- ✅ 支持多格式数据（MD/PDF/JSON/HTML）
- ✅ 智能数据源路由
- ✅ 表格/公式专项处理
- ✅ 完整的质量保障

---

## 📅 时间规划

| 阶段 | 任务 | 工时 | 完成时间 |
|------|------|------|----------|
| 阶段 1 | 数据预处理 | 14h | Day 1-2 |
| 阶段 2 | RAG 集成 | 16h | Day 3-4 |
| 阶段 3 | 增强功能 | 20h | Day 5-7 |
| 阶段 4 | 质量验证 | 12h | Day 8 |
| **总计** | | **62h** | **8 天** |

---

## 🎯 里程碑

### Milestone 1: 数据加载完成 (Day 2)
- ✅ 所有格式数据可加载
- ✅ 数据清洗完成
- ✅ 去重完成

### Milestone 2: 索引构建完成 (Day 4)
- ✅ 向量索引构建完成
- ✅ BM25 索引构建完成
- ✅ 元数据完整

### Milestone 3: 增强功能完成 (Day 7)
- ✅ 多源检索融合
- ✅ 表格数据处理
- ✅ 图片/公式处理

### Milestone 4: 系统上线 (Day 8)
- ✅ 质量验证通过
- ✅ 性能达标
- ✅ 文档完善

---

## 🚀 快速开始

### 第一步：创建统一数据加载器
```bash
# 创建新文件
touch backend/app/rag/data_loader.py
touch backend/app/rag/data_cleaner.py
touch backend/scripts/build_unified_index.py
```

### 第二步：运行数据处理
```bash
cd backend
python scripts/build_unified_index.py \
    --data-dir "F:\Financial_Asset_QA_System_cyx-master\data" \
    --output-dir "data/processed" \
    --chroma-dir "data/chroma_db"
```

### 第三步：验证索引质量
```bash
python scripts/validate_index.py \
    --chroma-dir "data/chroma_db"
```

### 第四步：测试检索效果
```bash
python scripts/test_retrieval.py \
    --query "什么是市盈率？" \
    --top-k 5
```

---

## 📊 成功指标

### 数据质量指标
- [ ] 数据覆盖率 > 95%
- [ ] 重复率 < 5%
- [ ] 元数据完整率 > 98%

### 检索质量指标
- [ ] Recall@5 > 90%
- [ ] Precision@5 > 85%
- [ ] MRR > 0.8

### 性能指标
- [ ] 索引构建时间 < 30 分钟
- [ ] 单次检索时间 < 200ms
- [ ] 内存使用 < 4GB

---

## 🔄 持续优化

### 短期优化 (1个月内)
1. 收集用户查询日志
2. 分析检索失败案例
3. 优化切分策略
4. 调整检索权重

### 长期优化 (3个月内)
1. 添加更多数据源
2. 实现增量更新
3. 支持多模态检索
4. 添加用户反馈循环

---

## 📝 注意事项

### 数据处理注意事项
1. **编码问题**: 统一使用 UTF-8
2. **特殊字符**: 清理 MinerU 解析的特殊符号
3. **表格格式**: 保持表格的可读性
4. **公式处理**: LaTeX 公式需要特殊处理

### 性能注意事项
1. **批量处理**: 避免逐个文件处理
2. **内存管理**: 大文件分批加载
3. **并行处理**: 使用多进程加速
4. **缓存策略**: 缓存常用查询结果

### 质量注意事项
1. **人工抽查**: 随机抽查 10% 的 chunks
2. **边界情况**: 测试极端查询
3. **错误处理**: 记录所有处理失败的文件
4. **版本控制**: 保留原始数据备份

---

## 🎉 预期效果

完成后，系统将具备：
- ✅ **89 个文件**全部集成
- ✅ **~6000 个高质量 chunks**
- ✅ **4 个专业知识库**
- ✅ **多格式数据支持**
- ✅ **智能检索路由**
- ✅ **完整的可观测性**

这将是一个**生产级的金融知识问答系统**！🚀
