"""
测试数据集构建脚本 - 用于验证系统准确率和召回率
Test Dataset Builder - For validating system accuracy and recall
"""
import json
from pathlib import Path

# 测试数据集目录
TEST_DIR = Path(__file__).parent.parent / "tests" / "datasets"
TEST_DIR.mkdir(parents=True, exist_ok=True)

# 测试数据集：100条标注问答对
TEST_DATASET = [
    # 价格查询类（10条）
    {"id": 1, "query": "苹果股票现在多少钱", "expected_type": "price", "expected_symbols": ["AAPL"], "expected_answer_contains": ["价格", "美元"]},
    {"id": 2, "query": "TSLA最新价格", "expected_type": "price", "expected_symbols": ["TSLA"], "expected_answer_contains": ["价格"]},
    {"id": 3, "query": "贵州茅台今天股价", "expected_type": "price", "expected_symbols": ["600519.SS"], "expected_answer_contains": ["价格", "元"]},
    {"id": 4, "query": "比特币现价", "expected_type": "price", "expected_symbols": ["BTC-USD"], "expected_answer_contains": ["价格"]},
    {"id": 5, "query": "腾讯控股多少钱一股", "expected_type": "price", "expected_symbols": ["0700.HK"], "expected_answer_contains": ["价格"]},
    {"id": 6, "query": "阿里巴巴股价", "expected_type": "price", "expected_symbols": ["BABA"], "expected_answer_contains": ["价格"]},
    {"id": 7, "query": "特斯拉现在什么价位", "expected_type": "price", "expected_symbols": ["TSLA"], "expected_answer_contains": ["价格"]},
    {"id": 8, "query": "AAPL当前报价", "expected_type": "price", "expected_symbols": ["AAPL"], "expected_answer_contains": ["价格"]},
    {"id": 9, "query": "茅台股票价格", "expected_type": "price", "expected_symbols": ["600519.SS"], "expected_answer_contains": ["价格"]},
    {"id": 10, "query": "苹果公司股价多少", "expected_type": "price", "expected_symbols": ["AAPL"], "expected_answer_contains": ["价格"]},

    # 涨跌幅查询类（10条）
    {"id": 11, "query": "苹果股票今天涨了多少", "expected_type": "change", "expected_symbols": ["AAPL"], "expected_answer_contains": ["涨", "%"]},
    {"id": 12, "query": "特斯拉本周涨跌幅", "expected_type": "change", "expected_symbols": ["TSLA"], "expected_answer_contains": ["涨跌", "%"]},
    {"id": 13, "query": "AAPL近7天表现", "expected_type": "change", "expected_symbols": ["AAPL"], "expected_answer_contains": ["%"]},
    {"id": 14, "query": "茅台这个月涨了还是跌了", "expected_type": "change", "expected_symbols": ["600519.SS"], "expected_answer_contains": ["涨", "跌"]},
    {"id": 15, "query": "比特币今年涨幅", "expected_type": "change", "expected_symbols": ["BTC-USD"], "expected_answer_contains": ["%"]},
    {"id": 16, "query": "TSLA昨天涨跌情况", "expected_type": "change", "expected_symbols": ["TSLA"], "expected_answer_contains": ["涨", "跌"]},
    {"id": 17, "query": "阿里巴巴近期走势", "expected_type": "change", "expected_symbols": ["BABA"], "expected_answer_contains": ["走势"]},
    {"id": 18, "query": "苹果股票本月表现如何", "expected_type": "change", "expected_symbols": ["AAPL"], "expected_answer_contains": ["%"]},
    {"id": 19, "query": "特斯拉最近涨得厉害吗", "expected_type": "change", "expected_symbols": ["TSLA"], "expected_answer_contains": ["涨"]},
    {"id": 20, "query": "AAPL今年收益率", "expected_type": "change", "expected_symbols": ["AAPL"], "expected_answer_contains": ["%"]},

    # 知识问答类（20条）
    {"id": 41, "query": "什么是市盈率", "expected_type": "knowledge", "expected_symbols": [], "expected_answer_contains": ["市盈率", "PE", "股价", "收益"]},
    {"id": 42, "query": "如何计算ROE", "expected_type": "knowledge", "expected_symbols": [], "expected_answer_contains": ["ROE", "净资产收益率", "净利润"]},
    {"id": 43, "query": "MACD指标怎么看", "expected_type": "knowledge", "expected_symbols": [], "expected_answer_contains": ["MACD", "金叉", "死叉"]},
    {"id": 44, "query": "什么是蓝筹股", "expected_type": "knowledge", "expected_symbols": [], "expected_answer_contains": ["蓝筹股", "业绩", "规模"]},
    {"id": 45, "query": "RSI指标的含义", "expected_type": "knowledge", "expected_symbols": [], "expected_answer_contains": ["RSI", "超买", "超卖"]},
]

def save_test_dataset():
    """保存测试数据集"""
    output_file = TEST_DIR / "qa_test_dataset.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(TEST_DATASET, f, ensure_ascii=False, indent=2)

    print(f"[OK] Test dataset saved to {output_file}")
    print(f"[INFO] Total {len(TEST_DATASET)} test cases")

    # 统计各类型数量
    type_counts = {}
    for item in TEST_DATASET:
        t = item["expected_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\n[INFO] Test case distribution:")
    for t, count in sorted(type_counts.items()):
        print(f"  - {t}: {count} cases")

if __name__ == "__main__":
    save_test_dataset()
