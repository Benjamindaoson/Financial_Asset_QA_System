/**
 * 数据格式化工具函数
 */

// 列名中英文映射
export const COLUMN_LABELS = {
  // 通用字段
  symbol: "代码",
  name: "名称",
  price: "价格",
  metric: "指标",
  value: "数值",

  // 收益指标
  total_return_pct: "总收益",
  annualized_return_pct: "年化收益",
  change_pct: "涨跌幅",

  // 风险指标
  annualized_volatility: "年化波动率",
  max_drawdown_pct: "最大回撤",
  sharpe_ratio: "夏普比率",

  // 估值指标
  pe_ratio: "市盈率",
  pb_ratio: "市净率",
  market_cap: "市值",

  // 技术指标
  rsi: "RSI",
  macd: "MACD",
  ma5: "5日均线",
  ma20: "20日均线",

  // 其他
  range: "区间",
  date: "日期",
  volume: "成交量",
  sector: "行业",
  industry: "细分行业",
  unit: "单位",
  timestamp: "时间戳",
  source: "来源",
};

// 货币/单位中文映射（表格 unit 列显示）
export const UNIT_LABELS = {
  USD: "美元",
  CNY: "人民币",
  HKD: "港币",
  EUR: "欧元",
  GBP: "英镑",
  "%": "%",
  "": "",
};

// 指标中文映射（用于表格行）
export const METRIC_LABELS = {
  total_return_pct: "总收益",
  annualized_return_pct: "年化收益",
  annualized_volatility: "年化波动率",
  max_drawdown_pct: "最大回撤",
  sharpe_ratio: "夏普比率",
  range: "区间",
  metric: "指标",
  value: "数值",
  latest_price: "最新价格",
  interval_change_pct: "区间涨跌",
  trend: "走势",
  asset_name: "资产名称",
};

/**
 * 格式化百分比
 */
export function formatPercent(value, decimals = 2, showSign = true) {
  if (value === null || value === undefined || value === "N/A") {
    return "N/A";
  }

  const num = typeof value === "string" ? parseFloat(value.replace("%", "")) : value;
  if (isNaN(num)) return "N/A";

  const sign = showSign && num > 0 ? "+" : "";
  return `${sign}${num.toFixed(decimals)}%`;
}

/**
 * 格式化货币
 */
export function formatCurrency(value, currency = "$", decimals = 2) {
  if (value === null || value === undefined || value === "N/A") {
    return "N/A";
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";

  return `${currency}${num.toFixed(decimals)}`;
}

/**
 * 格式化数字（带千分位）
 */
export function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || value === "N/A") {
    return "N/A";
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";

  return num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * 格式化市值（转换为亿、万亿）
 */
export function formatMarketCap(value) {
  if (value === null || value === undefined || value === "N/A") {
    return "N/A";
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";

  if (num >= 1e12) {
    return `$${(num / 1e12).toFixed(2)}T`;
  } else if (num >= 1e9) {
    return `$${(num / 1e9).toFixed(2)}B`;
  } else if (num >= 1e6) {
    return `$${(num / 1e6).toFixed(2)}M`;
  }
  return `$${num.toFixed(0)}`;
}

/**
 * 获取涨跌颜色
 */
export function getChangeColor(value) {
  if (value === null || value === undefined || value === "N/A") {
    return "#64748B"; // 灰色
  }

  const num = typeof value === "string" ? parseFloat(value.replace("%", "")) : value;
  if (isNaN(num)) return "#64748B";

  if (num > 0) return "#16A34A"; // 绿色（涨）
  if (num < 0) return "#DC2626"; // 红色（跌）
  return "#64748B"; // 灰色（平）
}

/**
 * 获取趋势图标
 */
export function getTrendIcon(value) {
  if (value === null || value === undefined || value === "N/A") {
    return "—";
  }

  const num = typeof value === "string" ? parseFloat(value.replace("%", "")) : value;
  if (isNaN(num)) return "—";

  if (num > 0) return "↑";
  if (num < 0) return "↓";
  return "—";
}

/**
 * 智能格式化单元格值
 */
export function formatCellValue(value, columnKey) {
  // 处理空值
  if (value === null || value === undefined || value === "" || value === "N/A") {
    return "N/A";
  }

  // 百分比字段
  if (columnKey.includes("pct") || columnKey.includes("return") || columnKey.includes("volatility") || columnKey.includes("drawdown")) {
    return formatPercent(value);
  }

  // 比率字段
  if (columnKey.includes("ratio")) {
    return formatNumber(value, 2);
  }

  // 价格字段
  if (columnKey === "price") {
    return formatCurrency(value);
  }

  // 市值字段
  if (columnKey === "market_cap") {
    return formatMarketCap(value);
  }

  // 日期字段
  if (columnKey === "date" || columnKey === "timestamp") {
    return value;
  }

  // 代码和名称
  if (columnKey === "symbol" || columnKey === "name" || columnKey === "metric") {
    return value;
  }

  // 默认：如果是数字，格式化
  if (typeof value === "number") {
    return formatNumber(value, 2);
  }

  return value;
}

/**
 * 获取列名显示文本
 */
export function getColumnLabel(columnKey) {
  return COLUMN_LABELS[columnKey] || columnKey;
}

/**
 * 获取单位显示文本（USD→美元等）
 */
export function getUnitLabel(value) {
  if (value === null || value === undefined) return "";
  const v = String(value).trim().toUpperCase();
  return UNIT_LABELS[v] ?? UNIT_LABELS[value] ?? value;
}

/**
 * 获取指标名称显示文本
 */
export function getMetricLabel(metricKey) {
  return METRIC_LABELS[metricKey] || metricKey;
}
