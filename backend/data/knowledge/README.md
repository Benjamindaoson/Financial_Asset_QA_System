# 金融知识库 (Financial Knowledge Base)

本目录存储RAG检索所需的结构化金融知识文档。

## 文档列表

根据系统README，应包含以下11个文档：

1. **股票基础.md** - A股/港股/美股交易规则、涨跌停板、T+0/T+1、融资融券
2. **core_finance_metrics.md** - PE、PB、EPS、PEG、ROE等核心估值指标
3. **基本面分析.md** - 财务三表解读、盈利能力、偿债能力
4. **技术分析.md** - K线形态、均线系统、MACD、RSI、布林带
5. **ETF基金.md** - ETF分类、折溢价、跟踪误差
6. **宏观经济.md** - GDP、CPI、利率、汇率、货币政策
7. **市场术语.md** - 常见金融术语词典
8. **投资策略.md** - 价值投资、成长投资、量化策略
9. **量化投资.md** - 因子模型、回测逻辑、Alpha挖掘
10. **期权期货.md** - 衍生品定价原理、Greeks、套期保值
11. **风险管理.md** - VaR、最大回撤、夏普比率、凯利公式

## 文档格式要求

- 使用Markdown格式
- 每个文档应包含清晰的章节结构
- 关键术语使用粗体标注
- 公式使用LaTeX格式（如适用）
- 每个概念应包含定义、公式、示例

## 索引构建

运行以下命令构建向量索引：

```bash
cd backend
python scripts/build_vector_index.py
```

## 更新机制

- 手动更新：直接编辑Markdown文件后重新构建索引
- 自动更新：使用`scripts/knowledge_ingestion_pipeline.py`（待实现）
