import { useState, useRef, useEffect } from 'react'
import StockCard from './StockCard'
import TrendChart from './TrendChart'

const ChatPanel = () => {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [streamingMessage, setStreamingMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const eventSourceRef = useRef(null)

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

  // 处理发送消息
  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: input.trim(),
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
      // 发送POST请求获取SSE连接
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: 'default-session'
        })
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
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !streamingMessage && (
          <div className="text-center text-gray-400 mt-8">
            <p className="text-lg">开始对话</p>
            <p className="text-sm mt-2">输入您的问题，我将为您提供金融资产相关信息</p>
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
      <div className="border-t border-gray-200 p-4">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题..."
            disabled={loading}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                发送中
              </span>
            ) : '发送'}
          </button>
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
