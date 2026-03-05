import { useState, useRef, useEffect } from 'react'
import StockCard from './StockCard'
import TrendChart from './TrendChart'

const ChatPanel = ({ onQuickQuestion, selectedModel, onMessagesChange }) => {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [streamingMessage, setStreamingMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const eventSourceRef = useRef(null)

  // 快捷问题
  const quickQuestions = [
    '阿里巴巴当前股价是多少？',
    '最近7天特斯拉涨幅？',
    '市盈率是什么？',
    '比特币今日行情',
    'A股今日行情',
    '苹果公司股价'
  ]

  // 欢迎信息的快捷按钮
  const welcomeButtons = [
    { label: '查股价', icon: '📊' },
    { label: '看涨跌', icon: '📈' },
    { label: '学概念', icon: '📚' },
    { label: '看大盘', icon: '🔍' }
  ]

  // 监听快捷问题事件
  useEffect(() => {
    const handleQuickQuestion = (e) => {
      setInput(e.detail)
      // 自动发送
      setTimeout(() => {
        handleSendWithText(e.detail)
      }, 100)
    }

    const handleClearHistory = () => {
      setMessages([])
      setStreamingMessage(null)
      setError(null)
    }

    window.addEventListener('quickQuestion', handleQuickQuestion)
    window.addEventListener('clearHistory', handleClearHistory)
    return () => {
      window.removeEventListener('quickQuestion', handleQuickQuestion)
      window.removeEventListener('clearHistory', handleClearHistory)
    }
  }, [])

  // 通知父组件消息变化
  useEffect(() => {
    if (onMessagesChange) {
      onMessagesChange(messages)
    }
  }, [messages, onMessagesChange])

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingMessage])

  // 清理SSE连接
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  // 处理发送消息（带文本参数）
  const handleSendWithText = async (text) => {
    if (!text.trim() || loading) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString()
    }

    // 添加用户消息
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    // 初始化AI消息
    const aiMessageId = Date.now() + 1
    setStreamingMessage({
      id: aiMessageId,
      role: 'assistant',
      content: '',
      tools: [],
      timestamp: new Date().toISOString()
    })

    try {
      // 构建请求体，包含选中的模型
      const requestBody = {
        query: userMessage.content,
        session_id: 'default-session'
      }

      // 构建URL，如果有选中的模型则添加到查询参数
      const url = selectedModel
        ? `/api/chat?model=${encodeURIComponent(selectedModel)}`
        : '/api/chat'

      // 发送POST请求获取SSE连接
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // 处理SSE流
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()

            if (data === '[DONE]') {
              continue
            }

            try {
              const event = JSON.parse(data)
              handleSSEEvent(event, aiMessageId)
            } catch (e) {
              console.error('Failed to parse SSE data:', e, data)
            }
          }
        }
      }

      // 完成后将流式消息添加到消息列表
      setMessages(prev => [...prev, streamingMessage])
      setStreamingMessage(null)
      setLoading(false)

    } catch (err) {
      console.error('Chat error:', err)
      setError(err.message || '发送消息失败，请重试')
      setStreamingMessage(null)
      setLoading(false)
    }
  }

  // 处理发送消息
  const handleSend = () => {
    handleSendWithText(input)
  }

  // 处理SSE事件
  const handleSSEEvent = (event, messageId) => {
    switch (event.type) {
      case 'tool_start':
        // 工具开始调用
        setStreamingMessage(prev => ({
          ...prev,
          tools: [...(prev?.tools || []), {
            name: event.name,
            display: event.display,
            status: 'running',
            data: null
          }]
        }))
        break

      case 'tool_data':
        // 工具返回数据
        setStreamingMessage(prev => ({
          ...prev,
          tools: prev.tools.map(tool =>
            tool.name === event.tool
              ? { ...tool, status: 'completed', data: event.data }
              : tool
          )
        }))
        break

      case 'chunk':
        // 文本片段
        setStreamingMessage(prev => ({
          ...prev,
          content: (prev?.content || '') + event.text
        }))
        break

      case 'done':
        // 完成
        setStreamingMessage(prev => ({
          ...prev,
          verified: event.verified,
          sources: event.sources || [],
          request_id: event.request_id
        }))
        break

      case 'error':
        // 错误
        setError(`${event.message} (${event.code})`)
        setStreamingMessage(prev => ({
          ...prev,
          error: event.message
        }))
        break

      default:
        console.warn('Unknown SSE event type:', event.type)
    }
  }

  // 处理回车发送
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && !streamingMessage && (
          <div className="flex flex-col items-center justify-center h-full">
            {/* 欢迎图标 */}
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mb-6">
              <svg className="w-12 h-12 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>

            {/* 欢迎文字 */}
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              欢迎使用金融资产问答系统
            </h2>
            <p className="text-gray-500 text-center mb-8 max-w-2xl">
              您可以直接输入任何金融、资产类问题、系统将在数秒内为您成熟答案和<br/>
              智能分析。无需注册即可使用。
            </p>

            {/* 快捷按钮 */}
            <div className="flex space-x-4 mb-8">
              {welcomeButtons.map((btn, idx) => (
                <button
                  key={idx}
                  className="px-6 py-3 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all"
                >
                  <div className="text-2xl mb-1">{btn.icon}</div>
                  <div className="text-sm text-gray-700">{btn.label}</div>
                </button>
              ))}
            </div>

            {/* 快捷问题标签 */}
            <div className="w-full max-w-3xl">
              <p className="text-sm text-gray-500 mb-3">快捷问题：</p>
              <div className="flex flex-wrap gap-2">
                {quickQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendWithText(question)}
                    className="px-4 py-2 text-sm text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-full transition-colors"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>

            {/* 免责声明 */}
            <div className="mt-8 flex items-start space-x-2 text-xs text-gray-400 max-w-2xl">
              <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <p>历史记录将存储在本地，刷新后会全部清空。</p>
            </div>
          </div>
        )}

        {messages.map(message => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {streamingMessage && (
          <MessageBubble message={streamingMessage} streaming={true} />
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
            <span className="font-semibold">错误：</span> {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="flex space-x-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="请输入您的金融问题，例如「阿里巴巴当前股价是多少？」"
              disabled={loading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {loading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  发送中
                </span>
              ) : (
                <span className="flex items-center">
                  发送
                  <span className="ml-2 text-xs opacity-75">Enter</span>
                </span>
              )}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2 text-center">
            Shift + Enter 换行 {selectedModel && `• 当前模型: ${selectedModel}`}
          </p>
        </div>
      </div>
    </div>
  )
}

// 消息气泡组件
const MessageBubble = ({ message, streaming = false }) => {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-3xl ${isUser ? 'ml-12' : 'mr-12'}`}>
        {/* 消息内容 */}
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          {/* 工具调用状态 */}
          {!isUser && message.tools && message.tools.length > 0 && (
            <div className="mb-3 space-y-3">
              {message.tools.map((tool, idx) => (
                <div key={idx}>
                  <div className="flex items-center space-x-2 text-sm mb-2">
                    {tool.status === 'running' ? (
                      <svg className="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    ) : (
                      <svg className="h-4 w-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                    )}
                    <span className="text-gray-700">{tool.display}</span>
                  </div>

                  {/* 渲染工具数据卡片 */}
                  {tool.status === 'completed' && tool.data && (
                    <div className="ml-6">
                      {tool.name === 'get_history' ? (
                        <TrendChart data={tool.data} />
                      ) : (
                        <StockCard data={tool.data} toolName={tool.name} />
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 消息文本 */}
          <div className="whitespace-pre-wrap break-words">
            {message.content}
            {streaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-current animate-pulse"></span>
            )}
          </div>

          {/* 来源信息 */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-xs text-gray-500 mb-1">数据来源：</p>
              <div className="space-y-1">
                {message.sources.map((source, idx) => (
                  <div key={idx} className="text-xs text-gray-600">
                    {source}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 验证标记 */}
          {!isUser && message.verified && (
            <div className="mt-2 flex items-center text-xs text-green-600">
              <svg className="h-3 w-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              已验证
            </div>
          )}
        </div>

        {/* 时间戳 */}
        <div className={`text-xs text-gray-400 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
          })}
        </div>
      </div>
    </div>
  )
}

export default ChatPanel
