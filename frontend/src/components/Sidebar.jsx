const QUICK_ASSETS = [
  { symbol: 'AAPL', name: 'Apple' },
  { symbol: 'TSLA', name: 'Tesla' },
  { symbol: 'BABA', name: 'Alibaba' },
  { symbol: 'NVDA', name: 'NVIDIA' },
  { symbol: 'BTC-USD', name: 'Bitcoin' },
  { symbol: '000001.SS', name: 'SSE Index' },
]

const FAQ_ITEMS = [
  '如何查询股票价格？',
  '什么是市盈率？',
  '如何理解收入和净利润？',
  '为什么某只股票会突然大涨？',
]

const Sidebar = () => {
  const ask = (question) => {
    const event = new CustomEvent('quickQuestion', { detail: question })
    window.dispatchEvent(event)
  }

  return (
    <div className="w-80 overflow-y-auto border-l border-gray-200 bg-white">
      <div className="border-b border-gray-200 p-4">
        <div className="mb-3 flex items-center space-x-2">
          <svg className="h-5 w-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.05 2.93c.3-.92 1.6-.92 1.9 0l1.07 3.29a1 1 0 00.95.69h3.46c.97 0 1.37 1.24.59 1.81l-2.8 2.03a1 1 0 00-.36 1.12l1.07 3.29c.3.92-.76 1.69-1.54 1.12l-2.8-2.03a1 1 0 00-1.18 0l-2.8 2.03c-.78.57-1.84-.2-1.54-1.12l1.07-3.29a1 1 0 00-.36-1.12L2.98 8.72c-.78-.57-.38-1.81.59-1.81h3.46a1 1 0 00.95-.69l1.07-3.29z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-900">Quick assets</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {QUICK_ASSETS.map((asset) => (
            <button
              key={asset.symbol}
              onClick={() => ask(`${asset.name} (${asset.symbol}) current price and recent trend`)}
              className="rounded-lg bg-gray-50 px-3 py-2 text-left text-sm transition-colors hover:bg-gray-100"
            >
              <div className="font-medium text-gray-900">{asset.name}</div>
              <div className="text-xs text-gray-500">{asset.symbol}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="border-b border-gray-200 p-4">
        <div className="mb-3 flex items-center space-x-2">
          <div className="h-2 w-2 rounded-full bg-blue-500"></div>
          <h3 className="text-sm font-semibold text-gray-900">Market data behavior</h3>
        </div>
        <p className="text-sm leading-6 text-gray-600">
          This sidebar no longer shows synthetic real-time prices. Live market
          data is rendered only after the backend returns verified tool output.
        </p>
      </div>

      <div className="p-4">
        <div className="mb-3 flex items-center space-x-2">
          <svg className="h-5 w-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.23 9c.55-1.17 2.03-2 3.77-2 2.21 0 4 1.34 4 3 0 1.4-1.28 2.57-3.01 2.91-.54.1-.99.54-.99 1.09m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-900">FAQ shortcuts</h3>
        </div>
        <div className="space-y-2">
          {FAQ_ITEMS.map((question) => (
            <button
              key={question}
              onClick={() => ask(question)}
              className="w-full rounded-lg p-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-50"
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Sidebar
