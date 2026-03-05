import React from 'react'

const StockCard = ({ data, toolName }) => {
  // 根据不同的工具类型渲染不同的卡片
  const renderCard = () => {
    switch (toolName) {
      case 'get_price':
        return <PriceCard data={data} />
      case 'get_change':
        return <ChangeCard data={data} />
      case 'get_info':
        return <InfoCard data={data} />
      default:
        return null
    }
  }

  return renderCard()
}

// 价格卡片
const PriceCard = ({ data }) => {
  if (!data) return null

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <h3 className="text-2xl font-bold text-gray-900">{data.symbol}</h3>
            <span className="text-sm text-gray-500">{data.currency}</span>
          </div>
          {data.name && (
            <p className="text-sm text-gray-600 mt-1">{data.name}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-gray-900">
            {typeof data.price === 'number' ? data.price.toFixed(2) : data.price}
          </div>
          {data.source && (
            <p className="text-xs text-gray-500 mt-1">来源: {data.source}</p>
          )}
        </div>
      </div>
      {data.timestamp && (
        <div className="mt-3 pt-3 border-t border-blue-200">
          <p className="text-xs text-gray-500">
            更新时间: {new Date(data.timestamp).toLocaleString('zh-CN')}
          </p>
        </div>
      )}
    </div>
  )
}

// 涨跌幅卡片
const ChangeCard = ({ data }) => {
  if (!data) return null

  const isPositive = data.change_pct >= 0
  const changeColor = isPositive ? 'text-red-600' : 'text-green-600'
  const bgColor = isPositive ? 'bg-red-50' : 'bg-green-50'
  const borderColor = isPositive ? 'border-red-200' : 'border-green-200'
  const arrowIcon = isPositive ? '↑' : '↓'

  return (
    <div className={`${bgColor} rounded-lg p-4 border ${borderColor} shadow-sm`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-xl font-bold text-gray-900">{data.symbol}</h3>
          <p className="text-sm text-gray-600 mt-1">{data.days}日涨跌</p>
        </div>
        <div className="text-right">
          <div className={`text-3xl font-bold ${changeColor} flex items-center justify-end`}>
            <span>{arrowIcon}</span>
            <span className="ml-1">
              {Math.abs(data.change_pct).toFixed(2)}%
            </span>
          </div>
          {data.trend && (
            <p className="text-xs text-gray-600 mt-1">趋势: {data.trend}</p>
          )}
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500">起始价格</p>
          <p className="text-sm font-semibold text-gray-900">
            {typeof data.start_price === 'number' ? data.start_price.toFixed(2) : data.start_price}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">结束价格</p>
          <p className="text-sm font-semibold text-gray-900">
            {typeof data.end_price === 'number' ? data.end_price.toFixed(2) : data.end_price}
          </p>
        </div>
      </div>
    </div>
  )
}

// 公司信息卡片
const InfoCard = ({ data }) => {
  if (!data) return null

  const formatMarketCap = (value) => {
    if (!value) return 'N/A'
    if (value >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`
    if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
    if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
    return value.toString()
  }

  return (
    <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg p-4 border border-purple-200 shadow-sm">
      <div className="mb-3">
        <h3 className="text-2xl font-bold text-gray-900">{data.symbol}</h3>
        {data.name && (
          <p className="text-lg text-gray-700 mt-1">{data.name}</p>
        )}
      </div>

      <div className="space-y-2">
        {data.sector && (
          <div className="flex justify-between items-center py-2 border-b border-purple-100">
            <span className="text-sm text-gray-600">行业</span>
            <span className="text-sm font-semibold text-gray-900">{data.sector}</span>
          </div>
        )}
        {data.industry && (
          <div className="flex justify-between items-center py-2 border-b border-purple-100">
            <span className="text-sm text-gray-600">细分行业</span>
            <span className="text-sm font-semibold text-gray-900">{data.industry}</span>
          </div>
        )}
        {data.market_cap && (
          <div className="flex justify-between items-center py-2 border-b border-purple-100">
            <span className="text-sm text-gray-600">市值</span>
            <span className="text-sm font-semibold text-gray-900">
              {formatMarketCap(data.market_cap)}
            </span>
          </div>
        )}
        {data.pe_ratio && (
          <div className="flex justify-between items-center py-2 border-b border-purple-100">
            <span className="text-sm text-gray-600">市盈率</span>
            <span className="text-sm font-semibold text-gray-900">{data.pe_ratio}</span>
          </div>
        )}
        {(data['52w_high'] || data['52w_low']) && (
          <div className="flex justify-between items-center py-2">
            <span className="text-sm text-gray-600">52周区间</span>
            <span className="text-sm font-semibold text-gray-900">
              {data['52w_low']} - {data['52w_high']}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default StockCard
