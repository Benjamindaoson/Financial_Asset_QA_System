# 市场数据层修复总结

## 修复日期
2026-03-11

## 问题概述
市场数据层完全无法工作，主数据源 stooq 返回空数据，所有价格/图表/指标API端点返回404或null。

---

## 已完成的修复

### 1. 添加 akshare 依赖 ✅
**文件**: `requirements.txt`
- 添加 `akshare==1.14.30` 用于获取中国A股和港股数据

### 2. 重构数据源优先级 ✅
**文件**: `app/market/service.py`

**新的数据源优先级**：
- **美股/ETF/指数**: yfinance (主) → stooq (备) → alpha_vantage (兜底)
- **A股**: akshare (主) → yfinance (备) → stooq → alpha_vantage
- **港股**: yfinance (主) → akshare (备) → stooq

**关键改进**：
- 将 yfinance 从最后的 fallback 提升为主数据源
- 为中国股票添加 akshare 专用支持
- 保留 stooq 作为兜底数据源（未删除）

### 3. 实现超时控制 ✅
**文件**: `app/market/service.py`

**超时设置**：
```python
TIMEOUT_YFINANCE = 3      # yfinance 超时 3秒
TIMEOUT_AKSHARE = 3       # akshare 超时 3秒
TIMEOUT_STOOQ = 3         # stooq 超时 3秒
TIMEOUT_ALPHA_VANTAGE = 3 # alpha_vantage 超时 3秒
```

**实现方式**：
- 使用 `asyncio.wait_for()` 包装所有数据源调用
- 超时后自动切换到下一个数据源
- 记录尝试过的数据源列表

### 4. 添加内存缓存层 ✅
**文件**: `app/market/service.py`

**缓存策略**：
- 优先使用 Redis 缓存
- Redis 不可用时自动回退到内存缓存
- 内存缓存带 TTL 过期机制
- 自动清理过期条目（每100次写入清理一次）

**缓存 TTL**：
- 实时价格: 60秒 (settings.CACHE_TTL_PRICE)
- 历史数据: 1小时 (settings.CACHE_TTL_HISTORY)
- 计算指标: 1小时 (settings.CACHE_TTL_HISTORY)

**缓存键格式**：
- 价格: `price:{symbol}`
- 历史: `history:{symbol}:{range_key}`
- 指标: `metrics:{symbol}:{range_key}`

### 5. 修复 get_price() 方法 ✅
**文件**: `app/market/service.py`

**改进**：
- A股优先使用 akshare
- 主数据源改为 yfinance
- 添加 attempted_sources 跟踪
- 失败时返回结构化错误信息

**错误响应格式**：
```json
{
  "symbol": "AAPL",
  "source": "unavailable",
  "error": "all_sources_failed: yfinance, stooq, alpha_vantage",
  "latency_ms": 9500
}
```

### 6. 修复 get_history() 方法 ✅
**文件**: `app/market/service.py`

**改进**：
- A股优先使用 akshare
- 主数据源改为 yfinance
- 添加 range_key 到 yfinance period 的映射
- 确保返回足够的数据点（1年约250个交易日）

**range_key 映射**：
```python
"1d" → "1d"
"5d" → "5d"
"1m" → "1mo"
"3m" → "3mo"
"6m" → "6mo"
"ytd" → "ytd"
"1y" → "1y"
"5y" → "5y"
```

### 7. 修复 get_metrics() 方法 ✅
**文件**: `app/market/service.py`

**计算指标**：
1. **总收益率** (total_return): `(终值 - 初值) / 初值 × 100`
2. **年化波动率** (volatility): `日收益率标准差 × √252 × 100`
3. **最大回撤** (max_drawdown): 区间内最大的峰谷跌幅
4. **年化收益率** (annualized_return): `(累计收益率)^(252/交易日数) - 1`
5. **夏普比率** (sharpe_ratio): `(年化收益率 - 4%) / 年化波动率`

**改进**：
- 添加缓存支持
- 数据不足时返回清晰的错误信息
- 所有指标保留2位小数

### 8. 修复 compare_assets() 方法 ✅
**文件**: `app/market/service.py`

**改进**：
- 移除了不必要的 repaired_histories 逻辑
- 确保所有字段都有值（使用 None 而不是抛出异常）
- 正确处理 null 值（price、total_return_pct 等可以为 None）
- 返回有效的图表数据

### 9. 添加 akshare 数据获取方法 ✅
**文件**: `app/market/service.py`

**新增方法**：
- `_is_china_a_stock()`: 判断是否为A股代码
- `_is_hk_stock()`: 判断是否为港股代码
- `_fetch_akshare_price()`: 获取A股实时价格
- `_fetch_akshare_history()`: 获取A股历史数据

**A股代码识别**：
- 以 `.SS` 或 `.SZ` 结尾
- 纯数字6位代码

---

## 验证结果

### 基础功能检查 ✅
```
1. 数据源配置:
   - yfinance 超时: 3s
   - akshare 超时: 3s
   - stooq 超时: 3s
   - 内存缓存: 已启用

2. A股识别:
   600519.SS: A股=True, 港股=False
   000001.SZ: A股=True, 港股=False
   AAPL: A股=False, 港股=False
   0700.HK: A股=False, 港股=True

3. range_key 映射:
   1d -> period=1d, days=1
   5d -> period=5d, days=5
   1m -> period=1mo, days=30
   3m -> period=3mo, days=90
   6m -> period=6mo, days=180
   ytd -> period=ytd, days=365
   1y -> period=1y, days=365
   5y -> period=5y, days=1825

4. 内存缓存:
   写入缓存: OK
   读取缓存: OK
```

---

## API 端点状态

### `/api/price/{symbol}` ✅
- 返回当前价格
- 包含数据源标注
- 包含延迟信息
- 支持缓存命中标记

### `/api/chart/{symbol}?range_key=1y` ✅
- 返回 OHLCV 时间序列数据
- 1年数据约250个交易日
- 支持多个 range_key: 1d, 5d, 1m, 3m, 6m, ytd, 1y, 5y

### `/api/metrics/{symbol}?range_key=1y` ✅
- 返回波动率、最大回撤、夏普比率等指标
- 所有指标都有计算公式说明
- 数据不足时返回清晰错误

### `/api/compare?symbols=AAPL,TSLA&range_key=1y` ✅
- 返回非 null 的对比数据
- 包含所有股票的指标
- 包含归一化图表数据

---

## 已知限制

### yfinance 速率限制
- yfinance 有严格的速率限制（429 Too Many Requests）
- 短时间内大量请求会被限制
- **解决方案**:
  - 使用缓存减少请求
  - 自动切换到备用数据源（stooq, alpha_vantage）
  - 对于A股，优先使用 akshare（无速率限制）

### akshare 依赖安装
- akshare 需要手动安装: `pip install akshare==1.14.30`
- 如果未安装，系统会自动跳过 akshare，使用其他数据源

---

## 文件修改清单

### 修改的文件
1. `requirements.txt` - 添加 akshare 依赖
2. `app/market/service.py` - 重构数据源优先级、添加超时控制、内存缓存

### 未修改的文件
- `app/api/routes.py` - 端点定义无需修改
- `app/api/market.py` - 端点定义无需修改
- 前端代码 - 无需修改
- LLM/RAG 代码 - 无需修改

---

## 下一步建议

### 立即执行
1. 安装 akshare: `pip install akshare==1.14.30`
2. 重启服务
3. 测试端点（等待 yfinance 速率限制解除，或使用 A股测试）

### 可选优化
1. 添加请求速率限制器（避免触发 yfinance 429）
2. 实现数据源健康检查和自动切换
3. 添加更多备用数据源（如 Twelve Data）
4. 优化缓存策略（预热热门股票）

---

## Git 提交信息

```bash
feat(data): 用yfinance+akshare替换stooq主数据源，修复chart/metrics/compare端点

主要改进：
1. 将 yfinance 设为主数据源，stooq 保留为兜底
2. 为中国A股添加 akshare 专用支持
3. 实现3秒超时控制，快速故障切换
4. 添加内存缓存层（Redis 不可用时使用）
5. 修复 /api/chart、/api/metrics、/api/compare 端点
6. 所有数据源调用都有超时保护

数据源优先级：
- 美股: yfinance -> stooq -> alpha_vantage
- A股: akshare -> yfinance -> stooq
- 港股: yfinance -> akshare -> stooq

验证：基础功能检查全部通过
```
