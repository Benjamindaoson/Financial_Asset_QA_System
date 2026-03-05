import { useState, useEffect } from 'react'

const HealthStatus = () => {
  const [health, setHealth] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchHealth()
    // Refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchHealth = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/health')
      const data = await response.json()
      setHealth(data)
    } catch (error) {
      console.error('Failed to fetch health:', error)
      setHealth({ status: 'error', components: {} })
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-50'
      case 'degraded':
        return 'text-yellow-600 bg-yellow-50'
      case 'error':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return (
          <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        )
      case 'degraded':
        return (
          <svg className="w-4 h-4 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        )
      case 'error':
        return (
          <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        )
      default:
        return null
    }
  }

  const getComponentStatus = (component) => {
    const statusMap = {
      'connected': 'healthy',
      'ready': 'healthy',
      'available': 'healthy',
      'configured': 'healthy',
      'disconnected': 'error',
      'unavailable': 'error',
      'not_configured': 'error'
    }
    return statusMap[component] || 'degraded'
  }

  const getComponentDisplayName = (key) => {
    const names = {
      'redis': 'Redis缓存',
      'chromadb': '向量数据库',
      'claude_api': 'Claude API',
      'yfinance': '市场数据'
    }
    return names[key] || key
  }

  if (!health) {
    return (
      <div className="flex items-center space-x-2 text-gray-400">
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
        <span className="text-sm">检查中...</span>
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center space-x-2 px-3 py-1.5 rounded-full text-sm ${getStatusColor(health.status)}`}
      >
        {getStatusIcon(health.status)}
        <span className="font-medium">
          {health.status === 'healthy' ? '系统正常' : health.status === 'degraded' ? '部分降级' : '系统异常'}
        </span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="p-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">系统状态</h3>
              <button
                onClick={fetchHealth}
                disabled={loading}
                className="text-xs text-blue-600 hover:text-blue-700 disabled:text-gray-400"
              >
                {loading ? '刷新中...' : '刷新'}
              </button>
            </div>
            {health.timestamp && (
              <p className="text-xs text-gray-500 mt-1">
                更新时间: {new Date(health.timestamp).toLocaleTimeString('zh-CN')}
              </p>
            )}
          </div>

          <div className="p-3 space-y-2">
            {health.components && Object.entries(health.components).map(([key, value]) => {
              const status = getComponentStatus(value)
              return (
                <div key={key} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(status)}
                    <span className="text-sm text-gray-900">{getComponentDisplayName(key)}</span>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${getStatusColor(status)}`}>
                    {value}
                  </span>
                </div>
              )
            })}
          </div>

          {health.version && (
            <div className="p-3 border-t border-gray-200 bg-gray-50">
              <p className="text-xs text-gray-500">版本: {health.version}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default HealthStatus
