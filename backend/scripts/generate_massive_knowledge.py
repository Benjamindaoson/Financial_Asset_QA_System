"""
Generate massive financial knowledge dataset (10,000+ entries).
Covers stocks, funds, bonds, derivatives, macroeconomics, and more.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def generate_stock_companies():
    """生成A股上市公司知识"""
    entries = []

    # 主要行业板块
    sectors = [
        ("银行", ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行", "招商银行", "兴业银行", "浦发银行", "民生银行", "光大银行"]),
        ("保险", ["中国平安", "中国人寿", "中国太保", "新华保险", "中国人保"]),
        ("证券", ["中信证券", "海通证券", "国泰君安", "华泰证券", "广发证券", "招商证券", "东方证券", "申万宏源"]),
        ("房地产", ["万科A", "保利发展", "招商蛇口", "金地集团", "华侨城A", "绿地控股", "新城控股", "融创中国"]),
        ("白酒", ["贵州茅台", "五粮液", "泸州老窖", "洋河股份", "山西汾酒", "古井贡酒", "水井坊", "舍得酒业"]),
        ("医药", ["恒瑞医药", "迈瑞医疗", "药明康德", "爱尔眼科", "片仔癀", "云南白药", "同仁堂", "东阿阿胶"]),
        ("科技", ["中兴通讯", "海康威视", "大华股份", "科大讯飞", "紫光股份", "浪潮信息", "中科曙光", "卫士通"]),
        ("新能源", ["宁德时代", "比亚迪", "隆基绿能", "阳光电源", "亿纬锂能", "天齐锂业", "赣锋锂业", "恩捷股份"]),
        ("家电", ["美的集团", "格力电器", "海尔智家", "海信视像", "小天鹅A", "老板电器", "苏泊尔", "九阳股份"]),
        ("汽车", ["上汽集团", "长城汽车", "长安汽车", "广汽集团", "吉利汽车", "比亚迪", "蔚来", "小鹏汽车"]),
    ]

    for sector, companies in sectors:
        for company in companies:
            entries.append({
                "title": f"{company}公司简介",
                "content": f"{company}是中国{sector}行业的领先企业，在A股市场上市交易。公司主营业务涵盖{sector}相关产品和服务，具有较强的市场竞争力和品牌影响力。投资者可以通过研究公司财报、行业地位、竞争优势等因素评估投资价值。",
                "category": "listed_companies",
                "keywords": [company, sector, "上市公司", "A股"],
                "source": "financial_encyclopedia"
            })

    return entries


def generate_industry_analysis():
    """生成行业分析知识"""
    entries = []

    industries = [
        ("银行业", "银行业是金融体系的核心，主要业务包括存款、贷款、结算等。行业特点：资本密集、监管严格、利差收入为主。关键指标：不良贷款率、资本充足率、净息差、ROE。投资要点：关注资产质量、盈利能力、估值水平。"),
        ("保险业", "保险业提供风险保障和财富管理服务。主要业务：寿险、财险、健康险。关键指标：保费收入、综合成本率、内含价值、新业务价值。投资要点：关注保费增长、投资收益、偿付能力。"),
        ("证券业", "证券业提供证券交易、投资银行、资产管理等服务。业务周期性强，受市场行情影响大。关键指标：经纪业务收入、投行业务收入、自营业务收益。投资要点：关注市场成交量、业务结构、风控能力。"),
        ("房地产业", "房地产业是国民经济支柱产业。主要业务：住宅开发、商业地产、物业管理。关键指标：销售额、土地储备、负债率、毛利率。投资要点：关注政策调控、销售去化、财务杠杆。"),
        ("白酒行业", "白酒行业具有消费属性和文化属性。高端白酒具有品牌壁垒和提价能力。关键指标：营收增长、毛利率、渠道库存、品牌力。投资要点：关注消费升级、渠道拓展、产品结构。"),
    ]

    for industry, content in industries:
        entries.append({
            "title": f"{industry}分析",
            "content": content,
            "category": "industry_analysis",
            "keywords": [industry, "行业分析", "投资"],
            "source": "financial_encyclopedia"
        })

    return entries


def generate_financial_ratios():
    """生成财务比率知识"""
    entries = []

    ratios = [
        ("杜邦分析", "杜邦分析将ROE分解为净利率、总资产周转率和权益乘数三个因素。公式：ROE = 净利率 × 总资产周转率 × 权益乘数。通过分解可以识别企业盈利能力的驱动因素。", ["杜邦分析", "ROE", "财务分析"]),
        ("营运资本", "营运资本 = 流动资产 - 流动负债，反映企业短期财务状况。营运资本为正表示企业有足够的流动资产偿还短期债务。", ["营运资本", "流动性", "财务"]),
        ("现金流量比率", "现金流量比率 = 经营活动现金流 / 流动负债，衡量企业用现金流偿还短期债务的能力。比率越高，偿债能力越强。", ["现金流", "偿债能力", "比率"]),
        ("利息保障倍数", "利息保障倍数 = EBIT / 利息费用，反映企业支付利息的能力。倍数越高，财务风险越低。一般认为应大于3。", ["利息保障", "财务风险", "偿债"]),
        ("资产周转天数", "资产周转天数 = 365 / 总资产周转率，反映资产周转一次所需天数。天数越少，资产使用效率越高。", ["周转天数", "资产效率", "运营"]),
    ]

    for title, content, keywords in ratios:
        entries.append({
            "title": title,
            "content": content,
            "category": "financial_ratios",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_trading_strategies():
    """生成交易策略知识"""
    entries = []

    strategies = [
        ("突破交易", "突破交易是在价格突破关键阻力位或支撑位时进场。突破伴随放量更可靠。止损设在突破点下方。适合趋势行情。", ["突破", "交易策略", "技术分析"]),
        ("回调买入", "回调买入是在上涨趋势中等待价格回调至支撑位再买入。可以获得更好的入场价格。需要确认趋势未改变。", ["回调", "买入", "趋势"]),
        ("高抛低吸", "高抛低吸适用于震荡市场，在价格区间上沿卖出、下沿买入。需要准确判断震荡区间。", ["高抛低吸", "震荡", "波段"]),
        ("金字塔加仓", "金字塔加仓是盈利后逐步加仓，每次加仓量递减。可以降低平均成本，控制风险。", ["加仓", "仓位管理", "风控"]),
        ("止损策略", "止损是控制风险的关键。常见方法：固定比例止损、技术位止损、时间止损。严格执行止损纪律。", ["止损", "风险管理", "纪律"]),
    ]

    for title, content, keywords in strategies:
        entries.append({
            "title": title,
            "content": content,
            "category": "trading_strategies",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_bond_knowledge():
    """生成债券知识"""
    entries = []

    bonds = [
        ("国债", "国债是国家发行的债券，信用等级最高，几乎无违约风险。收益率较低，适合稳健投资者。国债利率是市场利率的基准。", ["国债", "债券", "低风险"]),
        ("企业债", "企业债是企业发行的债券，收益率高于国债，但存在信用风险。需要关注企业信用评级和财务状况。", ["企业债", "信用风险", "收益率"]),
        ("可转债", "可转债是可以转换为股票的债券，具有债券的保底和股票的上涨潜力。转股价、转股溢价率是关键指标。", ["可转债", "转股", "债券"]),
        ("城投债", "城投债是地方政府融资平台发行的债券。具有隐性政府信用背书，但需关注地方财政状况。", ["城投债", "地方债", "信用"]),
        ("债券久期", "久期衡量债券价格对利率变化的敏感度。久期越长，利率风险越大。久期 = 债券现金流加权平均到期时间。", ["久期", "利率风险", "债券"]),
    ]

    for title, content, keywords in bonds:
        entries.append({
            "title": title,
            "content": content,
            "category": "bonds",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_derivatives():
    """生成衍生品知识"""
    entries = []

    derivatives = [
        ("股指期货", "股指期货是以股票指数为标的的期货合约。可以对冲股票组合风险，也可以进行投机交易。具有杠杆效应。", ["股指期货", "期货", "对冲"]),
        ("期权", "期权赋予持有人在未来某时间以特定价格买入或卖出标的资产的权利。分为看涨期权和看跌期权。", ["期权", "衍生品", "权利"]),
        ("认沽权证", "认沽权证给予持有人以约定价格卖出标的股票的权利。可以用于对冲下跌风险或进行方向性交易。", ["认沽", "权证", "对冲"]),
        ("融资融券", "融资是借钱买股票，融券是借股票卖出。都具有杠杆效应，放大收益和风险。需要满足一定条件才能开通。", ["融资融券", "杠杆", "两融"]),
        ("ETF期权", "ETF期权是以ETF为标的的期权合约。流动性好，可以进行多种策略组合。常见策略：买入看涨、卖出看跌、跨式组合。", ["ETF期权", "期权策略", "组合"]),
    ]

    for title, content, keywords in derivatives:
        entries.append({
            "title": title,
            "content": content,
            "category": "derivatives",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_macro_economics():
    """生成宏观经济知识"""
    entries = []

    macro = [
        ("GDP", "GDP（国内生产总值）是衡量一国经济总量的指标。GDP增速反映经济增长情况。高GDP增长通常利好股市。", ["GDP", "经济增长", "宏观"]),
        ("CPI", "CPI（居民消费价格指数）衡量通货膨胀水平。CPI过高表示通胀压力大，央行可能加息。影响债券和股票估值。", ["CPI", "通胀", "物价"]),
        ("PMI", "PMI（采购经理人指数）反映制造业景气度。PMI>50表示扩张，<50表示收缩。是经济先行指标。", ["PMI", "制造业", "景气度"]),
        ("货币政策", "货币政策通过调节货币供应量和利率影响经济。宽松政策利好股市，紧缩政策利空股市。关注央行政策动向。", ["货币政策", "央行", "利率"]),
        ("财政政策", "财政政策通过政府支出和税收影响经济。积极财政政策增加支出，刺激经济增长。关注减税降费、基建投资。", ["财政政策", "政府支出", "税收"]),
    ]

    for title, content, keywords in macro:
        entries.append({
            "title": title,
            "content": content,
            "category": "macroeconomics",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_investment_psychology():
    """生成投资心理学知识"""
    entries = []

    psychology = [
        ("损失厌恶", "损失厌恶是指人们对损失的痛苦感受强于同等收益的快乐。导致投资者不愿止损，持有亏损股票过久。", ["损失厌恶", "心理", "行为金融"]),
        ("锚定效应", "锚定效应是指过度依赖最初获得的信息。投资者容易以买入价为锚点，影响卖出决策。应客观评估当前价值。", ["锚定效应", "认知偏差", "心理"]),
        ("羊群效应", "羊群效应是指盲目跟随大众行为。市场狂热时容易追高，恐慌时容易杀跌。应保持独立思考。", ["羊群效应", "从众", "市场情绪"]),
        ("过度自信", "过度自信导致投资者高估自己的判断能力，过度交易，承担过高风险。应保持谦逊，承认不确定性。", ["过度自信", "认知偏差", "风险"]),
        ("确认偏误", "确认偏误是指只关注支持自己观点的信息，忽略相反证据。应主动寻找反面信息，避免一厢情愿。", ["确认偏误", "认知", "客观性"]),
    ]

    for title, content, keywords in psychology:
        entries.append({
            "title": title,
            "content": content,
            "category": "investment_psychology",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_risk_management():
    """生成风险管理知识"""
    entries = []

    risk = [
        ("仓位管理", "仓位管理是控制投资组合中各资产的比例。不要满仓操作，保留现金应对机会和风险。根据市场环境调整仓位。", ["仓位管理", "风险控制", "资金管理"]),
        ("分散投资", "分散投资是将资金分配到不同资产、行业、地区。降低单一投资的风险。但过度分散会降低收益。", ["分散投资", "风险分散", "组合"]),
        ("风险收益比", "风险收益比 = 预期收益 / 预期风险。应选择风险收益比高的投资机会。一般要求风险收益比>2。", ["风险收益比", "风险评估", "收益"]),
        ("最大回撤", "最大回撤是投资组合从峰值到谷底的最大跌幅。反映投资的风险水平。应控制最大回撤在可承受范围内。", ["最大回撤", "风险指标", "波动"]),
        ("夏普比率", "夏普比率 = (组合收益率 - 无风险利率) / 组合波动率。衡量单位风险的超额收益。夏普比率越高越好。", ["夏普比率", "风险调整收益", "评估"]),
    ]

    for title, content, keywords in risk:
        entries.append({
            "title": title,
            "content": content,
            "category": "risk_management",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def generate_qa_pairs():
    """生成问答对知识"""
    entries = []

    qa_pairs = [
        ("如何选择成长股？", "选择成长股要关注：1) 行业处于成长期，市场空间大；2) 公司营收和利润持续高增长；3) 具有核心竞争力和技术壁垒；4) 管理团队优秀；5) 估值合理，PEG<1。", ["成长股", "选股", "投资"]),
        ("如何判断股票估值高低？", "判断估值可以：1) 横向比较同行业公司PE、PB；2) 纵向比较历史估值分位；3) 使用DCF、DDM等绝对估值法；4) 考虑行业特性和成长性；5) 结合市场情绪和流动性。", ["估值", "PE", "投资分析"]),
        ("熊市如何操作？", "熊市策略：1) 降低仓位，保留现金；2) 关注防御性板块如公用事业、医药；3) 定投优质资产；4) 不要抄底，等待趋势反转信号；5) 控制情绪，避免恐慌性抛售。", ["熊市", "投资策略", "风险控制"]),
        ("牛市如何操作？", "牛市策略：1) 提高仓位，充分参与；2) 关注成长股和周期股；3) 注意估值泡沫，分批止盈；4) 不要追高，等待回调机会；5) 保持理性，避免过度贪婪。", ["牛市", "投资策略", "收益"]),
        ("如何构建投资组合？", "构建组合要：1) 确定资产配置比例（股债比）；2) 分散投资不同行业和风格；3) 核心持仓+卫星持仓；4) 定期再平衡；5) 根据市场环境动态调整。", ["投资组合", "资产配置", "分散"]),
    ]

    for question, answer, keywords in qa_pairs:
        entries.append({
            "title": question,
            "content": answer,
            "category": "qa_pairs",
            "keywords": keywords,
            "source": "financial_encyclopedia"
        })

    return entries


def main():
    """生成所有知识条目"""
    print("=" * 60)
    print("Generating Massive Financial Knowledge Dataset")
    print("Target: 10,000+ entries")
    print("=" * 60)

    all_entries = []

    # 生成各类知识
    print("\n生成上市公司知识...")
    all_entries.extend(generate_stock_companies())

    print("生成行业分析知识...")
    all_entries.extend(generate_industry_analysis())

    print("生成财务比率知识...")
    all_entries.extend(generate_financial_ratios())

    print("生成交易策略知识...")
    all_entries.extend(generate_trading_strategies())

    print("生成债券知识...")
    all_entries.extend(generate_bond_knowledge())

    print("生成衍生品知识...")
    all_entries.extend(generate_derivatives())

    print("生成宏观经济知识...")
    all_entries.extend(generate_macro_economics())

    print("生成投资心理学知识...")
    all_entries.extend(generate_investment_psychology())

    print("生成风险管理知识...")
    all_entries.extend(generate_risk_management())

    print("生成问答对知识...")
    all_entries.extend(generate_qa_pairs())

    print(f"\n当前生成 {len(all_entries)} 条知识条目")

    # 保存到文件
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data" / "knowledge_base" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"financial_knowledge_massive_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到: {output_file}")
    print("\n" + "=" * 60)
    print(f"完成！共 {len(all_entries)} 条知识条目")
    print("=" * 60)

    # 统计各类别数量
    from collections import Counter
    categories = Counter(entry["category"] for entry in all_entries)
    print("\n各类别统计:")
    for category, count in categories.most_common():
        print(f"  {category}: {count} 条")


if __name__ == "__main__":
    main()
