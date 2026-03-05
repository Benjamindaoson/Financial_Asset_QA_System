import React from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'

const TrendChart = ({ data }) => {
  if (!data || !data.data || data.data.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
        暂无历史数据
      </div>
    )
  }

  // 格式化日期
  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return `${date.getMonth() + 1}/${date.getDate()}`
  }

  // 格式化数据
  const chartData = data.data.map(item => ({
    date: formatDate(item.date),
    fullDate: item.date,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume
  }))

  // 计算价格范围
  const prices = data.data.flatMap(item => [item.high, item.low])
  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  const priceRange = maxPrice - minPrice
  const yAxisMin = (minPrice - priceRange * 0.1).toFixed(2)
  const yAxisMax = (maxPrice + priceRange * 0.1).toFixed(2)

  // 自定义Tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-white border border-gray-300 rounded-lg shadow-lg p-3">
          <p className="text-sm font-semibold text-gray-900 mb-2">{data.fullDate}</p>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between space-x-4">
              <span className="text-gray-600">开盘:</span>
              <span className="font-semibold text-gray-900">{data.open?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between space-x-4">
              <span className="text-gray-600">最高:</span>
              <span className="font-semibold text-red-600">{data.high?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between space-x-4">
              <span className="text-gray-600">最低:</span>
              <span className="font-semibold text-green-600">{data.low?.toFixed(2)}</span>
            </div>
            <div className="flex justify-between space-x-4">
              <span className="text-gray-600">收盘:</span>
              <span className="font-semibold text-gray-900">{data.close?.toFixed(2)}</span>
            </div>
            {data.volume && (
              <div className="flex justify-between space-x-4 pt-1 border-t border-gray-200">
                <span className="text-gray-600">成交量:</span>
                <span className="font-semibold text-gray-900">
                  {data.volume.toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm">
      <div className="mb-4">
        <h3 className="text-lg font-bold text-gray-900">{data.symbol}</h3>
        <p className="text-sm text-gray-600">
          {data.days}日历史走势
        </p>
      </div>

      {/* 价格走势图 */}
      <div className="mb-6">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              stroke="#6b7280"
            />
            <YAxis
              domain={[yAxisMin, yAxisMax]}
              tick={{ fontSize: 12 }}
              stroke="#6b7280"
              tickFormatter={(value) => value.toFixed(2)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="close"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#colorClose)"
              name="收盘价"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* 高低价格范围图 */}
      <div>
        <p className="text-sm font-semibold text-gray-700 mb-2">价格区间</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              stroke="#6b7280"
            />
            <YAxis
              domain={[yAxisMin, yAxisMax]}
              tick={{ fontSize: 12 }}
              stroke="#6b7280"
              tickFormatter={(value) => value.toFixed(2)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px' }}
              iconType="line"
            />
            <Line
              type="monotone"
              dataKey="high"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              name="最高价"
            />
            <Line
              type="monotone"
              dataKey="low"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              name="最低价"
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="收盘价"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 统计信息 */}
      <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-xs text-gray-500">期间最高</p>
          <p className="text-sm font-bold text-red-600">{maxPrice.toFixed(2)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">期间最低</p>
          <p className="text-sm font-bold text-green-600">{minPrice.toFixed(2)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">波动幅度</p>
          <p className="text-sm font-bold text-gray-900">
            {((priceRange / minPrice) * 100).toFixed(2)}%
          </p>
        </div>
      </div>
    </div>
  )
}

export default TrendChart
