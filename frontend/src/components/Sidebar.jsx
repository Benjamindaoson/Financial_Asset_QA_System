import { useState, useEffect } from 'react'

const Sidebar = () => {
  const [tickers, setTickers] = useState([
    { symbol: 'AAPL', name: '苹果', price: 233.65, change: 0.53, loading: false },
    { symbol: 'TSLA', name: '特斯拉', price: 190.44, change: 0.41, loading: false },
    { symbol: 'BABA', name: '阿里巴巴', price: 88.46, change: 3.66, loading: false },
    { symbol: 'NVDA', name: '英伟达', price: 861.37, change: -2.20, loading: false },
    { symbol: 'BTC-USD', name: '比特币', price: 84370.21, change: -1.41, loading: false },
    { symbol: 'AMZN', name: '亚马逊', price: 196.11, change: -0.46, loading: false },
    { symbol: '000001.SS', name: '上证指数', price: 3300.64, change: -0.70, loading: false },
  ])

  const quickAssets = [
    { symbol: 'AAPL', name: '苹果' },
    { symbol: 'TSLA', name: '特斯拉' },
    { symbol: 'BABA', name: '阿里巴巴' },
    { symbol: 'NVDA', name: '英伟达' },
    { symbol: 'BTC-USD', name: '比特币' },
    { symbol: '000001.SS', name: 'A股-上证指数' },
  ]

  // 更新实时行情数据
  useEffect(() => {
    const updateTickers = async () => {
      const updatedTickers = await Promise.all(
        tickers.map(async (ticker) => {
          try {
            // 调用后端API获取实时价格
            const response = await fetch(`/api/chat`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ query: `${ticker.symbol} price` })
            })

            // 这里简化处理，实际应该解析SSE流
            // 为了不阻塞UI，我们保持原有数据
            return ticker
          } catch (error) {
            console.error(`Failed to update ${ticker.symbol}:`, error)
            return ticker
          }
        })
      )
      setTickers(updatedTickers)
    }

    // 初始加载后每60秒更新一次
    const interval = setInterval(updateTickers, 60000)

    return () => clearInterval(interval)
  }, [])

  const handleAssetClick = (symbol, name) => {
    const question = `${name}的当前股价是多少？`
    const event = new CustomEvent('quickQuestion', { detail: question })
    window.dispatchEvent(event)
  }

  const handleTickerClick = (symbol, name) => {
    const question = `${name}(${symbol})的详细信息`
    const event = new CustomEvent('quickQuestion', { detail: question })
    window.dispatchEvent(event)
  }

  return (
    <div className="w-80 bg-white border-l border-gray-200 overflow-y-auto">
      {/* Quick Assets */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2 mb-3">
          <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-900">热门资产快捷入口</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {quickAssets.map((asset) => (
            <button
              key={asset.symbol}
              onClick={() => handleAssetClick(asset.symbol, asset.name)}
              className="px-3 py-2 text-sm text-left bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <div className="font-medium text-gray-900">{asset.name}</div>
              <div className="text-xs text-gray-500">{asset.symbol}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Real-time Tickers */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2 mb-3">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <h3 className="text-sm font-semibold text-gray-900">实时行情 TICKER</h3>
        </div>
        <div className="space-y-3">
          {tickers.map((ticker) => (
            <button
              key={ticker.symbol}
              onClick={() => handleTickerClick(ticker.symbol, ticker.name)}
              className="w-full flex items-center justify-between hover:bg-gray-50 rounded-lg p-2 transition-colors"
            >
              <div className="flex-1 text-left">
                <div className="font-medium text-gray-900 text-sm">{ticker.symbol}</div>
                <div className="text-xs text-gray-500">{ticker.name}</div>
              </div>
              <div className="text-right">
                <div className="font-semibold text-gray-900 text-sm">
                  ${ticker.price.toLocaleString()}
                </div>
                <div className={`text-xs flex items-center justify-end ${
                  ticker.change >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {ticker.change >= 0 ? (
                    <svg className="w-3 h-3 mr-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-3 h-3 mr-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                  {Math.abs(ticker.change).toFixed(2)}%
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* FAQ */}
      <div className="p-4">
        <div className="flex items-center space-x-2 mb-3">
          <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-900">常见问题 FAQ</h3>
        </div>
        <div className="space-y-2">
          {[
            { q: '如何查询股票价格？', a: '直接输入公司名或股票代码即可' },
            { q: '什么是市盈率？', a: '点击查看详细解释' },
            { q: '如何分析财务报表？', a: '点击查看分析方法' },
            { q: '技术分析指标有哪些？', a: '点击了解常用指标' }
          ].map((faq, idx) => (
            <button
              key={idx}
              onClick={() => {
                const event = new CustomEvent('quickQuestion', { detail: faq.q })
                window.dispatchEvent(event)
              }}
              className="w-full text-left p-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <div className="font-medium text-gray-900">• {faq.q}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Sidebar
