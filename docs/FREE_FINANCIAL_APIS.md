# 免费金融API资源汇总

本文档整理了尽可能多的免费金融API，适用于金融资产问答系统的数据获取。

## 📊 股票市场数据 API

### 综合性股票数据平台

1. **Alpha Vantage** - [https://www.alphavantage.co/](https://www.alphavantage.co/)
   - 免费额度：25次请求/天
   - 数据类型：实时和历史股票数据、技术指标、基本面数据
   - 特点：技术指标库丰富，支持全球市场

2. **Finnhub** - [https://finnhub.io/](https://finnhub.io/)
   - 免费额度：60次请求/分钟
   - 数据类型：实时股票价格、新闻、ESG数据
   - 特点：慷慨的免费层级

3. **Twelve Data** - [https://twelvedata.com/](https://twelvedata.com/)
   - 免费额度：每日有限积分
   - 数据类型：实时和历史数据、技术指标、基本面数据
   - 特点：支持多种订阅层级

4. **Polygon.io** - [https://polygon.io/](https://polygon.io/)
   - 免费额度：5次请求/分钟，15分钟延迟数据
   - 数据类型：日终数据、历史数据
   - 特点：付费计划从$29/月起，提供实时数据

5. **Mboum API** - [https://www.mboum.com/](https://www.mboum.com/)
   - 数据类型：实时和历史价格、公司基本面、期权数据
   - 特点：全球股票市场覆盖，易于集成

6. **Eulerpool** - [https://eulerpool.com/financial-data-api](https://eulerpool.com/financial-data-api)
   - 免费提供：实时股票价格、公司基本面、财务报表
   - 数据类型：股票、固定收益、衍生品、外汇、商品、经济指标
   - 特点：专为AI代理和开发者构建

7. **Tiingo** - [https://www.tiingo.com/](https://www.tiingo.com/)
   - 免费提供：30+年股票数据
   - 数据类型：历史价格、基本面数据（免费用户5年，付费用户15+年）
   - 特点：数据覆盖全面

8. **Financial Modeling Prep (FMP)** - [https://site.financialmodelingprep.com/](https://site.financialmodelingprep.com/)
   - 数据类型：实时股票价格、财务报表、历史数据
   - 特点：100+个API端点，支持WebSocket和批量下载

9. **Yahoo Finance API (非官方)** - 通过yfinance库访问
   - 免费但不稳定：官方API已于2023年停用
   - 数据类型：股票价格、历史数据、基本面
   - 注意：可能被封锁，建议使用替代方案

## 💰 加密货币 API

1. **CoinGecko** - [https://www.coingecko.com/en/api](https://www.coingecko.com/en/api)
   - 免费提供：实时和历史价格、市场数据、元数据
   - 数据类型：币种和代币的价格、图片、描述、链接、社交统计、供应信息
   - 特点：最全面可靠的加密货币数据

2. **CoinMarketCap** - [https://coinmarketcap.com/api/](https://coinmarketcap.com/api/)
   - 数据类型：实时价格、市值、历史数据
   - 特点：全球第一的加密货币市场数据API

3. **LiveCoinWatch** - [https://www.livecoinwatch.com/tools/api](https://www.livecoinwatch.com/tools/api)
   - 100%免费
   - 每2秒更新一次
   - 10,000次请求/天
   - 8+年价格历史

4. **Coinlore** - [https://coinlore.com/cryptocurrency-data-api](https://coinlore.com/cryptocurrency-data-api)
   - 完全免费，无需注册
   - 数据类型：实时加密货币市场数据
   - 特点：为开发者和研究项目提供可靠独立数据

5. **DIA** - [https://www.diadata.org/free-crypto-api/](https://www.diadata.org/free-crypto-api/)
   - 免费提供：3,000+代币的实时市场价格数据
   - 特点：为Web3和Web2用例设计

6. **CoinAPI.io** - [https://www.coinapi.io/](https://www.coinapi.io/)
   - 数据类型：400+交易所的实时和历史市场数据
   - 特点：统一的低延迟API

7. **Coinlayer** - [https://coinlayer.com/](https://coinlayer.com/)
   - 数据类型：实时加密货币汇率
   - 覆盖：25个交易所，385+币种

8. **FreeCryptoAPI** - [https://freecryptoapi.com/](https://freecryptoapi.com/)
   - 数据类型：实时价格、历史数据、技术分析
   - 特点：可靠、可扩展、免费启动

9. **Abyiss Crypto API** - [https://abyiss.com/crypto-api](https://abyiss.com/crypto-api)
   - 免费访问：100+交易所，100,000+资产
   - 数据类型：实时和历史数据

## 💱 外汇/货币汇率 API

1. **Frankfurter** - [https://frankfurter.dev/](https://frankfurter.dev/)
   - 100%免费开源
   - 数据来源：欧洲央行等机构发布的参考汇率
   - 历史数据：1999年至今

2. **FreeCurrencyAPI** - [https://freecurrencyapi.com/](https://freecurrencyapi.com/)
   - 100%免费
   - 数据类型：实时和历史汇率
   - 历史数据：1999年至今

3. **ExchangeRatesAPI** - [https://exchangeratesapi.io/](https://exchangeratesapi.io/)
   - 数据类型：实时和历史货币数据
   - 更新频率：每60秒
   - 覆盖：数百种全球货币

4. **CurrencyAPI.net** - [https://currencyapi.net/](https://currencyapi.net/)
   - 免费额度：500次请求/月
   - 特点：低延迟JSON，稳定平台

5. **CurrencyAPI.com** - [https://currencyapi.com/](https://currencyapi.com/)
   - 覆盖：150+世界货币和加密货币

6. **ForexRateAPI** - [https://forexrateapi.com/](https://forexrateapi.com/)
   - 数据类型：实时和历史外汇汇率
   - 覆盖：150+世界货币

7. **MoneyConvert API** - [https://www.moneyconvert.net/api/](https://www.moneyconvert.net/api/)
   - 免费JSON API
   - 覆盖：181+货币的实时汇率
   - 无需认证，每5分钟更新

8. **UnirateAPI** - [http://unirateapi.com/](http://unirateapi.com/)
   - 免费提供：593种实时和历史外汇汇率、贵金属价格、欧盟增值税率
   - 历史数据：商品数据自1968年，外汇自1999年，加密货币自比特币诞生

9. **Fixer.io** - [https://fixer.io/](https://fixer.io/)
   - 数据类型：实时汇率和货币转换
   - 特点：6+年经验，数据源可靠

## 📈 经济指标 API

1. **FRED (Federal Reserve Economic Data)** - [https://fred.stlouisfed.org/](https://fred.stlouisfed.org/)
   - 免费提供：816,000+美国和国际时间序列数据
   - 数据来源：108个来源
   - 数据类型：GDP、失业率、通胀、利率等
   - Python库：fredapi

2. **Financial Modeling Prep - Economics** - [https://www.financialmodelingprep.com/datasets/economics](https://www.financialmodelingprep.com/datasets/economics)
   - 数据类型：宏观经济指标（CPI、GDP、失业率等）

3. **API Ninjas - Inflation API** - [https://www.api-ninjas.com/api/inflation](https://www.api-ninjas.com/api/inflation)
   - 数据类型：38个主要国家的当前经济通胀数据
   - 更新频率：通常每月更新

4. **Pineify Economic Indicators** - [https://pineify.app/economic-indicators](https://pineify.app/economic-indicators)
   - 免费提供：GDP、CPI、失业率、利率等
   - 特点：查看历史数据、比较趋势、导出分析

5. **Quandl** - [https://www.quandl.com/](https://www.quandl.com/)
   - 统一数据源：世界银行、联合国、欧盟统计局、亚洲开发银行、BEA、BLS、FRED等
   - 数据类型：经济数据、利率数据
   - 特点：单一易用的强大经济数据API

6. **Truflation** - [https://truflation.com/](https://truflation.com/)
   - 数据类型：实时CPI、通胀组成部分、宏观指标
   - 特点：透明、无偏见的数据源

## 🛢️ 商品/大宗商品 API

1. **Commodities-API** - [https://commodities-api.com/](https://commodities-api.com/)
   - 数据类型：原油、黄金、白银、咖啡等实时和历史价格

2. **CommodityPriceAPI** - [https://commoditypriceapi.com/](https://commoditypriceapi.com/)
   - 数据类型：130+商品的实时和历史汇率
   - 历史数据：可追溯至1990年1月1日
   - 格式：简单JSON格式

3. **OilPriceAPI** - [https://www.oilpriceapi.com/](https://www.oilpriceapi.com/)
   - 免费提供：WTI、布伦特、天然气数据
   - 数据类型：实时原油价格、天然气、贵金属、50+能源和农产品商品
   - 无需注册

4. **Omkar Cloud Commodity Price API** - [https://www.omkar.cloud/tools/commodity-price-api](https://www.omkar.cloud/tools/commodity-price-api)
   - 免费额度：5,000次查询/月
   - 数据类型：商品期货价格（黄金、白银、原油、咖啡等25+种）
   - 来源：CME和NYMEX，以美元计价

5. **AllTick Futures API** - [https://alltick.co/futures-api](https://alltick.co/futures-api)
   - 数据类型：贵金属（黄金、白银）和能源（原油、天然气）的高频tick数据

6. **FinanceFlow Commodities** - [https://financeflowapi.com/commodities](https://financeflowapi.com/commodities)
   - 数据类型：金属、能源、农产品的实时价格

## 📑 债券/固定收益 API

1. **U.S. Treasury Fiscal Data** - [https://fiscaldata.treasury.gov/api-documentation/](https://fiscaldata.treasury.gov/api-documentation/)
   - 免费提供：美国财政部官方数据
   - 数据类型：国债利率、财政数据
   - 格式：CSV、JSON、XML

2. **Financial Modeling Prep - Treasury Rates** - [http://www.financialmodelingprep.com/developer/docs/stable/treasury-rates](http://www.financialmodelingprep.com/developer/docs/stable/treasury-rates)
   - 数据类型：所有期限的国债利率实时和历史数据
   - 特点：美国政府债务利率

3. **FinanceFlow Government Bonds** - [https://financeflowapi.com/government-bonds](https://financeflowapi.com/government-bonds)
   - 数据类型：50+国家的债券实时收益率（包括美国国债、德国国债）
   - 更新频率：每分钟更新
   - 覆盖：国债、票据、短期国库券

4. **EODHD US Treasury Interest Rates API** - [https://eodhd.com/financial-apis/us-treasury-ust-interest-rates-api-beta](https://eodhd.com/financial-apis/us-treasury-ust-interest-rates-api-beta)
   - 数据类型：短期国库券利率、长期利率、收益率、实际收益率
   - 特点：支持按年份过滤

5. **Quandl Interest Rate Data** - [https://blog.quandl.com/api-for-interest-rate-data](https://blog.quandl.com/api-for-interest-rate-data)
   - 数据类型：短期货币市场利率、长期债券收益率、商业票据利率、公司债券利率

6. **Cbonds Bond API** - [https://cbonds.com/api/bonds/](https://cbonds.com/api/bonds/)
   - 数据类型：债券价格、历史价格、基本面数据、公司行动

7. **Exanomic** - [https://exanomic.com/](https://exanomic.com/)
   - 数据类型：债券市场数据和经济指标
   - 特点：统一API

## 📰 财经新闻与情绪分析 API

1. **Marketaux** - [https://www.marketaux.com/](https://www.marketaux.com/)
   - 免费提供：全球股市和金融新闻
   - 数据类型：股票、基金、加密货币、外汇新闻及综合情绪分析
   - 覆盖：200,000+实体，5,000+新闻源

2. **StockNewsAPI** - [https://stocknewsapi.com/](https://stocknewsapi.com/)
   - 数据类型：最新股市新闻
   - 格式：JSON API
   - 特点：清洁相关的股市新闻数据

3. **EODHD Financial News API** - [https://eodhd.com/financial-apis/stock-market-financial-news-api](https://eodhd.com/financial-apis/stock-market-financial-news-api)
   - 数据类型：财经新闻源和股票新闻情绪数据
   - 覆盖：5,000+来源，30+语言

4. **StockData.org** - [https://www.stockdata.org/](https://www.stockdata.org/)
   - 数据类型：实时、日内、历史股票数据
   - 新闻覆盖：5,000+来源，30+语言，情绪分析

5. **StockGeist** - [https://www.stockgeist.ai/stock-market-api/](https://www.stockgeist.ai/stock-market-api/)
   - 数据类型：股票情绪数据
   - 特点：灵活易用，可集成到各种应用

6. **Eulerpool Financial Data API** - [https://eulerpool.com/financial-data-api](https://eulerpool.com/financial-data-api)
   - 免费提供：实时和历史新闻数据

## 📊 公司基本面与财务报表 API

1. **SEC Financial Data API (FundamentalsAPI)** - [https://fundamentalsapi.com/](https://fundamentalsapi.com/)
   - 免费提供：5,000+美国公司的SEC财务数据
   - 数据类型：损益表、资产负债表、现金流量表、财务比率
   - 格式：简单JSON API

2. **Eulerpool Fundamentals Data** - [https://eulerpool.com/financial-data-api/fundamentals-data](https://eulerpool.com/financial-data-api/fundamentals-data)
   - 数据类型：损益表、资产负债表、现金流量表、财务比率、SEC文件、盈利预测
   - 特点：时点数据，支持GAAP和IFRS

3. **Financial Modeling Prep - Fundamentals** - [http://www.financialmodelingprep.com/datasets/fundamental-financial-statements](http://www.financialmodelingprep.com/datasets/fundamental-financial-statements)
   - 数据类型：详细的损益表、资产负债表、现金流量表
   - 特点：快速、开发者友好的端点

4. **Twelve Data Fundamentals** - [https://twelvedata.com/fundamentals](https://twelvedata.com/fundamentals)
   - 数据类型：盈利数据（EPS预估和实际值）
   - 覆盖：公司完整历史

5. **Alpha Vantage** - [https://www.alphavantage.co/](https://www.alphavantage.co/)
   - 数据类型：基本面数据、财务报表
   - 免费额度：500次调用/天，最多5次/分钟

6. **Intrinio (Stanford Academic Portal)** - [https://stanford.intrinio.com/](https://stanford.intrinio.com/)
   - 数据类型：标准化财务数据、基本面数据
   - 特点：为学术用户提供免费访问

## 📈 ETF与共同基金 API

1. **Financial Modeling Prep - ETF & Mutual Funds** - [https://financialmodelingprep.com/datasets/etf-mutual-funds](https://financialmodelingprep.com/datasets/etf-mutual-funds)
   - 数据类型：持仓、资产和行业配置、官方文件和披露
   - 特点：结构化数据，易于集成

2. **API Ninjas - Mutual Fund API** - [https://api-ninjas.com/api/mutualfund](https://api-ninjas.com/api/mutualfund)
   - 数据类型：共同基金价格、持仓、费用率、管理资产、关键指标

3. **Twelve Data ETF APIs** - [https://twelvedata.com/etf](https://twelvedata.com/etf)
   - 数据类型：实时和历史ETF及共同基金数据
   - 特点：通过单一JSON API访问全球ETF数据

4. **Cbonds ETF API** - [https://cbonds.com/api/etf](https://cbonds.com/api/etf)
   - 数据类型：基金基本信息、描述信息（名称、国家、货币、基准）、ETF或共同基金持仓

5. **Pineify ETF Holdings** - [https://pineify.app/etf-fund-holdings](https://pineify.app/etf-fund-holdings)
   - 免费工具：按股票代码查找ETF或共同基金
   - 数据类型：持有的每项资产、权重百分比、股份数量、市值

6. **FastTrack API** - [https://fasttrack.net/api](https://fasttrack.net/api)
   - 数据类型：共同基金、ETF、股票、指数的日终定价数据
   - 参考数据：费用率、前十大持仓、名称、股份类别

## 🔔 财经日历 API（IPO、分红、财报）

1. **EODHD Calendar API** - [https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits](https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits)
   - 数据类型：即将到来的分红、财报、趋势、IPO、股票拆分
   - 交易所API：交易时间、股市假期、股票代码变更历史

2. **Financial Modeling Prep - Calendars** - [https://intelligence.financialmodelingprep.com/datasets/calendars](https://intelligence.financialmodelingprep.com/datasets/calendars)
   - 数据类型：财报、分红、IPO等预定财经事件
   - 特点：结构化数据，适合构建警报系统、研究仪表板、自动化策略

3. **Pineify Market Calendar** - [https://pineify.app/market-calendar](https://pineify.app/market-calendar)
   - 免费提供：2026年市场日历
   - 数据类型：财报、分红日期、经济事件、IPO、股票拆分
   - 特点：统一日历，实时数据

4. **Mboum API - Calendar Events** - [https://www.mboum.com/blogs/how-to-track-dividends-splits-and-ipos-using-the-mboum-api](https://www.mboum.com/blogs/how-to-track-dividends-splits-and-ipos-using-the-mboum-api)
   - 数据类型：分红时间表、股票拆分历史、IPO日历
   - 特点：专用端点，程序化跟踪

5. **SteadyAPI - Calendar Events** - [https://steadyapi.com/blogs/how-to-track-dividends-splits-and-public-offerings-using-steadyapi](https://steadyapi.com/blogs/how-to-track-dividends-splits-and-public-offerings-using-steadyapi)
   - 数据类型：分红、股票拆分、公开发行
   - 日期格式：YYYY-MM-DD

6. **Earnings Calendar Net** - [https://earningscalendar.net/](https://earningscalendar.net/)
   - 覆盖：2010年至未来90天
   - 更新：实时更新

## 📊 技术指标 API

1. **Alpha Vantage** - [https://www.alphavantage.co/documentation/](https://www.alphavantage.co/documentation/)
   - 数据类型：丰富的技术指标库（SMA、EMA、RSI、MACD、布林带等）
   - 免费额度：25次请求/天
   - 特点：技术指标是其核心优势

2. **Indictr** - [https://indictr.com/](https://indictr.com/)
   - 数据类型：预计算的RSI、MACD、布林带等
   - 特点：一次API调用，JSON响应，无需数学库

3. **Mboum Indicators API** - [https://www.mboum.com/blogs/how-to-calculate-sma-ema-rsi-and-macd-using-the-mboum-indicators-ap](https://www.mboum.com/blogs/how-to-calculate-sma-ema-rsi-and-macd-using-the-mboum-indicators-ap)
   - 数据类型：预计算的SMA、EMA、RSI、MACD
   - 特点：卸载计算负担，直接获取技术分析数据

4. **SteadyAPI Indicators** - [https://steadyapi.com/blogs/how-to-calculate-sma-ema-rsi-and-macd-using-steadyapi-indicators](https://steadyapi.com/blogs/how-to-calculate-sma-ema-rsi-and-macd-using-steadyapi-indicators)
   - 数据类型：SMA、EMA、RSI、MACD的清洁预计算值
   - 特点：无需本地处理原始K线数据

5. **Python technical-indicator库** - [https://pypi.org/project/technical-indicator/](https://pypi.org/project/technical-indicator/)
   - 数据类型：动量指标、趋势指标、波动率指标、成交量指标
   - 特点：从金融时间序列数据集计算各种技术指标

## 📊 期权与衍生品 API

1. **Eulerpool Options & Futures Data** - [https://eulerpool.com/financial-data-api/options-futures-data](https://eulerpool.com/financial-data-api/options-futures-data)
   - 数据类型：完整期权链数据、实时希腊字母、隐含波动率曲面、期货期限结构曲线
   - 特点：为衍生品交易者和量化研究者构建

2. **ThetaData** - [https://www.thetadata.net/](https://www.thetadata.net/)
   - 数据类型：期权、股票市场数据
   - 特点：API访问

3. **CME Group WebSocket API** - [https://www.cmegroup.com/market-data/real-time-futures-and-options-data-api.html](https://www.cmegroup.com/market-data/real-time-futures-and-options-data-api.html)
   - 数据类型：实时期货和期权数据（顶级价格、交易信息、市场统计）
   - 特点：从云端直接流式传输到系统

4. **MarketData.app Options** - [https://www.marketdata.app/data/options/](https://www.marketdata.app/data/options/)
   - 数据类型：完整期权链、实时或历史数据
   - 特点：复杂过滤、强大的期权API

5. **Polygon.io Options** - [https://polygon.io/options](https://polygon.io/options)
   - 数据类型：实时期权价格、历史数据、新闻
   - 覆盖：CBOE、NYSE、NASDAQ等主要期权市场

6. **Alpha Vantage** - [https://www.alphavantage.co/](https://www.alphavantage.co/)
   - 数据类型：美国期权数据
   - 免费额度：25次请求/天

7. **Databento** - [https://databento.com/options](https://databento.com/options)
   - 数据类型：实时和历史期权数据API

## 🏢 内幕交易与机构持仓 API

1. **SEC-API.io Insider Trading** - [https://sec-api.io/docs/insider-ownership-trading-api](https://sec-api.io/docs/insider-ownership-trading-api)
   - 数据类型：SEC Form 3、4、5文件的内幕交易数据
   - 特点：搜索和列出所有美国上市公司的内幕买卖交易

2. **SEC-API.io Form 13F** - [https://sec-api.io/docs/form-13-f-filings-institutional-holdings-api](https://sec-api.io/docs/form-13-f-filings-institutional-holdings-api)
   - 数据类型：SEC注册基金和投资经理的当前和历史投资组合持仓
   - 信息：发行人名称、证券类别、CUSIP、CIK、股票代码

3. **API Ninjas - Insider Trading API** - [https://api-ninjas.com/api/insidertrading](https://api-ninjas.com/api/insidertrading)
   - 数据类型：SEC文件（Form 3、4、5）的综合内幕交易数据
   - 特点：按公司、内幕人士、交易类型、日期范围搜索和过滤

4. **Kscope Financial Data API** - [https://docs.kscope.io/](https://docs.kscope.io/)
   - 数据类型：18M+ SEC文件、13F机构持仓、内幕交易
   - 特点：实时更新、高级过滤、30+年历史数据

5. **Mboum API - SEC Filings** - [https://mboum.com/blogs/how-to-pull-sec-filings-insider-transactions-via-mboum-api](https://mboum.com/blogs/how-to-pull-sec-filings-insider-transactions-via-mboum-api)
   - 数据类型：内幕交易、机构持仓、实时SEC文件
   - 特点：清洁的JSON格式数据，无需解析原始文档

6. **Findl Holdings API** - [https://findl.com/docs/holdings](https://findl.com/docs/holdings)
   - 数据来源：SEC Form 13F文件
   - 数据类型：中大型机构投资经理的美国证券持仓详情

7. **Pineify SEC Filings Extract** - [https://pineify.app/filings-extract](https://pineify.app/filings-extract)
   - 免费工具：提取13F机构所有权数据
   - 要求：管理资产超过1亿美元的机构投资经理

8. **SECForm4.com** - [https://www.secform4.com/](https://www.secform4.com/)
   - 数据类型：内幕交易、机构持仓、Schedule 13D/13G文件
   - 特点：实时监控SEC EDGAR文件

## 🌍 国际组织经济数据 API

1. **World Bank API** - 通过Quandl访问
   - 数据类型：全球发展指标、公共部门债务数据
   - 特点：世界银行和IMF联合开发

2. **IMF Data** - 通过Quandl访问
   - 数据类型：多个指标和国家的宏观经济数据
   - 访问方式：Quandl API包装器

3. **Quandl Economic Data** - [https://blog.quandl.com/api-for-economic-data](https://blog.quandl.com/api-for-economic-data)
   - 统一数据源：世界银行、联合国、欧盟统计局、亚洲开发银行、BEA、BLS、FRED等
   - 特点：单一易用的强大经济数据API

## 📊 综合对比：主流免费API

| API名称 | 免费额度 | 主要优势 | 数据类型 |
|---------|----------|----------|----------|
| **Alpha Vantage** | 25次/天 | 技术指标丰富 | 股票、外汇、加密货币、技术指标 |
| **Finnhub** | 60次/分钟 | 免费额度慷慨 | 股票、新闻、ESG |
| **Twelve Data** | 有限积分/天 | 全球市场覆盖 | 股票、外汇、加密货币、ETF |
| **Polygon.io** | 5次/分钟（延迟15分钟） | 数据质量高 | 股票、期权、外汇 |
| **FRED** | 无限制 | 官方权威数据 | 经济指标 |
| **CoinGecko** | 慷慨免费层 | 加密货币最全 | 加密货币价格、市场数据 |
| **Frankfurter** | 无限制 | 完全免费开源 | 外汇汇率 |
| **Eulerpool** | 免费层 | 多资产类别 | 股票、债券、衍生品、商品 |

## 💡 使用建议

### 1. 数据源选择策略
- **股票实时数据**：优先考虑Finnhub（免费额度大）或Alpha Vantage（技术指标丰富）
- **历史数据**：Tiingo（30+年数据）或Alpha Vantage
- **加密货币**：CoinGecko或Coinlore（无需注册）
- **外汇**：Frankfurter（完全免费）或FreeCurrencyAPI
- **经济指标**：FRED（官方权威）或Quandl（多源统一）
- **公司基本面**：FundamentalsAPI（SEC数据）或FMP
- **新闻情绪**：Marketaux或StockNewsAPI

### 2. API限制应对
- **速率限制**：实现请求缓存和速率限制器
- **数据延迟**：免费层通常有15分钟延迟，适合非实时应用
- **多源备份**：为关键数据配置多个API源，提高可靠性

### 3. 成本优化
- **混合使用**：根据不同数据类型选择最优免费API
- **本地缓存**：缓存历史数据，减少API调用
- **批量请求**：尽可能使用批量端点减少请求次数

### 4. 数据质量
- **交叉验证**：关键数据使用多个源交叉验证
- **异常检测**：实现数据质量检查机制
- **更新频率**：了解各API的数据更新频率

## 📚 参考资源

### 综合指南
- [Best Stock Market APIs (2026 Guide)](https://steadyapi.com/blogs/best-stock-market-apis-2026-guide)
- [10+ Best Real-Time Stock Data APIs (2026)](https://steadyapi.com/blogs/10-best-real-time-stock-data-apis-2026)
- [Best Financial Data APIs in 2026](https://www.nb-data.com/p/best-financial-data-apis-in-2026)
- [Polygon vs IEX Cloud vs Alpha Vantage (2026)](https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/)

### 加密货币
- [Free Cryptocurrency API](https://freecryptoapi.com/)
- [Best 13 Crypto APIs](https://www.abstractapi.com/guides/other/best-crypto-currency-apis)

### 外汇
- [Free exchange rates API](https://frankfurter.dev/)
- [Currency Conversion API](https://freecurrencyapi.com/)

### 经济数据
- [FRED API Documentation](https://fred.stlouisfed.org/)
- [Quandl Economic Data](https://blog.quandl.com/api-for-economic-data)

### 技术实现
- [Python fredapi](https://github.com/mortada/fredapi)
- [Python technical-indicator](https://pypi.org/project/technical-indicator/)

---

**最后更新**: 2026-03-07

**注意事项**:
1. 免费API的限制和条款可能随时变化，使用前请查看最新文档
2. 部分API需要注册获取API密钥
3. 生产环境建议配置多个数据源以提高可靠性
4. 注意遵守各API的使用条款和速率限制
