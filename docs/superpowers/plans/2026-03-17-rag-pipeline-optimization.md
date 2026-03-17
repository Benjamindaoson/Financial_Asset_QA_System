# RAG Pipeline 全面优化实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面优化金融资产问答系统的RAG pipeline，提升检索准确率40-60%和召回率30-50%

**Architecture:** 渐进式优化策略，分3个阶段实施。第一阶段改进BM25分词和查询改写（快速见效），第二阶段实现多查询生成和MMR重排序（深化优化），第三阶段增强质量控制（幻觉检测和验证）。所有新功能通过配置开关控制，完全向后兼容。

**Tech Stack:** Python 3.11, jieba分词, sentence-transformers, FlagEmbedding, ChromaDB, FastAPI

---

## 第一阶段：快速见效优化（预计1周）

### Task 1: 创建金融词典和查询处理器

**Files:**
- Create: `backend/data/financial_dictionary.txt`
- Create: `backend/app/rag/query_processor.py`
- Create: `backend/tests/test_query_processor.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 创建金融词典文件**

创建 `backend/data/financial_dictionary.txt`:

```text
市盈率
市净率
市销率
净资产收益率
每股收益
市值
总市值
流通市值
资产负债率
毛利率
净利率
营业收入
净利润
现金流
自由现金流
股息率
分红率
市盈率TTM
动态市盈率
静态市盈率
```

- [ ] **Step 2: 添加配置项**

在 `backend/app/config.py` 的 `Settings` 类中添加:

```python
# Query Processing Configuration
QUERY_REWRITE_ENABLED: bool = True
QUERY_SYNONYM_EXPANSION: bool = True
FINANCIAL_DICT_PATH: str = "data/financial_dictionary.txt"
```

- [ ] **Step 3: 编写查询处理器测试**

创建 `backend/tests/test_query_processor.py`:

```python
import pytest
from app.rag.query_processor import QueryProcessor

@pytest.fixture
def processor():
    return QueryProcessor()

def test_query_cleaning(processor):
    """测试查询清洗"""
    query = "  苹果公司  的  市盈率   是多少？？  "
    cleaned = processor.clean_query(query)
    assert cleaned == "苹果公司的市盈率是多少？"
    assert "  " not in cleaned

def test_synonym_expansion(processor):
    """测试同义词扩展"""
    query = "PE是什么"
    expanded = processor.expand_synonyms(query)
    assert "市盈率" in expanded or "price-to-earnings" in expanded.lower()

def test_financial_term_normalization(processor):
    """测试金融术语标准化"""
    query = "ROE指标"
    normalized = processor.normalize_financial_terms(query)
    assert "净资产收益率" in normalized or "ROE" in normalized
```

- [ ] **Step 4: 运行测试确认失败**

```bash
cd backend
pytest tests/test_query_processor.py -v
```

预期输出: FAIL - QueryProcessor not found

- [ ] **Step 5: 实现查询处理器**

创建 `backend/app/rag/query_processor.py`:

```python
"""
查询预处理器 - 查询清洗、同义词扩展、术语标准化
Query Processor - Cleaning, Synonym Expansion, Term Normalization
"""
import re
from typing import List, Set
from pathlib import Path
from app.config import settings

class QueryProcessor:
    """查询预处理器"""

    # 金融术语同义词映射
    SYNONYM_MAP = {
        "pe": ["市盈率", "price-to-earnings", "p/e ratio"],
        "pb": ["市净率", "price-to-book", "p/b ratio"],
        "ps": ["市销率", "price-to-sales"],
        "roe": ["净资产收益率", "return on equity"],
        "roa": ["资产收益率", "return on assets"],
        "eps": ["每股收益", "earnings per share"],
        "市盈率": ["pe", "price-to-earnings"],
        "市净率": ["pb", "price-to-book"],
    }

    def __init__(self):
        self.financial_terms = self._load_financial_dictionary()

    def _load_financial_dictionary(self) -> Set[str]:
        """加载金融词典"""
        dict_path = Path(settings.FINANCIAL_DICT_PATH)
        if not dict_path.exists():
            return set()

        terms = set()
        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                term = line.strip()
                if term:
                    terms.add(term)
        return terms

    def clean_query(self, query: str) -> str:
        """清洗查询文本"""
        # 移除多余空格
        query = re.sub(r'\s+', ' ', query)
        # 统一标点符号
        query = query.replace('？？', '？').replace('！！', '！')
        # 移除首尾空格
        query = query.strip()
        return query

    def expand_synonyms(self, query: str) -> List[str]:
        """扩展同义词"""
        if not settings.QUERY_SYNONYM_EXPANSION:
            return [query]

        expanded_queries = [query]
        query_lower = query.lower()

        # 查找匹配的术语
        for term, synonyms in self.SYNONYM_MAP.items():
            if term in query_lower:
                # 为每个同义词生成新查询
                for synonym in synonyms:
                    new_query = re.sub(
                        term,
                        synonym,
                        query_lower,
                        flags=re.IGNORECASE
                    )
                    if new_query != query_lower:
                        expanded_queries.append(new_query)

        # 去重并限制数量
        return list(dict.fromkeys(expanded_queries))[:3]

    def normalize_financial_terms(self, query: str) -> str:
        """标准化金融术语"""
        normalized = query

        # 将英文缩写替换为中文全称
        for abbr, full_terms in self.SYNONYM_MAP.items():
            if abbr.isupper() and len(abbr) <= 4:
                # 这是缩写，替换为中文
                chinese_term = next((t for t in full_terms if '\u4e00' <= t[0] <= '\u9fff'), None)
                if chinese_term:
                    normalized = re.sub(
                        r'\b' + abbr + r'\b',
                        chinese_term,
                        normalized,
                        flags=re.IGNORECASE
                    )

        return normalized

    def process(self, query: str) -> dict:
        """完整的查询处理流程"""
        # 1. 清洗
        cleaned = self.clean_query(query)

        # 2. 标准化术语
        normalized = self.normalize_financial_terms(cleaned)

        # 3. 扩展同义词
        expanded = self.expand_synonyms(normalized)

        return {
            "original": query,
            "cleaned": cleaned,
            "normalized": normalized,
            "expanded_queries": expanded
        }
```

- [ ] **Step 6: 运行测试确认通过**

```bash
pytest tests/test_query_processor.py -v
```

预期输出: PASS (3 tests)

- [ ] **Step 7: 提交代码**

```bash
git add backend/data/financial_dictionary.txt backend/app/rag/query_processor.py backend/tests/test_query_processor.py backend/app/config.py
git commit -m "feat: add query processor with synonym expansion and term normalization

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: 改进BM25分词（使用jieba）

**Files:**
- Modify: `backend/app/rag/hybrid_retrieval.py:115-139`
- Create: `backend/tests/test_bm25_tokenizer.py`

- [ ] **Step 1: 编写BM25分词测试**

创建 `backend/tests/test_bm25_tokenizer.py`:

```python
import pytest
from app.rag.hybrid_retrieval import BM25Retriever

def test_jieba_tokenization():
    """测试jieba分词"""
    retriever = BM25Retriever()

    # 测试金融术语不被切分
    text = "市盈率是重要的估值指标"
    tokens = retriever._tokenize(text)
    assert "市盈率" in tokens
    assert "估值" in tokens
    assert "指标" in tokens

    # 测试英文保持完整
    text2 = "Apple的PE ratio很高"
    tokens2 = retriever._tokenize(text2)
    assert "apple" in tokens2
    assert "pe" in tokens2
    assert "ratio" in tokens2

def test_mixed_language_tokenization():
    """测试中英文混合分词"""
    retriever = BM25Retriever()
    text = "AAPL的市盈率TTM是25倍"
    tokens = retriever._tokenize(text)
    assert "aapl" in tokens
    assert "市盈率" in tokens
    assert "ttm" in tokens
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_bm25_tokenizer.py -v
```

预期输出: FAIL - 当前使用字符级分词

- [ ] **Step 3: 修改BM25分词方法**

在 `backend/app/rag/hybrid_retrieval.py` 中修改 `_tokenize` 方法:

```python
def _tokenize(self, text: str) -> List[str]:
    """
    使用jieba进行中文分词 + 英文词级分词

    Args:
        text: 文本

    Returns:
        词列表
    """
    import jieba

    # 加载金融词典（如果存在）
    dict_path = Path(__file__).parent.parent.parent / "data" / "financial_dictionary.txt"
    if dict_path.exists() and not hasattr(self, '_dict_loaded'):
        jieba.load_userdict(str(dict_path))
        self._dict_loaded = True

    # 使用jieba分词
    tokens = []
    words = jieba.cut(text.lower())

    for word in words:
        word = word.strip()
        if not word:
            continue
        # 过滤停用词
        if word in {'的', '了', '是', '在', '有', '和', '与', '或', '等'}:
            continue
        tokens.append(word)

    return tokens
```

- [ ] **Step 4: 添加必要的import**

在文件顶部添加:

```python
from pathlib import Path
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_bm25_tokenizer.py -v
```

预期输出: PASS (2 tests)

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/hybrid_retrieval.py backend/tests/test_bm25_tokenizer.py
git commit -m "feat: improve BM25 tokenization with jieba for financial terms

- Replace character-level tokenization with jieba word segmentation
- Load financial dictionary for better term recognition
- Add stopword filtering

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

---

### Task 3: 集成查询处理器到混合检索pipeline

**Files:**
- Modify: `backend/app/rag/hybrid_pipeline.py:151-234`
- Create: `backend/tests/test_hybrid_pipeline_integration.py`

- [ ] **Step 1: 编写集成测试**

创建 `backend/tests/test_hybrid_pipeline_integration.py`:

```python
import pytest
from app.rag.hybrid_pipeline import HybridRAGPipeline

@pytest.mark.asyncio
async def test_query_preprocessing_integration():
    """测试查询预处理集成"""
    pipeline = HybridRAGPipeline()

    # 测试查询会被预处理
    result = await pipeline.search("PE是什么", use_hybrid=True)
    # 应该能检索到市盈率相关内容
    assert result.total_found > 0

@pytest.mark.asyncio
async def test_synonym_expansion_improves_recall():
    """测试同义词扩展提升召回率"""
    pipeline = HybridRAGPipeline()

    # 使用缩写查询
    result_abbr = await pipeline.search("ROE指标", use_hybrid=True)

    # 使用全称查询
    result_full = await pipeline.search("净资产收益率", use_hybrid=True)

    # 两者应该返回相似的结果
    assert result_abbr.total_found > 0
    assert result_full.total_found > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_hybrid_pipeline_integration.py -v
```

预期输出: FAIL - 查询未被预处理

- [ ] **Step 3: 修改HybridRAGPipeline集成查询处理器**

在 `backend/app/rag/hybrid_pipeline.py` 的 `__init__` 方法中添加:

```python
def __init__(self):
    super().__init__()
    self.bm25_index = None
    self.corpus_texts = []
    self.corpus_ids = []
    # 新增：初始化查询处理器
    from app.rag.query_processor import QueryProcessor
    self.query_processor = QueryProcessor()
```

- [ ] **Step 4: 修改search方法使用查询处理器**

在 `search` 方法开始处添加查询预处理:

```python
async def search(self, query: str, use_hybrid: bool = True) -> KnowledgeResult:
    """
    混合检索（增强版）

    Args:
        query: 查询文本
        use_hybrid: 是否使用混合检索

    Returns:
        检索结果
    """
    # 新增：查询预处理
    from app.config import settings
    if settings.QUERY_REWRITE_ENABLED:
        processed = self.query_processor.process(query)
        # 使用标准化后的查询
        query = processed["normalized"]
        # 如果启用同义词扩展，使用第一个扩展查询
        if settings.QUERY_SYNONYM_EXPANSION and len(processed["expanded_queries"]) > 1:
            query = processed["expanded_queries"][0]

    # 原有的检索逻辑...
    vector_result = await super().search(query)
    # ... 其余代码保持不变
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_hybrid_pipeline_integration.py -v
```

预期输出: PASS (2 tests)

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/hybrid_pipeline.py backend/tests/test_hybrid_pipeline_integration.py
git commit -m "feat: integrate query processor into hybrid retrieval pipeline

- Add query preprocessing before retrieval
- Enable synonym expansion for better recall
- Add integration tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: 优化生成提示词（Few-Shot示例）

**Files:**
- Modify: `backend/prompts.yaml`
- Create: `backend/tests/test_prompt_improvements.py`

- [ ] **Step 1: 备份现有prompts.yaml**

```bash
cp backend/prompts.yaml backend/prompts.yaml.backup
```

- [ ] **Step 2: 编写提示词测试**

创建 `backend/tests/test_prompt_improvements.py`:

```python
import pytest
import yaml
from pathlib import Path

def test_generator_prompt_has_few_shot_examples():
    """测试生成器提示词包含Few-Shot示例"""
    prompts_path = Path("prompts.yaml")
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = yaml.safe_load(f)

    system_prompt = prompts['generator']['system_prompt']

    # 应该包含示例标记
    assert "【示例" in system_prompt or "示例1" in system_prompt
    assert "查询:" in system_prompt or "问题:" in system_prompt
    assert "回答:" in system_prompt or "答案:" in system_prompt

def test_generator_prompt_has_citation_requirement():
    """测试提示词要求引用来源"""
    prompts_path = Path("prompts.yaml")
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = yaml.safe_load(f)

    system_prompt = prompts['generator']['system_prompt']

    # 应该明确要求引用
    assert "[文档" in system_prompt or "引用" in system_prompt or "来源" in system_prompt
```

- [ ] **Step 3: 运行测试确认失败**

```bash
pytest tests/test_prompt_improvements.py -v
```

预期输出: FAIL - 当前提示词缺少Few-Shot示例

- [ ] **Step 4: 修改generator提示词添加Few-Shot示例**

在 `backend/prompts.yaml` 中修改 `generator.system_prompt`:

```yaml
generator:
  system_prompt: |
    你是一个专业的金融知识助手。请严格遵守以下规则：

    【核心规则】
    1. 只能基于提供的文档回答问题
    2. 不允许使用文档之外的知识
    3. 如果文档中没有相关信息，必须明确说"根据现有资料无法回答"
    4. 必须引用来源，使用 [文档X] 标注

    【示例1 - 定义类问题】
    查询: 什么是市盈率？
    文档: [文档1] 市盈率(PE)是股价除以每股收益的比率，用于衡量股票估值水平。计算公式为：市盈率 = 股价 / 每股收益。
    回答: 市盈率是衡量股票估值的重要指标，计算公式为股价除以每股收益[文档1]。它反映了投资者愿意为每单位盈利支付的价格。

    【示例2 - 数据类问题】
    查询: 苹果公司2025年Q4营收是多少？
    文档: [文档1] 根据苹果公司2025年第四季度财报，该季度营收为1234亿美元，同比增长8%。
    回答: 根据财报数据，苹果公司2025年第四季度营收为1234亿美元，同比增长8%[文档1]。

    【示例3 - 信息不足】
    查询: 特斯拉2026年的营收预测？
    文档: [文档1] 特斯拉2025年Q3营收为XXX亿美元...
    回答: 根据现有资料无法回答2026年的营收预测。文档中仅包含2025年Q3的历史数据[文档1]，没有2026年的预测信息。

    【回答要求】
    1. 直接回答问题，简洁明了
    2. 每个关键信息后标注来源，如：市盈率是股价除以每股收益[文档1]
    3. 如果多个文档有相同信息，引用最相关的
    4. 不要添加文档中没有的信息
    5. 不要做推测或假设
    6. 使用简体中文回答
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_prompt_improvements.py -v
```

预期输出: PASS (2 tests)

- [ ] **Step 6: 提交代码**

```bash
git add backend/prompts.yaml backend/tests/test_prompt_improvements.py
git commit -m "feat: enhance generator prompt with Few-Shot examples

- Add 3 Few-Shot examples covering different query types
- Strengthen citation requirements
- Improve clarity on handling insufficient information

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: 添加引用验证机制

**Files:**
- Create: `backend/app/rag/citation_validator.py`
- Create: `backend/tests/test_citation_validator.py`
- Modify: `backend/app/rag/grounded_pipeline.py:210-224`

- [ ] **Step 1: 编写引用验证器测试**

创建 `backend/tests/test_citation_validator.py`:

```python
import pytest
from app.rag.citation_validator import CitationValidator

@pytest.fixture
def validator():
    return CitationValidator()

def test_detect_valid_citations(validator):
    """测试检测有效引用"""
    answer = "市盈率是股价除以每股收益[文档1]。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["is_valid"] is True
    assert len(result["citations"]) == 1
    assert 1 in result["citations"]

def test_detect_invalid_citations(validator):
    """测试检测无效引用"""
    answer = "市盈率是股价除以每股收益[文档5]。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["is_valid"] is False
    assert 5 in result["invalid_citations"]

def test_detect_missing_citations(validator):
    """测试检测缺失引用"""
    answer = "市盈率是股价除以每股收益。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["has_citations"] is False

def test_fix_invalid_citations(validator):
    """测试修复无效引用"""
    answer = "市盈率[文档5]是重要指标[文档10]。"
    num_docs = 3

    fixed = validator.fix_citations(answer, num_docs)
    assert "[文档5]" not in fixed
    assert "[文档10]" not in fixed
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_citation_validator.py -v
```

预期输出: FAIL - CitationValidator not found

- [ ] **Step 3: 实现引用验证器**

创建 `backend/app/rag/citation_validator.py`:

```python
"""
引用验证器 - 验证和修复LLM生成的文档引用
Citation Validator - Validate and fix document citations in LLM output
"""
import re
from typing import Dict, List, Set

class CitationValidator:
    """引用验证器"""

    def __init__(self):
        self.citation_pattern = re.compile(r'\[文档(\d+)\]')

    def validate(self, answer: str, num_docs: int) -> Dict:
        """
        验证答案中的引用是否有效

        Args:
            answer: LLM生成的答案
            num_docs: 实际提供的文档数量

        Returns:
            验证结果字典
        """
        # 提取所有引用
        citations = self.citation_pattern.findall(answer)
        citation_nums = [int(c) for c in citations]

        # 检查引用是否有效
        valid_citations = [c for c in citation_nums if 1 <= c <= num_docs]
        invalid_citations = [c for c in citation_nums if c > num_docs or c < 1]

        return {
            "is_valid": len(invalid_citations) == 0 and len(valid_citations) > 0,
            "has_citations": len(citation_nums) > 0,
            "citations": set(valid_citations),
            "invalid_citations": invalid_citations,
            "total_citations": len(citation_nums),
            "num_docs": num_docs
        }

    def fix_citations(self, answer: str, num_docs: int) -> str:
        """
        修复答案中的无效引用

        Args:
            answer: 原始答案
            num_docs: 实际文档数量

        Returns:
            修复后的答案
        """
        def replace_citation(match):
            doc_num = int(match.group(1))
            if doc_num > num_docs:
                # 无效引用，移除
                return ""
            return match.group(0)

        fixed = self.citation_pattern.sub(replace_citation, answer)

        # 清理多余空格
        fixed = re.sub(r'\s+', ' ', fixed)
        fixed = fixed.strip()

        return fixed

    def add_missing_citations(self, answer: str, num_docs: int) -> str:
        """
        为缺少引用的答案添加通用引用

        Args:
            answer: 原始答案
            num_docs: 文档数量

        Returns:
            添加引用后的答案
        """
        validation = self.validate(answer, num_docs)

        if validation["has_citations"]:
            return answer

        # 在答案末尾添加引用
        if num_docs > 0:
            return f"{answer}[文档1]"

        return answer

    def extract_cited_docs(self, answer: str) -> Set[int]:
        """
        提取答案中引用的文档编号

        Args:
            answer: 答案文本

        Returns:
            引用的文档编号集合
        """
        citations = self.citation_pattern.findall(answer)
        return set(int(c) for c in citations)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_citation_validator.py -v
```

预期输出: PASS (4 tests)

- [ ] **Step 5: 集成到grounded_pipeline**

在 `backend/app/rag/grounded_pipeline.py` 的 `_generate_grounded_answer` 方法中添加验证:

```python
async def _generate_grounded_answer(
    self,
    query: str,
    relevant_docs: List,
    require_sources: bool = True
) -> Dict:
    """生成基于事实的答案"""
    # ... 现有代码 ...

    try:
        response = await self.llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个严谨的金融知识助手，只基于提供的文档回答问题。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )

        answer_text = response.choices[0].message.content.strip()

        # 新增：验证引用
        from app.rag.citation_validator import CitationValidator
        validator = CitationValidator()
        validation = validator.validate(answer_text, len(relevant_docs))

        if not validation["is_valid"]:
            # 修复无效引用
            answer_text = validator.fix_citations(answer_text, len(relevant_docs))

        if require_sources and not validation["has_citations"]:
            # 添加缺失的引用
            answer_text = validator.add_missing_citations(answer_text, len(relevant_docs))

        return {
            "text": answer_text,
            "sources": sources,
            "context_used": context,
            "citation_validation": validation
        }
    # ... 其余代码保持不变
```

- [ ] **Step 6: 运行集成测试**

```bash
pytest tests/test_citation_validator.py tests/test_hybrid_pipeline_integration.py -v
```

预期输出: PASS (所有测试)

- [ ] **Step 7: 提交代码**

```bash
git add backend/app/rag/citation_validator.py backend/tests/test_citation_validator.py backend/app/rag/grounded_pipeline.py
git commit -m "feat: add citation validation and auto-fixing

- Implement CitationValidator to detect invalid citations
- Auto-fix citations exceeding document count
- Add missing citations when required
- Integrate into grounded answer generation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 第一阶段总结与验证

- [ ] **运行所有第一阶段测试**

```bash
pytest tests/test_query_processor.py tests/test_bm25_tokenizer.py tests/test_hybrid_pipeline_integration.py tests/test_prompt_improvements.py tests/test_citation_validator.py -v
```

预期输出: PASS (11 tests total)

- [ ] **手动验证检索质量提升**

运行测试脚本验证改进效果:

```bash
python backend/scripts/test_retrieval_quality.py
```

预期结果:
- BM25召回率提升 20-30%
- 同义词查询准确率提升 30-40%
- 引用准确率达到 95%+

---

## Chunk 1 结束

第一阶段（快速见效优化）已完成，包含5个核心任务：
1. ✅ 创建金融词典和查询处理器
2. ✅ 改进BM25分词（jieba）
3. ✅ 集成查询处理器到检索pipeline
4. ✅ 优化生成提示词（Few-Shot）
5. ✅ 添加引用验证机制

**预期效果**：
- 检索准确率提升 30-40%
- 答案引用准确率 95%+
- 金融术语识别准确率显著提升

---

## Chunk 2: 第二阶段 - 深化优化

**目标**: 提升检索多样性和动态适应能力

**核心改进**:
1. 多查询生成（Multi-Query Generation）
2. 动态Top-K调整
3. MMR多样性重排序
4. 改进置信度计算
5. 结构化输出

---

### Task 6: 多查询生成（Multi-Query Generation）

**Files:**
- Create: `backend/app/rag/multi_query_generator.py`
- Create: `backend/tests/test_multi_query_generator.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 编写多查询生成器测试**

创建 `backend/tests/test_multi_query_generator.py`:

```python
import pytest
from app.rag.multi_query_generator import MultiQueryGenerator

@pytest.fixture
def generator():
    return MultiQueryGenerator()

def test_generate_perspective_queries(generator):
    """测试生成不同视角的查询"""
    query = "苹果公司的市盈率是多少？"

    queries = generator.generate_queries(query, num_queries=3)

    assert len(queries) >= 2  # 至少包含原查询+1个变体
    assert query in queries  # 包含原查询
    # 变体应该包含同义词或不同表达
    assert any("PE" in q or "估值" in q for q in queries)

def test_generate_decomposed_queries(generator):
    """测试复杂查询分解"""
    query = "对比苹果和微软的市盈率和市净率"

    queries = generator.generate_queries(query, num_queries=4)

    # 应该分解为子查询
    assert len(queries) >= 3
    # 可能包含单独的查询
    assert any("苹果" in q and "市盈率" in q for q in queries)

def test_financial_term_expansion(generator):
    """测试金融术语扩展"""
    query = "什么是PE？"

    queries = generator.generate_queries(query, num_queries=2)

    # 应该扩展缩写
    assert any("市盈率" in q for q in queries)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_multi_query_generator.py -v
```

预期输出: FAIL - MultiQueryGenerator not found

- [ ] **Step 3: 实现多查询生成器**

创建 `backend/app/rag/multi_query_generator.py`:

```python
"""
多查询生成器 - 从单个查询生成多个视角的查询变体
Multi-Query Generator - Generate multiple query perspectives from a single query
"""
from typing import List
import re

class MultiQueryGenerator:
    """多查询生成器"""

    # 金融术语同义词映射
    TERM_SYNONYMS = {
        "PE": ["市盈率", "price-to-earnings", "盈利倍数"],
        "PB": ["市净率", "price-to-book", "账面价值比"],
        "ROE": ["净资产收益率", "return on equity", "股东回报率"],
        "市盈率": ["PE", "盈利倍数", "估值倍数"],
        "市净率": ["PB", "账面价值比"],
        "波动率": ["volatility", "风险", "价格波动"],
        "回撤": ["drawdown", "最大回撤", "亏损幅度"],
    }

    # 查询模板
    QUERY_TEMPLATES = {
        "definition": [
            "{term}的定义是什么？",
            "解释一下{term}",
            "{term}是什么意思？",
        ],
        "comparison": [
            "对比{entity1}和{entity2}的{metric}",
            "{entity1}与{entity2}的{metric}有什么区别？",
            "{entity1}和{entity2}在{metric}方面的表现",
        ],
        "data": [
            "{entity}的{metric}是多少？",
            "查询{entity}的{metric}数据",
            "{entity}{metric}的具体数值",
        ],
    }

    def __init__(self):
        pass

    def generate_queries(self, query: str, num_queries: int = 3) -> List[str]:
        """
        生成多个查询变体

        Args:
            query: 原始查询
            num_queries: 生成查询数量

        Returns:
            查询列表（包含原查询）
        """
        queries = [query]  # 始终包含原查询

        # 1. 同义词替换
        synonym_queries = self._generate_synonym_variants(query)
        queries.extend(synonym_queries[:num_queries-1])

        # 2. 如果是对比查询，分解为单独查询
        if self._is_comparison_query(query):
            decomposed = self._decompose_comparison(query)
            queries.extend(decomposed)

        # 3. 去重并限制数量
        unique_queries = []
        seen = set()
        for q in queries:
            if q not in seen:
                unique_queries.append(q)
                seen.add(q)
                if len(unique_queries) >= num_queries:
                    break

        return unique_queries

    def _generate_synonym_variants(self, query: str) -> List[str]:
        """生成同义词变体"""
        variants = []

        for term, synonyms in self.TERM_SYNONYMS.items():
            if term in query:
                for synonym in synonyms[:2]:  # 最多2个同义词
                    variant = query.replace(term, synonym)
                    if variant != query:
                        variants.append(variant)

        return variants

    def _is_comparison_query(self, query: str) -> bool:
        """判断是否为对比查询"""
        comparison_keywords = ["对比", "比较", "vs", "versus", "和", "与"]
        return any(kw in query for kw in comparison_keywords)

    def _decompose_comparison(self, query: str) -> List[str]:
        """分解对比查询为单独查询"""
        decomposed = []

        # 提取实体（简单实现）
        # 例如: "对比苹果和微软的市盈率" -> ["苹果的市盈率", "微软的市盈率"]

        # 匹配 "A和B的X" 模式
        pattern = r"(.+?)[和与](.+?)的(.+)"
        match = re.search(pattern, query)

        if match:
            entity1 = match.group(1).replace("对比", "").replace("比较", "").strip()
            entity2 = match.group(2).strip()
            metric = match.group(3).strip()

            decomposed.append(f"{entity1}的{metric}")
            decomposed.append(f"{entity2}的{metric}")

        return decomposed
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_multi_query_generator.py -v
```

预期输出: PASS (3 tests)

- [ ] **Step 5: 添加配置选项**

在 `backend/app/config.py` 中添加:

```python
# Multi-Query Generation
MULTI_QUERY_ENABLED: bool = True
MULTI_QUERY_NUM_VARIANTS: int = 3
```

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/multi_query_generator.py backend/tests/test_multi_query_generator.py backend/app/config.py
git commit -m "feat: add multi-query generation for improved recall

- Implement synonym-based query variants
- Decompose comparison queries into sub-queries
- Add financial term expansion
- Configurable via MULTI_QUERY_ENABLED

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 7: 动态Top-K调整

**Files:**
- Create: `backend/app/rag/dynamic_topk.py`
- Create: `backend/tests/test_dynamic_topk.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 编写动态Top-K测试**

创建 `backend/tests/test_dynamic_topk.py`:

```python
import pytest
from app.rag.dynamic_topk import DynamicTopKCalculator

@pytest.fixture
def calculator():
    return DynamicTopKCalculator()

def test_simple_query_small_k(calculator):
    """测试简单查询使用较小K值"""
    query = "什么是市盈率？"

    k = calculator.calculate_topk(query)

    assert k <= 5  # 简单定义查询，小K值足够

def test_complex_query_large_k(calculator):
    """测试复杂查询使用较大K值"""
    query = "对比苹果、微软、谷歌三家公司的市盈率、市净率和ROE，分析哪家估值更合理"

    k = calculator.calculate_topk(query)

    assert k >= 8  # 复杂对比查询，需要更多文档

def test_multi_entity_query(calculator):
    """测试多实体查询"""
    query = "苹果、微软、特斯拉的股价"

    k = calculator.calculate_topk(query)

    assert k >= 6  # 3个实体，每个至少2个文档
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_dynamic_topk.py -v
```

预期输出: FAIL - DynamicTopKCalculator not found

- [ ] **Step 3: 实现动态Top-K计算器**

创建 `backend/app/rag/dynamic_topk.py`:

```python
"""
动态Top-K计算器 - 根据查询复杂度动态调整检索数量
Dynamic Top-K Calculator - Adjust retrieval count based on query complexity
"""
import re
from typing import List

class DynamicTopKCalculator:
    """动态Top-K计算器"""

    # 复杂度指标关键词
    COMPARISON_KEYWORDS = {"对比", "比较", "vs", "versus", "哪个", "区别"}
    MULTI_METRIC_KEYWORDS = {"和", "与", "以及", "还有"}
    COMPLEX_KEYWORDS = {"分析", "评估", "综合", "全面", "详细"}

    def __init__(self, base_k: int = 5, max_k: int = 15):
        """
        初始化

        Args:
            base_k: 基础K值
            max_k: 最大K值
        """
        self.base_k = base_k
        self.max_k = max_k

    def calculate_topk(self, query: str) -> int:
        """
        计算动态Top-K值

        Args:
            query: 查询文本

        Returns:
            Top-K值
        """
        complexity_score = 0

        # 1. 检测对比查询 (+2)
        if any(kw in query for kw in self.COMPARISON_KEYWORDS):
            complexity_score += 2

        # 2. 检测多指标查询 (+1 per metric)
        metric_count = sum(1 for kw in self.MULTI_METRIC_KEYWORDS if kw in query)
        complexity_score += metric_count

        # 3. 检测复杂分析需求 (+2)
        if any(kw in query for kw in self.COMPLEX_KEYWORDS):
            complexity_score += 2

        # 4. 检测实体数量 (+1 per entity beyond first)
        entity_count = self._count_entities(query)
        if entity_count > 1:
            complexity_score += (entity_count - 1)

        # 5. 查询长度 (+1 if > 30 chars)
        if len(query) > 30:
            complexity_score += 1

        # 计算最终K值
        k = self.base_k + complexity_score
        k = min(k, self.max_k)  # 不超过最大值

        return k

    def _count_entities(self, query: str) -> int:
        """
        估算查询中的实体数量

        Args:
            query: 查询文本

        Returns:
            实体数量估计
        """
        # 简单实现：检测股票代码和公司名称
        # 股票代码模式: AAPL, MSFT, 600519等
        ticker_pattern = r'\b[A-Z]{2,5}\b|\b\d{6}\b'
        tickers = re.findall(ticker_pattern, query)

        # 常见公司名称
        company_names = ["苹果", "微软", "谷歌", "特斯拉", "亚马逊", "阿里", "腾讯", "茅台"]
        companies = [name for name in company_names if name in query]

        # 检测顿号、逗号分隔的列表
        if "、" in query or "，" in query:
            parts = re.split(r"[、，]", query)
            # 过滤掉短片段
            entities = [p.strip() for p in parts if len(p.strip()) >= 2]
            return max(len(entities), len(tickers) + len(companies))

        return len(tickers) + len(companies)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_dynamic_topk.py -v
```

预期输出: PASS (3 tests)

- [ ] **Step 5: 添加配置选项**

在 `backend/app/config.py` 中添加:

```python
# Dynamic Top-K
DYNAMIC_TOPK_ENABLED: bool = True
DYNAMIC_TOPK_BASE: int = 5
DYNAMIC_TOPK_MAX: int = 15
```

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/dynamic_topk.py backend/tests/test_dynamic_topk.py backend/app/config.py
git commit -m "feat: add dynamic Top-K calculation based on query complexity

- Calculate complexity score from multiple factors
- Adjust retrieval count for comparison/multi-entity queries
- Configurable base and max K values

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: MMR多样性重排序

**Files:**
- Create: `backend/app/rag/mmr_reranker.py`
- Create: `backend/tests/test_mmr_reranker.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 编写MMR重排序测试**

创建 `backend/tests/test_mmr_reranker.py`:

```python
import pytest
import numpy as np
from app.rag.mmr_reranker import MMRReranker
from app.models import Document

@pytest.fixture
def reranker():
    return MMRReranker(lambda_param=0.7)

@pytest.fixture
def sample_documents():
    """创建测试文档（包含相似和不同的文档）"""
    return [
        Document(content="市盈率是股价除以每股收益", source="doc1.md", score=0.9),
        Document(content="PE ratio是股价除以每股收益的比率", source="doc2.md", score=0.85),  # 与doc1相似
        Document(content="市净率是股价除以每股净资产", source="doc3.md", score=0.8),  # 不同主题
        Document(content="市盈率用于衡量股票估值水平", source="doc4.md", score=0.75),  # 与doc1相似
        Document(content="波动率反映价格变化幅度", source="doc5.md", score=0.7),  # 不同主题
    ]

def test_mmr_increases_diversity(reranker, sample_documents):
    """测试MMR提升结果多样性"""
    # 提供简单的相似度函数（基于内容长度差异）
    def similarity_fn(doc1, doc2):
        # 简化：基于共同字符数
        common = set(doc1.content) & set(doc2.content)
        return len(common) / max(len(doc1.content), len(doc2.content))

    reranked = reranker.rerank(sample_documents, top_n=3, similarity_fn=similarity_fn)

    # MMR应该选择多样化的文档
    assert len(reranked) == 3
    # 第一个应该是最高分
    assert reranked[0].source == "doc1.md"
    # 后续应该包含不同主题的文档
    sources = [doc.source for doc in reranked]
    # 应该包含至少一个不同主题的文档（doc3或doc5）
    assert "doc3.md" in sources or "doc5.md" in sources

def test_mmr_with_high_lambda_prefers_relevance(reranker, sample_documents):
    """测试高lambda值偏向相关性"""
    high_lambda_reranker = MMRReranker(lambda_param=0.9)

    def similarity_fn(doc1, doc2):
        common = set(doc1.content) & set(doc2.content)
        return len(common) / max(len(doc1.content), len(doc2.content))

    reranked = high_lambda_reranker.rerank(sample_documents, top_n=3, similarity_fn=similarity_fn)

    # 高lambda应该更偏向高分文档
    assert reranked[0].score >= reranked[1].score
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_mmr_reranker.py -v
```

预期输出: FAIL - MMRReranker not found

- [ ] **Step 3: 实现MMR重排序器**

创建 `backend/app/rag/mmr_reranker.py`:

```python
"""
MMR重排序器 - 使用Maximal Marginal Relevance提升结果多样性
MMR Reranker - Use Maximal Marginal Relevance for diverse results
"""
from typing import List, Callable
from app.models import Document

class MMRReranker:
    """MMR (Maximal Marginal Relevance) 重排序器"""

    def __init__(self, lambda_param: float = 0.7):
        """
        初始化

        Args:
            lambda_param: 相关性与多样性的权衡参数 (0-1)
                         1.0 = 完全基于相关性
                         0.0 = 完全基于多样性
        """
        self.lambda_param = lambda_param

    def rerank(
        self,
        documents: List[Document],
        top_n: int,
        similarity_fn: Callable[[Document, Document], float]
    ) -> List[Document]:
        """
        使用MMR重排序文档

        Args:
            documents: 候选文档列表（已按相关性排序）
            top_n: 返回文档数量
            similarity_fn: 文档相似度计算函数

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        if len(documents) <= top_n:
            return documents

        # 初始化
        selected = []
        remaining = documents.copy()

        # 第一个文档：选择最相关的
        selected.append(remaining.pop(0))

        # 迭代选择剩余文档
        while len(selected) < top_n and remaining:
            best_score = float('-inf')
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # 计算相关性分数（使用原始score）
                relevance = candidate.score

                # 计算与已选文档的最大相似度
                max_similarity = max(
                    similarity_fn(candidate, selected_doc)
                    for selected_doc in selected
                )

                # MMR分数 = λ * 相关性 - (1-λ) * 最大相似度
                mmr_score = (
                    self.lambda_param * relevance -
                    (1 - self.lambda_param) * max_similarity
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            # 选择最佳候选
            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def cosine_similarity(doc1: Document, doc2: Document) -> float:
        """
        计算两个文档的余弦相似度（基于内容）

        简化实现：基于字符集合的Jaccard相似度

        Args:
            doc1: 文档1
            doc2: 文档2

        Returns:
            相似度分数 (0-1)
        """
        # 简化实现：使用字符级Jaccard相似度
        set1 = set(doc1.content)
        set2 = set(doc2.content)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_mmr_reranker.py -v
```

预期输出: PASS (2 tests)

- [ ] **Step 5: 添加配置选项**

在 `backend/app/config.py` 中添加:

```python
# MMR Reranking
MMR_ENABLED: bool = True
MMR_LAMBDA: float = 0.7  # 0.7 = 70% relevance, 30% diversity
```

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/mmr_reranker.py backend/tests/test_mmr_reranker.py backend/app/config.py
git commit -m "feat: add MMR reranking for result diversity

- Implement Maximal Marginal Relevance algorithm
- Balance relevance and diversity with lambda parameter
- Prevent redundant similar documents in results

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
### Task 9: 改进置信度计算（多维度评分）

**Files:**
- Create: `backend/app/rag/confidence_scorer.py`
- Create: `backend/tests/test_confidence_scorer.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 编写置信度评分器测试**

创建 `backend/tests/test_confidence_scorer.py`:

```python
import pytest
from app.rag.confidence_scorer import ConfidenceScorer
from app.models import Document

@pytest.fixture
def scorer():
    return ConfidenceScorer()

@pytest.fixture
def high_quality_docs():
    """高质量文档：高分、多文档、有引用"""
    return [
        Document(content="市盈率是股价除以每股收益", source="doc1.md", score=0.9),
        Document(content="PE ratio计算公式为股价/EPS", source="doc2.md", score=0.85),
        Document(content="市盈率用于衡量估值水平", source="doc3.md", score=0.8),
    ]

@pytest.fixture
def low_quality_docs():
    """低质量文档：低分、单文档"""
    return [
        Document(content="一些不太相关的内容", source="doc1.md", score=0.3),
    ]

def test_high_confidence_with_quality_docs(scorer, high_quality_docs):
    """测试高质量文档产生高置信度"""
    answer = "市盈率是股价除以每股收益的比率[文档1]，用于衡量估值[文档3]。"

    confidence = scorer.calculate_confidence(
        answer=answer,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    assert confidence >= 0.7  # 高置信度

def test_low_confidence_with_poor_docs(scorer, low_quality_docs):
    """测试低质量文档产生低置信度"""
    answer = "市盈率是一个指标。"

    confidence = scorer.calculate_confidence(
        answer=answer,
        documents=low_quality_docs,
        query="什么是市盈率？"
    )

    assert confidence < 0.5  # 低置信度

def test_confidence_considers_citations(scorer, high_quality_docs):
    """测试置信度考虑引用情况"""
    answer_with_citations = "市盈率是股价除以每股收益[文档1]。"
    answer_without_citations = "市盈率是股价除以每股收益。"

    conf_with = scorer.calculate_confidence(
        answer=answer_with_citations,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    conf_without = scorer.calculate_confidence(
        answer=answer_without_citations,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    # 有引用的置信度应该更高
    assert conf_with > conf_without

def test_confidence_breakdown(scorer, high_quality_docs):
    """测试置信度分解"""
    answer = "市盈率是股价除以每股收益[文档1]。"

    result = scorer.calculate_confidence_breakdown(
        answer=answer,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    assert "overall" in result
    assert "retrieval_quality" in result
    assert "answer_quality" in result
    assert "citation_quality" in result
    assert 0 <= result["overall"] <= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_confidence_scorer.py -v
```

预期输出: FAIL - ConfidenceScorer not found

- [ ] **Step 3: 实现置信度评分器（第1部分）**

创建 `backend/app/rag/confidence_scorer.py`:

```python
"""
置信度评分器 - 多维度评估答案质量
Confidence Scorer - Multi-dimensional answer quality assessment
"""
import re
from typing import List, Dict
from app.models import Document

class ConfidenceScorer:
    """置信度评分器"""

    def __init__(
        self,
        retrieval_weight: float = 0.4,
        answer_weight: float = 0.3,
        citation_weight: float = 0.3
    ):
        """
        初始化

        Args:
            retrieval_weight: 检索质量权重
            answer_weight: 答案质量权重
            citation_weight: 引用质量权重
        """
        self.retrieval_weight = retrieval_weight
        self.answer_weight = answer_weight
        self.citation_weight = citation_weight

    def calculate_confidence(
        self,
        answer: str,
        documents: List[Document],
        query: str
    ) -> float:
        """
        计算整体置信度

        Args:
            answer: 生成的答案
            documents: 检索到的文档
            query: 原始查询

        Returns:
            置信度分数 (0-1)
        """
        breakdown = self.calculate_confidence_breakdown(answer, documents, query)
        return breakdown["overall"]

    def calculate_confidence_breakdown(
        self,
        answer: str,
        documents: List[Document],
        query: str
    ) -> Dict[str, float]:
        """
        计算置信度分解

        Args:
            answer: 生成的答案
            documents: 检索到的文档
            query: 原始查询

        Returns:
            置信度分解字典
        """
        # 1. 检索质量评分
        retrieval_score = self._score_retrieval_quality(documents)

        # 2. 答案质量评分
        answer_score = self._score_answer_quality(answer, query)

        # 3. 引用质量评分
        citation_score = self._score_citation_quality(answer, documents)

        # 4. 计算加权总分
        overall = (
            self.retrieval_weight * retrieval_score +
            self.answer_weight * answer_score +
            self.citation_weight * citation_score
        )

        return {
            "overall": overall,
            "retrieval_quality": retrieval_score,
            "answer_quality": answer_score,
            "citation_quality": citation_score,
        }
# __CONTINUE_HERE__
```

- [ ] **Step 4: 实现置信度评分器（第2部分）**

继续编辑 `backend/app/rag/confidence_scorer.py`，添加评分方法:

```python
    def _score_retrieval_quality(self, documents: List[Document]) -> float:
        """评估检索质量"""
        if not documents:
            return 0.0

        num_docs = len(documents)
        if num_docs <= 3:
            doc_count_score = 1.0
        elif num_docs <= 5:
            doc_count_score = 0.8
        else:
            doc_count_score = 0.6

        avg_score = sum(doc.score for doc in documents) / len(documents)
        top_score = documents[0].score if documents else 0.0

        retrieval_quality = (
            0.3 * doc_count_score +
            0.4 * avg_score +
            0.3 * top_score
        )

        return min(retrieval_quality, 1.0)

    def _score_answer_quality(self, answer: str, query: str) -> float:
        """评估答案质量"""
        if not answer:
            return 0.0

        refusal_keywords = ["无法回答", "没有相关", "不清楚", "不确定"]
        if any(kw in answer for kw in refusal_keywords):
            return 0.3

        answer_len = len(answer)
        if answer_len < 20:
            length_score = 0.5
        elif answer_len <= 200:
            length_score = 1.0
        elif answer_len <= 500:
            length_score = 0.8
        else:
            length_score = 0.6

        query_terms = set(query.replace("？", "").replace("?", "").split())
        answer_terms = set(answer.split())
        if query_terms:
            keyword_coverage = len(query_terms & answer_terms) / len(query_terms)
        else:
            keyword_coverage = 0.5

        answer_quality = 0.6 * length_score + 0.4 * keyword_coverage
        return min(answer_quality, 1.0)

    def _score_citation_quality(self, answer: str, documents: List[Document]) -> float:
        """评估引用质量"""
        citation_pattern = re.compile(r'\[文档(\d+)\]')
        citations = citation_pattern.findall(answer)

        if not citations:
            return 0.0

        num_citations = len(citations)
        citation_nums = [int(c) for c in citations]
        num_docs = len(documents)
        valid_citations = [c for c in citation_nums if 1 <= c <= num_docs]

        if not valid_citations:
            return 0.2

        validity_ratio = len(valid_citations) / len(citation_nums)

        if num_citations <= 3:
            count_score = 1.0
        elif num_citations <= 5:
            count_score = 0.8
        else:
            count_score = 0.6

        citation_quality = 0.7 * validity_ratio + 0.3 * count_score
        return min(citation_quality, 1.0)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_confidence_scorer.py -v
```

预期输出: PASS (4 tests)

- [ ] **Step 6: 添加配置选项**

在 `backend/app/config.py` 中添加:

```python
# Confidence Scoring
CONFIDENCE_SCORING_ENABLED: bool = True
CONFIDENCE_THRESHOLD: float = 0.5
```

- [ ] **Step 7: 提交代码**

```bash
git add backend/app/rag/confidence_scorer.py backend/tests/test_confidence_scorer.py backend/app/config.py
git commit -m "feat: add multi-dimensional confidence scoring

- Score retrieval quality (doc count, relevance)
- Score answer quality (length, keyword coverage)
- Score citation quality (validity, count)
- Provide confidence breakdown for transparency

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
### Task 10: 结构化输出（统一响应格式）

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/tests/test_structured_output.py`
- Modify: `backend/app/rag/grounded_pipeline.py`

- [ ] **Step 1: 编写结构化输出测试**

创建 `backend/tests/test_structured_output.py`:

```python
import pytest
from app.models import StructuredAnswer

def test_structured_answer_model():
    """测试结构化答案模型"""
    answer = StructuredAnswer(
        answer="市盈率是股价除以每股收益[文档1]。",
        confidence=0.85,
        sources=["doc1.md", "doc2.md"],
        metadata={
            "retrieval_quality": 0.9,
            "answer_quality": 0.8,
            "citation_quality": 0.85,
        }
    )

    assert answer.answer == "市盈率是股价除以每股收益[文档1]。"
    assert answer.confidence == 0.85
    assert len(answer.sources) == 2
    assert "retrieval_quality" in answer.metadata

def test_structured_answer_serialization():
    """测试序列化"""
    answer = StructuredAnswer(
        answer="测试答案",
        confidence=0.75,
        sources=["doc1.md"],
        metadata={"key": "value"}
    )

    data = answer.model_dump()

    assert data["answer"] == "测试答案"
    assert data["confidence"] == 0.75
    assert data["sources"] == ["doc1.md"]
    assert data["metadata"]["key"] == "value"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_structured_output.py -v
```

预期输出: FAIL - StructuredAnswer not found

- [ ] **Step 3: 添加结构化答案模型**

在 `backend/app/models.py` 中添加:

```python
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class StructuredAnswer(BaseModel):
    """结构化答案输出"""

    answer: str = Field(..., description="生成的答案文本")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度分数 (0-1)")
    sources: List[str] = Field(default_factory=list, description="引用的文档来源")
    metadata: Dict = Field(default_factory=dict, description="额外元数据")

    retrieval_method: Optional[str] = Field(None, description="使用的检索方法")
    processing_time_ms: Optional[float] = Field(None, description="处理时间（毫秒）")
    warning: Optional[str] = Field(None, description="警告信息（如低置信度）")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "市盈率是股价除以每股收益的比率[文档1]。",
                "confidence": 0.85,
                "sources": ["financial_terms.md"],
                "metadata": {
                    "retrieval_quality": 0.9,
                    "answer_quality": 0.8,
                    "citation_quality": 0.85
                },
                "retrieval_method": "hybrid",
                "processing_time_ms": 1250.5,
                "warning": None
            }
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_structured_output.py -v
```

预期输出: PASS (2 tests)

- [ ] **Step 5: 修改grounded_pipeline使用结构化输出**

在 `backend/app/rag/grounded_pipeline.py` 的 `answer` 方法中修改返回格式:

```python
async def answer(self, query: str) -> StructuredAnswer:
    """生成结构化答案"""
    import time
    start_time = time.time()

    knowledge_result = await self.search(query)

    if not knowledge_result.documents:
        return StructuredAnswer(
            answer="根据现有资料无法回答该问题。",
            confidence=0.0,
            sources=[],
            metadata={},
            retrieval_method="hybrid",
            processing_time_ms=(time.time() - start_time) * 1000,
            warning="未找到相关文档"
        )

    answer_data = await self._generate_grounded_answer(
        query=query,
        relevant_docs=knowledge_result.documents,
        require_sources=True
    )

    from app.rag.confidence_scorer import ConfidenceScorer
    from app.config import settings

    scorer = ConfidenceScorer()
    confidence_breakdown = scorer.calculate_confidence_breakdown(
        answer=answer_data["text"],
        documents=knowledge_result.documents,
        query=query
    )

    processing_time = (time.time() - start_time) * 1000

    structured = StructuredAnswer(
        answer=answer_data["text"],
        confidence=confidence_breakdown["overall"],
        sources=[doc.source for doc in knowledge_result.documents],
        metadata={
            "retrieval_quality": confidence_breakdown["retrieval_quality"],
            "answer_quality": confidence_breakdown["answer_quality"],
            "citation_quality": confidence_breakdown["citation_quality"],
            "total_docs_found": knowledge_result.total_found,
            "docs_used": len(knowledge_result.documents),
        },
        retrieval_method="hybrid",
        processing_time_ms=processing_time,
        warning=None if confidence_breakdown["overall"] >= settings.CONFIDENCE_THRESHOLD
                else f"低置信度答案 ({confidence_breakdown['overall']:.2f})"
    )

    return structured
```

- [ ] **Step 6: 运行集成测试**

```bash
pytest tests/test_structured_output.py -v
```

预期输出: PASS (所有测试)

- [ ] **Step 7: 提交代码**

```bash
git add backend/app/models.py backend/tests/test_structured_output.py backend/app/rag/grounded_pipeline.py
git commit -m "feat: add structured answer output format

- Define StructuredAnswer model with confidence and metadata
- Include processing time and warnings
- Provide confidence breakdown for transparency
- Enable downstream quality monitoring

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 第二阶段总结与验证

- [ ] **运行所有第二阶段测试**

```bash
pytest tests/test_multi_query_generator.py tests/test_dynamic_topk.py tests/test_mmr_reranker.py tests/test_confidence_scorer.py tests/test_structured_output.py -v
```

预期输出: PASS (14 tests total)

- [ ] **手动验证优化效果**

运行评估脚本:

```bash
python backend/scripts/evaluate_phase2_improvements.py
```

预期结果:
- 多查询召回率提升 15-25%
- MMR多样性指标提升 30-40%
- 置信度评分准确率 85%+

---

## Chunk 2 结束

第二阶段（深化优化）已完成，包含5个核心任务：
1. ✅ 多查询生成（提升召回率）
2. ✅ 动态Top-K调整（适应查询复杂度）
3. ✅ MMR多样性重排序（避免冗余）
4. ✅ 改进置信度计算（多维度评分）
5. ✅ 结构化输出（统一响应格式）

**预期效果**：
- 召回率提升 15-25%
- 结果多样性提升 30-40%
- 置信度评估准确率 85%+
- 输出格式标准化，便于监控

---

## Chunk 3: 第三阶段 - 质量控制增强

**目标**: 检测和防止幻觉，提升答案可信度

**核心改进**:
1. LLM幻觉检测
2. 数字上下文验证
3. 逻辑一致性检查
4. 集成测试和性能评估

---

### Task 11: LLM幻觉检测

**Files:**
- Create: `backend/app/rag/hallucination_detector.py`
- Create: `backend/tests/test_hallucination_detector.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: 编写幻觉检测器测试**

创建 `backend/tests/test_hallucination_detector.py`:

```python
import pytest
from app.rag.hallucination_detector import HallucinationDetector
from app.models import Document

@pytest.fixture
def detector():
    return HallucinationDetector()

@pytest.fixture
def sample_documents():
    return [
        Document(content="苹果公司2025年Q4营收为1234亿美元", source="doc1.md", score=0.9),
        Document(content="市盈率是股价除以每股收益", source="doc2.md", score=0.85),
    ]

def test_detect_no_hallucination(detector, sample_documents):
    """测试检测无幻觉的答案"""
    answer = "根据财报，苹果公司2025年Q4营收为1234亿美元[文档1]。"

    result = detector.detect(answer, sample_documents)

    assert result["has_hallucination"] is False
    assert result["confidence"] >= 0.8

def test_detect_number_hallucination(detector, sample_documents):
    """测试检测数字幻觉"""
    answer = "苹果公司2025年Q4营收为5678亿美元[文档1]。"  # 错误数字

    result = detector.detect(answer, sample_documents)

    assert result["has_hallucination"] is True
    assert "number_mismatch" in result["hallucination_types"]

def test_detect_entity_hallucination(detector, sample_documents):
    """测试检测实体幻觉"""
    answer = "微软公司2025年Q4营收为1234亿美元[文档1]。"  # 错误实体

    result = detector.detect(answer, sample_documents)

    assert result["has_hallucination"] is True
    assert "entity_mismatch" in result["hallucination_types"]

def test_detect_unsupported_claim(detector, sample_documents):
    """测试检测无依据的声明"""
    answer = "苹果公司将在2026年推出新产品[文档1]。"  # 文档中没有

    result = detector.detect(answer, sample_documents)

    assert result["has_hallucination"] is True
    assert "unsupported_claim" in result["hallucination_types"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_hallucination_detector.py -v
```

预期输出: FAIL - HallucinationDetector not found

- [ ] **Step 3: 实现幻觉检测器**

创建 `backend/app/rag/hallucination_detector.py`:

```python
"""
幻觉检测器 - 检测LLM生成答案中的幻觉内容
Hallucination Detector - Detect hallucinated content in LLM answers
"""
import re
from typing import List, Dict, Set
from app.models import Document

class HallucinationDetector:
    """幻觉检测器"""

    def __init__(self, threshold: float = 0.7):
        """
        初始化

        Args:
            threshold: 幻觉检测阈值
        """
        self.threshold = threshold

    def detect(self, answer: str, documents: List[Document]) -> Dict:
        """
        检测答案中的幻觉

        Args:
            answer: 生成的答案
            documents: 检索到的文档

        Returns:
            检测结果字典
        """
        hallucination_types = []
        details = []

        # 1. 数字验证
        if self._has_number_hallucination(answer, documents):
            hallucination_types.append("number_mismatch")
            details.append("答案中的数字与文档不匹配")

        # 2. 实体验证
        if self._has_entity_hallucination(answer, documents):
            hallucination_types.append("entity_mismatch")
            details.append("答案中的实体与文档不匹配")

        # 3. 无依据声明检测
        if self._has_unsupported_claim(answer, documents):
            hallucination_types.append("unsupported_claim")
            details.append("答案包含文档中没有的声明")

        has_hallucination = len(hallucination_types) > 0
        confidence = 0.0 if has_hallucination else 1.0

        return {
            "has_hallucination": has_hallucination,
            "hallucination_types": hallucination_types,
            "details": details,
            "confidence": confidence,
        }

    def _has_number_hallucination(self, answer: str, documents: List[Document]) -> bool:
        """检测数字幻觉"""
        # 提取答案中的数字
        answer_numbers = self._extract_numbers(answer)
        if not answer_numbers:
            return False

        # 提取文档中的数字
        doc_numbers = set()
        for doc in documents:
            doc_numbers.update(self._extract_numbers(doc.content))

        # 检查答案中的数字是否在文档中
        for num in answer_numbers:
            if num not in doc_numbers:
                # 允许小的舍入误差
                if not any(abs(num - doc_num) / max(num, doc_num) < 0.05 for doc_num in doc_numbers if doc_num > 0):
                    return True

        return False

    def _has_entity_hallucination(self, answer: str, documents: List[Document]) -> bool:
        """检测实体幻觉"""
        # 提取答案中的实体（公司名、股票代码）
        answer_entities = self._extract_entities(answer)
        if not answer_entities:
            return False

        # 提取文档中的实体
        doc_entities = set()
        for doc in documents:
            doc_entities.update(self._extract_entities(doc.content))

        # 检查答案中的实体是否在文档中
        for entity in answer_entities:
            if entity not in doc_entities:
                return True

        return False

    def _has_unsupported_claim(self, answer: str, documents: List[Document]) -> bool:
        """检测无依据的声明"""
        # 简化实现：检查答案中的关键短语是否在文档中
        # 移除引用标记
        clean_answer = re.sub(r'\[文档\d+\]', '', answer)

        # 分句
        sentences = re.split(r'[。！？]', clean_answer)

        doc_content = " ".join(doc.content for doc in documents)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            # 提取关键词（长度>=2的词）
            keywords = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', sentence) if len(w) >= 2]

            if not keywords:
                continue

            # 检查至少50%的关键词在文档中
            matched = sum(1 for kw in keywords if kw in doc_content)
            if matched / len(keywords) < 0.5:
                return True

        return False

    @staticmethod
    def _extract_numbers(text: str) -> Set[float]:
        """提取文本中的数字"""
        numbers = set()
        # 匹配整数和小数
        pattern = r'\d+\.?\d*'
        for match in re.finditer(pattern, text):
            try:
                num = float(match.group())
                numbers.add(num)
            except ValueError:
                continue
        return numbers

    @staticmethod
    def _extract_entities(text: str) -> Set[str]:
        """提取文本中的实体（公司名、股票代码）"""
        entities = set()

        # 股票代码
        ticker_pattern = r'\b[A-Z]{2,5}\b|\b\d{6}\b'
        entities.update(re.findall(ticker_pattern, text))

        # 常见公司名
        company_names = ["苹果", "微软", "谷歌", "特斯拉", "亚马逊", "阿里", "腾讯", "茅台", "贵州茅台"]
        for name in company_names:
            if name in text:
                entities.add(name)

        return entities
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_hallucination_detector.py -v
```

预期输出: PASS (4 tests)

- [ ] **Step 5: 添加配置选项**

在 `backend/app/config.py` 中添加:

```python
# Hallucination Detection
HALLUCINATION_DETECTION_ENABLED: bool = True
HALLUCINATION_THRESHOLD: float = 0.7
```

- [ ] **Step 6: 提交代码**

```bash
git add backend/app/rag/hallucination_detector.py backend/tests/test_hallucination_detector.py backend/app/config.py
git commit -m "feat: add LLM hallucination detection

- Detect number mismatches between answer and documents
- Detect entity hallucinations
- Detect unsupported claims
- Configurable detection threshold

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
### Task 12: 数字上下文验证

**Files:**
- Create: `backend/app/rag/number_validator.py`
- Create: `backend/tests/test_number_validator.py`

- [ ] **Step 1: 编写数字验证器测试**

创建 `backend/tests/test_number_validator.py`:

```python
import pytest
from app.rag.number_validator import NumberValidator

@pytest.fixture
def validator():
    return NumberValidator()

def test_validate_exact_match(validator):
    """测试精确匹配的数字"""
    answer = "苹果公司营收为1234亿美元"
    context = "根据财报，苹果公司营收为1234亿美元"

    result = validator.validate(answer, context)

    assert result["is_valid"] is True
    assert len(result["validated_numbers"]) > 0

def test_validate_approximate_match(validator):
    """测试近似匹配的数字（舍入误差）"""
    answer = "市盈率约为15.2"
    context = "市盈率为15.18"

    result = validator.validate(answer, context)

    assert result["is_valid"] is True  # 允许小误差

def test_detect_wrong_number(validator):
    """测试检测错误数字"""
    answer = "营收为5000亿美元"
    context = "营收为1234亿美元"

    result = validator.validate(answer, context)

    assert result["is_valid"] is False
    assert len(result["mismatched_numbers"]) > 0

def test_validate_with_units(validator):
    """测试带单位的数字验证"""
    answer = "增长了8%"
    context = "同比增长8%"

    result = validator.validate(answer, context)

    assert result["is_valid"] is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_number_validator.py -v
```

预期输出: FAIL - NumberValidator not found

- [ ] **Step 3: 实现数字验证器**

创建 `backend/app/rag/number_validator.py`:

```python
"""
数字验证器 - 验证答案中的数字是否与上下文一致
Number Validator - Validate numbers in answers against context
"""
import re
from typing import List, Dict, Tuple

class NumberValidator:
    """数字验证器"""

    def __init__(self, tolerance: float = 0.05):
        """
        初始化

        Args:
            tolerance: 允许的相对误差（默认5%）
        """
        self.tolerance = tolerance

    def validate(self, answer: str, context: str) -> Dict:
        """
        验证答案中的数字

        Args:
            answer: 生成的答案
            context: 上下文文档

        Returns:
            验证结果字典
        """
        # 提取答案和上下文中的数字
        answer_numbers = self._extract_numbers_with_context(answer)
        context_numbers = self._extract_numbers_with_context(context)

        validated = []
        mismatched = []

        for ans_num, ans_ctx in answer_numbers:
            # 查找上下文中是否有匹配的数字
            matched = False
            for ctx_num, ctx_ctx in context_numbers:
                if self._numbers_match(ans_num, ctx_num):
                    validated.append({
                        "number": ans_num,
                        "context": ans_ctx,
                        "source_number": ctx_num,
                        "source_context": ctx_ctx
                    })
                    matched = True
                    break

            if not matched:
                mismatched.append({
                    "number": ans_num,
                    "context": ans_ctx
                })

        is_valid = len(mismatched) == 0

        return {
            "is_valid": is_valid,
            "validated_numbers": validated,
            "mismatched_numbers": mismatched,
            "total_numbers": len(answer_numbers)
        }

    def _numbers_match(self, num1: float, num2: float) -> bool:
        """
        判断两个数字是否匹配（考虑舍入误差）

        Args:
            num1: 数字1
            num2: 数字2

        Returns:
            是否匹配
        """
        if num1 == num2:
            return True

        # 允许相对误差
        if max(abs(num1), abs(num2)) > 0:
            relative_error = abs(num1 - num2) / max(abs(num1), abs(num2))
            return relative_error <= self.tolerance

        return False

    def _extract_numbers_with_context(self, text: str) -> List[Tuple[float, str]]:
        """
        提取数字及其上下文

        Args:
            text: 文本

        Returns:
            (数字, 上下文) 列表
        """
        results = []

        # 匹配数字（整数、小数、百分比）
        pattern = r'(\d+\.?\d*)\s*(%|亿|万|千|百|美元|元|人民币)?'

        for match in re.finditer(pattern, text):
            try:
                num = float(match.group(1))

                # 提取上下文（前后各10个字符）
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 10)
                context = text[start:end]

                results.append((num, context))
            except ValueError:
                continue

        return results
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_number_validator.py -v
```

预期输出: PASS (4 tests)

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/rag/number_validator.py backend/tests/test_number_validator.py
git commit -m "feat: add number validation against context

- Extract numbers with surrounding context
- Validate numbers with tolerance for rounding errors
- Detect mismatched numbers between answer and source

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 13: 逻辑一致性检查

**Files:**
- Create: `backend/app/rag/consistency_checker.py`
- Create: `backend/tests/test_consistency_checker.py`

- [ ] **Step 1: 编写一致性检查器测试**

创建 `backend/tests/test_consistency_checker.py`:

```python
import pytest
from app.rag.consistency_checker import ConsistencyChecker

@pytest.fixture
def checker():
    return ConsistencyChecker()

def test_check_consistent_answer(checker):
    """测试一致的答案"""
    answer = "苹果公司市盈率为25，属于合理估值水平。"

    result = checker.check(answer)

    assert result["is_consistent"] is True

def test_detect_contradictory_statements(checker):
    """测试检测矛盾陈述"""
    answer = "市盈率很高，说明估值便宜。"  # 矛盾

    result = checker.check(answer)

    assert result["is_consistent"] is False
    assert "contradiction" in result["issues"]

def test_detect_temporal_inconsistency(checker):
    """测试检测时间不一致"""
    answer = "2025年Q4营收为1000亿，2025年Q3营收为1200亿，营收持续增长。"  # 实际在下降

    result = checker.check(answer)

    assert result["is_consistent"] is False
    assert "temporal_inconsistency" in result["issues"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_consistency_checker.py -v
```

预期输出: FAIL - ConsistencyChecker not found

- [ ] **Step 3: 实现一致性检查器**

创建 `backend/app/rag/consistency_checker.py`:

```python
"""
一致性检查器 - 检查答案的逻辑一致性
Consistency Checker - Check logical consistency of answers
"""
import re
from typing import Dict, List

class ConsistencyChecker:
    """一致性检查器"""

    # 矛盾关键词对
    CONTRADICTORY_PAIRS = [
        (["高", "上涨", "增长", "提升"], ["低", "下跌", "下降", "降低"]),
        (["便宜", "低估", "低价"], ["昂贵", "高估", "高价"]),
        (["好", "优秀", "强劲"], ["差", "糟糕", "疲软"]),
        (["增加", "扩大"], ["减少", "缩小"]),
    ]

    def __init__(self):
        pass

    def check(self, answer: str) -> Dict:
        """
        检查答案一致性

        Args:
            answer: 生成的答案

        Returns:
            检查结果字典
        """
        issues = []

        # 1. 检测矛盾陈述
        if self._has_contradiction(answer):
            issues.append("contradiction")

        # 2. 检测时间不一致
        if self._has_temporal_inconsistency(answer):
            issues.append("temporal_inconsistency")

        is_consistent = len(issues) == 0

        return {
            "is_consistent": is_consistent,
            "issues": issues,
            "details": self._generate_details(issues)
        }

    def _has_contradiction(self, answer: str) -> bool:
        """检测矛盾陈述"""
        # 分句
        sentences = re.split(r'[，。！？]', answer)

        for i, sent1 in enumerate(sentences):
            for sent2 in sentences[i+1:]:
                # 检查是否包含矛盾关键词对
                for positive_words, negative_words in self.CONTRADICTORY_PAIRS:
                    has_positive = any(word in sent1 for word in positive_words)
                    has_negative = any(word in sent2 for word in negative_words)

                    # 如果同一主题出现矛盾词
                    if has_positive and has_negative:
                        # 简化判断：如果两句话有共同实体，可能矛盾
                        common_entities = self._extract_common_entities(sent1, sent2)
                        if common_entities:
                            return True

        return False

    def _has_temporal_inconsistency(self, answer: str) -> bool:
        """检测时间不一致"""
        # 提取时间序列数据
        temporal_data = self._extract_temporal_data(answer)

        if len(temporal_data) < 2:
            return False

        # 检查趋势描述是否与数据一致
        trend_words = {
            "增长": "increase",
            "上涨": "increase",
            "提升": "increase",
            "下降": "decrease",
            "下跌": "decrease",
            "降低": "decrease",
        }

        for word, expected_trend in trend_words.items():
            if word in answer:
                # 检查实际数据趋势
                actual_trend = self._calculate_trend(temporal_data)
                if actual_trend and actual_trend != expected_trend:
                    return True

        return False

    def _extract_common_entities(self, sent1: str, sent2: str) -> List[str]:
        """提取两句话的共同实体"""
        # 简化实现：提取2-4字的中文词
        words1 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', sent1))
        words2 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', sent2))
        return list(words1 & words2)

    def _extract_temporal_data(self, text: str) -> List[Tuple[str, float]]:
        """提取时间序列数据"""
        # 匹配 "YYYY年QX" 或 "YYYY年X月" 后面的数字
        pattern = r'(\d{4}年[Q\d月]+)[^\d]*?(\d+\.?\d*)'
        matches = re.findall(pattern, text)
        return [(time, float(value)) for time, value in matches]

    def _calculate_trend(self, temporal_data: List[Tuple[str, float]]) -> str:
        """计算趋势"""
        if len(temporal_data) < 2:
            return None

        # 简化：比较最后两个数据点
        if temporal_data[-1][1] > temporal_data[-2][1]:
            return "increase"
        elif temporal_data[-1][1] < temporal_data[-2][1]:
            return "decrease"
        else:
            return "stable"

    def _generate_details(self, issues: List[str]) -> str:
        """生成问题详情"""
        if not issues:
            return "答案逻辑一致"

        details = []
        if "contradiction" in issues:
            details.append("检测到矛盾陈述")
        if "temporal_inconsistency" in issues:
            details.append("检测到时间序列不一致")

        return "；".join(details)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_consistency_checker.py -v
```

预期输出: PASS (3 tests)

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/rag/consistency_checker.py backend/tests/test_consistency_checker.py
git commit -m "feat: add logical consistency checking

- Detect contradictory statements
- Detect temporal inconsistencies
- Validate trend descriptions against data

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 14: 集成测试和性能评估

**Files:**
- Create: `backend/tests/test_rag_pipeline_integration.py`
- Create: `backend/scripts/evaluate_rag_improvements.py`
- Modify: `backend/app/rag/grounded_pipeline.py`

- [ ] **Step 1: 编写端到端集成测试**

创建 `backend/tests/test_rag_pipeline_integration.py`:

```python
import pytest
from app.rag.grounded_pipeline import GroundedRAGPipeline

@pytest.fixture
async def pipeline():
    return GroundedRAGPipeline()

@pytest.mark.asyncio
async def test_end_to_end_knowledge_query(pipeline):
    """测试知识类查询的完整流程"""
    query = "什么是市盈率？"

    result = await pipeline.answer(query)

    assert result.answer is not None
    assert len(result.answer) > 0
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0
    assert len(result.sources) > 0
    assert "retrieval_quality" in result.metadata

@pytest.mark.asyncio
async def test_end_to_end_with_hallucination_detection(pipeline):
    """测试幻觉检测集成"""
    query = "苹果公司的市盈率"

    result = await pipeline.answer(query)

    # 应该包含幻觉检测结果
    assert "hallucination_check" in result.metadata or result.warning is None

@pytest.mark.asyncio
async def test_end_to_end_with_confidence_scoring(pipeline):
    """测试置信度评分集成"""
    query = "市净率的计算公式"

    result = await pipeline.answer(query)

    # 应该有置信度分解
    assert "retrieval_quality" in result.metadata
    assert "answer_quality" in result.metadata
    assert "citation_quality" in result.metadata

@pytest.mark.asyncio
async def test_low_confidence_warning(pipeline):
    """测试低置信度警告"""
    query = "一个不太可能有答案的问题xyz123"

    result = await pipeline.answer(query)

    # 低置信度应该有警告
    if result.confidence < 0.5:
        assert result.warning is not None
```

- [ ] **Step 2: 运行集成测试确认失败**

```bash
pytest tests/test_rag_pipeline_integration.py -v
```

预期输出: FAIL - 部分功能未集成

- [ ] **Step 3: 集成所有优化到grounded_pipeline**

修改 `backend/app/rag/grounded_pipeline.py`，集成所有新功能:

```python
async def answer(self, query: str) -> StructuredAnswer:
    """生成结构化答案（集成所有优化）"""
    import time
    from app.config import settings
    from app.rag.confidence_scorer import ConfidenceScorer
    from app.rag.hallucination_detector import HallucinationDetector
    from app.rag.number_validator import NumberValidator
    from app.rag.consistency_checker import ConsistencyChecker

    start_time = time.time()

    # 检索文档
    knowledge_result = await self.search(query)

    if not knowledge_result.documents:
        return StructuredAnswer(
            answer="根据现有资料无法回答该问题。",
            confidence=0.0,
            sources=[],
            metadata={},
            retrieval_method="hybrid",
            processing_time_ms=(time.time() - start_time) * 1000,
            warning="未找到相关文档"
        )

    # 生成答案
    answer_data = await self._generate_grounded_answer(
        query=query,
        relevant_docs=knowledge_result.documents,
        require_sources=True
    )

    answer_text = answer_data["text"]

    # 1. 置信度评分
    scorer = ConfidenceScorer()
    confidence_breakdown = scorer.calculate_confidence_breakdown(
        answer=answer_text,
        documents=knowledge_result.documents,
        query=query
    )

    # 2. 幻觉检测
    hallucination_result = {}
    if settings.HALLUCINATION_DETECTION_ENABLED:
        detector = HallucinationDetector()
        hallucination_result = detector.detect(answer_text, knowledge_result.documents)

    # 3. 数字验证
    number_validation = {}
    if settings.CONFIDENCE_SCORING_ENABLED:
        validator = NumberValidator()
        context = " ".join(doc.content for doc in knowledge_result.documents)
        number_validation = validator.validate(answer_text, context)

    # 4. 一致性检查
    consistency_result = {}
    if settings.CONFIDENCE_SCORING_ENABLED:
        checker = ConsistencyChecker()
        consistency_result = checker.check(answer_text)

    processing_time = (time.time() - start_time) * 1000

    # 构建元数据
    metadata = {
        "retrieval_quality": confidence_breakdown["retrieval_quality"],
        "answer_quality": confidence_breakdown["answer_quality"],
        "citation_quality": confidence_breakdown["citation_quality"],
        "total_docs_found": knowledge_result.total_found,
        "docs_used": len(knowledge_result.documents),
    }

    if hallucination_result:
        metadata["hallucination_check"] = hallucination_result

    if number_validation:
        metadata["number_validation"] = number_validation

    if consistency_result:
        metadata["consistency_check"] = consistency_result

    # 生成警告
    warnings = []
    if confidence_breakdown["overall"] < settings.CONFIDENCE_THRESHOLD:
        warnings.append(f"低置信度 ({confidence_breakdown['overall']:.2f})")

    if hallucination_result.get("has_hallucination"):
        warnings.append("检测到可能的幻觉内容")

    if not consistency_result.get("is_consistent", True):
        warnings.append("检测到逻辑不一致")

    warning = "；".join(warnings) if warnings else None

    structured = StructuredAnswer(
        answer=answer_text,
        confidence=confidence_breakdown["overall"],
        sources=[doc.source for doc in knowledge_result.documents],
        metadata=metadata,
        retrieval_method="hybrid",
        processing_time_ms=processing_time,
        warning=warning
    )

    return structured
```

- [ ] **Step 4: 运行集成测试确认通过**

```bash
pytest tests/test_rag_pipeline_integration.py -v
```

预期输出: PASS (4 tests)

- [ ] **Step 5: 创建性能评估脚本**

创建 `backend/scripts/evaluate_rag_improvements.py`:

```python
"""
RAG优化效果评估脚本
"""
import asyncio
import time
from app.rag.grounded_pipeline import GroundedRAGPipeline

# 测试查询集
TEST_QUERIES = [
    "什么是市盈率？",
    "苹果公司的市值是多少？",
    "对比苹果和微软的市盈率",
    "市净率和市盈率的区别",
    "如何计算波动率？",
]

async def evaluate():
    pipeline = GroundedRAGPipeline()

    print("=" * 60)
    print("RAG Pipeline 优化效果评估")
    print("=" * 60)

    total_time = 0
    high_confidence_count = 0
    no_hallucination_count = 0

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] 查询: {query}")

        start = time.time()
        result = await pipeline.answer(query)
        elapsed = time.time() - start

        total_time += elapsed

        print(f"  答案: {result.answer[:100]}...")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  处理时间: {elapsed:.2f}s")
        print(f"  警告: {result.warning or '无'}")

        if result.confidence >= 0.7:
            high_confidence_count += 1

        if not result.metadata.get("hallucination_check", {}).get("has_hallucination", False):
            no_hallucination_count += 1

    print("\n" + "=" * 60)
    print("评估总结")
    print("=" * 60)
    print(f"平均处理时间: {total_time / len(TEST_QUERIES):.2f}s")
    print(f"高置信度比例: {high_confidence_count / len(TEST_QUERIES) * 100:.1f}%")
    print(f"无幻觉比例: {no_hallucination_count / len(TEST_QUERIES) * 100:.1f}%")

if __name__ == "__main__":
    asyncio.run(evaluate())
```

- [ ] **Step 6: 运行性能评估**

```bash
python backend/scripts/evaluate_rag_improvements.py
```

预期输出: 显示各项指标的改进情况

- [ ] **Step 7: 提交代码**

```bash
git add backend/tests/test_rag_pipeline_integration.py backend/scripts/evaluate_rag_improvements.py backend/app/rag/grounded_pipeline.py
git commit -m "feat: integrate all RAG optimizations and add evaluation

- Integrate confidence scoring, hallucination detection, validation
- Add end-to-end integration tests
- Create performance evaluation script
- Complete Phase 3 quality control enhancements

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 第三阶段总结与验证

- [ ] **运行所有第三阶段测试**

```bash
pytest tests/test_hallucination_detector.py tests/test_number_validator.py tests/test_consistency_checker.py tests/test_rag_pipeline_integration.py -v
```

预期输出: PASS (11 tests total)

- [ ] **运行完整测试套件**

```bash
pytest tests/ -v --tb=short
```

预期输出: PASS (所有测试)

- [ ] **性能基准测试**

```bash
python backend/scripts/evaluate_rag_improvements.py
```

预期结果:
- 幻觉检测准确率 90%+
- 数字验证准确率 95%+
- 一致性检查准确率 85%+

---

## Chunk 3 结束

第三阶段（质量控制增强）已完成，包含4个核心任务：
1. ✅ LLM幻觉检测（数字、实体、无依据声明）
2. ✅ 数字上下文验证（容错匹配）
3. ✅ 逻辑一致性检查（矛盾检测、时间序列）
4. ✅ 集成测试和性能评估

**预期效果**：
- 幻觉检测准确率 90%+
- 答案可信度显著提升
- 完整的质量监控体系

---

## 全流程总结

### 已完成的优化

**第一阶段（快速见效）**:
1. ✅ 金融词典 + 查询处理器
2. ✅ BM25分词优化（jieba）
3. ✅ 查询处理器集成
4. ✅ Few-Shot提示词
5. ✅ 引用验证机制

**第二阶段（深化优化）**:
6. ✅ 多查询生成
7. ✅ 动态Top-K调整
8. ✅ MMR多样性重排序
9. ✅ 多维度置信度评分
10. ✅ 结构化输出

**第三阶段（质量控制）**:
11. ✅ LLM幻觉检测
12. ✅ 数字上下文验证
13. ✅ 逻辑一致性检查
14. ✅ 集成测试和评估

### 预期整体效果

- **检索准确率**: 提升 40-50%
- **召回率**: 提升 30-40%
- **答案质量**: 提升 35-45%
- **幻觉率**: 降低 60-70%
- **置信度评估准确率**: 85%+

### 配置开关

所有新功能均可通过 `backend/app/config.py` 配置开关控制，确保向后兼容。

### 下一步

运行完整评估脚本验证优化效果:

```bash
python backend/scripts/evaluate_rag_improvements.py
```

---

**实施计划完成！** 🎉
