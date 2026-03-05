import { useState } from 'react'
import ChatPanel from './components/ChatPanel'
import Sidebar from './components/Sidebar'
import ModelSelector from './components/ModelSelector'
import HealthStatus from './components/HealthStatus'
import { HelpModal, FeedbackModal } from './components/Modals'

function App() {
  const [messages, setMessages] = useState([])
  const [selectedModel, setSelectedModel] = useState(null)
  const [showHelp, setShowHelp] = useState(false)
  const [showFeedback, setShowFeedback] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  const handleQuickQuestion = (question) => {
    // 触发快速问题
    const event = new CustomEvent('quickQuestion', { detail: question })
    window.dispatchEvent(event)
  }

  const handleClearHistory = () => {
    if (messages.length === 0) return
    setShowClearConfirm(true)
  }

  const confirmClearHistory = () => {
    // 触发清除历史事件
    const event = new CustomEvent('clearHistory')
    window.dispatchEvent(event)
    setMessages([])
    setShowClearConfirm(false)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-full mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-semibold text-gray-900">金融资产问答系统</h1>
              <span className="px-2 py-0.5 text-xs font-medium text-blue-600 bg-blue-50 rounded">BETA</span>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {/* Health Status */}
            <HealthStatus />

            {/* Model Selector */}
            <ModelSelector
              currentModel={selectedModel}
              onModelChange={setSelectedModel}
            />

            {/* Feedback Button */}
            <button
              onClick={() => setShowFeedback(true)}
              className="flex items-center space-x-1 text-gray-600 hover:text-gray-900"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <span className="text-sm">反馈</span>
            </button>

            {/* Help Button */}
            <button
              onClick={() => setShowHelp(true)}
              className="flex items-center space-x-1 text-gray-600 hover:text-gray-900"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm">帮助</span>
            </button>

            {/* Clear History Button */}
            <button
              onClick={handleClearHistory}
              className="flex items-center space-x-1 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={messages.length === 0}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span className="text-sm">清除记录</span>
            </button>
          </div>
        </div>
      </header>

      {/* Warning Banner */}
      <div className="bg-yellow-50 border-b border-yellow-100">
        <div className="max-w-full mx-auto px-6 py-2">
          <div className="flex items-center text-sm text-yellow-800">
            <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span>本系统所有内容仅供参考，不构成投资建议。金融投资有风险，请审慎决策。</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <div className="h-full flex">
          {/* Chat Area */}
          <div className="flex-1 overflow-hidden">
            <ChatPanel
              onQuickQuestion={handleQuickQuestion}
              selectedModel={selectedModel}
              onMessagesChange={setMessages}
            />
          </div>

          {/* Sidebar */}
          <Sidebar />
        </div>
      </main>

      {/* Modals */}
      <HelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />
      <FeedbackModal isOpen={showFeedback} onClose={() => setShowFeedback(false)} />

      {/* Clear Confirmation Modal */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">确认清除历史记录？</h3>
            <p className="text-sm text-gray-600 mb-6">
              此操作将清除所有聊天记录，且无法恢复。
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => setShowClearConfirm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmClearHistory}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                确认清除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
