import { useState, useEffect } from 'react'

const ModelSelector = ({ onModelChange, currentModel }) => {
  const [models, setModels] = useState([])
  const [usage, setUsage] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/models')
      const data = await response.json()
      setModels(data.models || [])
      setUsage(data.usage || null)
    } catch (error) {
      console.error('Failed to fetch models:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleModelSelect = (modelName) => {
    onModelChange(modelName)
    setIsOpen(false)
  }

  const getModelDisplayName = (model) => {
    const names = {
      'claude-opus': 'Claude Opus (高性能)',
      'claude-sonnet': 'Claude Sonnet (平衡)',
      'deepseek-chat': 'DeepSeek Chat (经济)',
      'auto': '自动选择'
    }
    return names[model] || model
  }

  const getModelColor = (model) => {
    if (model.includes('claude')) return 'text-purple-600 bg-purple-50'
    if (model.includes('deepseek')) return 'text-blue-600 bg-blue-50'
    return 'text-gray-600 bg-gray-50'
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <span>{getModelDisplayName(currentModel || 'auto')}</span>
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="p-3 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">选择模型</h3>
            <p className="text-xs text-gray-500 mt-1">不同模型有不同的性能和成本特点</p>
          </div>

          <div className="p-2 max-h-96 overflow-y-auto">
            {loading ? (
              <div className="text-center py-4 text-gray-500">加载中...</div>
            ) : (
              <>
                {/* Auto selection */}
                <button
                  onClick={() => handleModelSelect(null)}
                  className={`w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors ${
                    !currentModel ? 'bg-blue-50 border border-blue-200' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">自动选择</div>
                      <div className="text-xs text-gray-500">系统智能选择最佳模型</div>
                    </div>
                    {!currentModel && (
                      <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                </button>

                {/* Available models */}
                {models.map((model) => (
                  <button
                    key={model.name}
                    onClick={() => handleModelSelect(model.name)}
                    className={`w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors mt-1 ${
                      currentModel === model.name ? 'bg-blue-50 border border-blue-200' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900">{getModelDisplayName(model.name)}</span>
                          <span className={`px-2 py-0.5 text-xs rounded ${getModelColor(model.name)}`}>
                            {model.provider}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {model.description || '高质量AI模型'}
                        </div>
                      </div>
                      {currentModel === model.name && (
                        <svg className="w-5 h-5 text-blue-600 flex-shrink-0 ml-2" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>

          {/* Usage statistics */}
          {usage && (
            <div className="p-3 border-t border-gray-200 bg-gray-50">
              <div className="text-xs text-gray-600">
                <div className="flex justify-between mb-1">
                  <span>本次会话使用:</span>
                  <span className="font-semibold">{usage.total_requests || 0} 次请求</span>
                </div>
                {usage.by_model && Object.keys(usage.by_model).length > 0 && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(usage.by_model).map(([model, count]) => (
                      <div key={model} className="flex justify-between">
                        <span className="text-gray-500">{getModelDisplayName(model)}:</span>
                        <span>{count} 次</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ModelSelector
