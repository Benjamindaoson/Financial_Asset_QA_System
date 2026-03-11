import { useState } from 'react'

const HelpModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">使用帮助</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Quick Start */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">快速开始</h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>1. 在输入框中输入您的金融问题</p>
              <p>2. 按 Enter 键或点击"发送"按钮</p>
              <p>3. 系统将实时返回答案和数据</p>
            </div>
          </section>

          {/* Features */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">功能介绍</h3>
            <div className="space-y-3">
              <div className="bg-blue-50 rounded-lg p-4">
                <h4 className="font-semibold text-blue-900 mb-2">📊 股票查询</h4>
                <p className="text-sm text-blue-800">
                  查询实时股价、历史数据、涨跌幅、公司信息等
                </p>
                <p className="text-xs text-blue-600 mt-2">
                  示例: "苹果股价"、"特斯拉最近7天涨幅"
                </p>
              </div>

              <div className="bg-green-50 rounded-lg p-4">
                <h4 className="font-semibold text-green-900 mb-2">📚 知识问答</h4>
                <p className="text-sm text-green-800">
                  了解金融概念、投资策略、市场分析等
                </p>
                <p className="text-xs text-green-600 mt-2">
                  示例: "什么是市盈率"、"如何分析财务报表"
                </p>
              </div>

              <div className="bg-purple-50 rounded-lg p-4">
                <h4 className="font-semibold text-purple-900 mb-2">📈 数据可视化</h4>
                <p className="text-sm text-purple-800">
                  自动生成股票走势图、价格区间图等
                </p>
                <p className="text-xs text-purple-600 mt-2">
                  示例: "阿里巴巴30天历史数据"
                </p>
              </div>

              <div className="bg-yellow-50 rounded-lg p-4">
                <h4 className="font-semibold text-yellow-900 mb-2">🔍 智能搜索</h4>
                <p className="text-sm text-yellow-800">
                  结合知识库和网络搜索，提供全面答案
                </p>
                <p className="text-xs text-yellow-600 mt-2">
                  示例: "最新美联储利率决议"
                </p>
              </div>
            </div>
          </section>

          {/* Supported Assets */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">支持的资产</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="font-semibold text-gray-900 mb-1">🇺🇸 美股</div>
                <div className="text-xs text-gray-600">AAPL, TSLA, NVDA, MSFT...</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="font-semibold text-gray-900 mb-1">🇨🇳 A股</div>
                <div className="text-xs text-gray-600">上证指数, 深证成指...</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="font-semibold text-gray-900 mb-1">🇭🇰 港股</div>
                <div className="text-xs text-gray-600">腾讯, 阿里巴巴...</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="font-semibold text-gray-900 mb-1">₿ 加密货币</div>
                <div className="text-xs text-gray-600">BTC, ETH...</div>
              </div>
            </div>
          </section>

          {/* Tips */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">使用技巧</h3>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex items-start space-x-2">
                <span className="text-blue-600 font-semibold">•</span>
                <p>使用中文公司名或股票代码都可以查询</p>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-blue-600 font-semibold">•</span>
                <p>可以指定时间范围，如"最近7天"、"30天"</p>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-blue-600 font-semibold">•</span>
                <p>使用侧边栏的快捷入口快速查询热门资产</p>
              </div>
              <div className="flex items-start space-x-2">
                <span className="text-blue-600 font-semibold">•</span>
                <p>Shift + Enter 可以换行输入多行问题</p>
              </div>
            </div>
          </section>

          {/* Keyboard Shortcuts */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">快捷键</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded">
                <span className="text-sm text-gray-600">发送消息</span>
                <kbd className="px-2 py-1 text-xs font-semibold text-gray-800 bg-white border border-gray-300 rounded">Enter</kbd>
              </div>
              <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded">
                <span className="text-sm text-gray-600">换行</span>
                <kbd className="px-2 py-1 text-xs font-semibold text-gray-800 bg-white border border-gray-300 rounded">Shift + Enter</kbd>
              </div>
            </div>
          </section>

          {/* Disclaimer */}
          <section className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start space-x-2">
              <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <div>
                <h4 className="font-semibold text-yellow-900 mb-1">免责声明</h4>
                <p className="text-sm text-yellow-800">
                  本系统提供的所有信息仅供参考，不构成投资建议。金融投资有风险，请审慎决策。
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            开始使用
          </button>
        </div>
      </div>
    </div>
  )
}

const FeedbackModal = ({ isOpen, onClose }) => {
  const [feedback, setFeedback] = useState('')
  const [type, setType] = useState('suggestion')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = () => {
    // In a real app, this would send to backend
    console.log('Feedback submitted:', { type, feedback })
    setSubmitted(true)
    setTimeout(() => {
      setSubmitted(false)
      setFeedback('')
      onClose()
    }, 2000)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
        {/* Header */}
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">反馈建议</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {submitted ? (
            <div className="text-center py-8">
              <svg className="w-16 h-16 text-green-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">感谢您的反馈！</h3>
              <p className="text-sm text-gray-600">我们会认真考虑您的建议</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Type selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">反馈类型</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 'bug', label: '问题反馈', icon: '🐛' },
                    { value: 'suggestion', label: '功能建议', icon: '💡' },
                    { value: 'other', label: '其他', icon: '💬' }
                  ].map((item) => (
                    <button
                      key={item.value}
                      onClick={() => setType(item.value)}
                      className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                        type === item.value
                          ? 'bg-blue-50 border-blue-500 text-blue-700'
                          : 'bg-white border-gray-300 text-gray-700 hover:border-gray-400'
                      }`}
                    >
                      <div>{item.icon}</div>
                      <div className="text-xs mt-1">{item.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Feedback text */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">详细描述</label>
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="请描述您遇到的问题或建议..."
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>

              {/* Submit button */}
              <button
                onClick={handleSubmit}
                disabled={!feedback.trim()}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                提交反馈
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export { HelpModal, FeedbackModal }
