import { useEffect, useRef, useState } from 'react'
import StockCard from './StockCard'
import TrendChart from './TrendChart'

const QUICK_QUESTIONS = [
  '阿里巴巴当前股价是多少？',
  'BABA 最近 7 天涨跌情况如何？',
  '什么是市盈率？',
  '特斯拉近期走势如何？',
  '阿里巴巴最近为何 1 月 15 日大涨？',
  '苹果公司的市盈率是多少？',
]

const WELCOME_ACTIONS = [
  { label: '查价格', icon: 'Price' },
  { label: '看涨跌', icon: 'Trend' },
  { label: '学概念', icon: 'RAG' },
  { label: '查原因', icon: 'News' },
]

const createAssistantMessage = () => ({
  id: Date.now() + 1,
  role: 'assistant',
  content: '',
  tools: [],
  sources: [],
  timestamp: new Date().toISOString(),
})

const ChatPanel = ({ onMessagesChange, selectedModel }) => {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [streamingMessage, setStreamingMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const streamingMessageRef = useRef(null)

  useEffect(() => {
    const handleQuickQuestion = (event) => {
      const question = event.detail || ''
      if (!question) return
      setInput(question)
      setTimeout(() => {
        handleSendWithText(question)
      }, 0)
    }

    const handleClearHistory = () => {
      setMessages([])
      setStreamingMessage(null)
      streamingMessageRef.current = null
      setError(null)
    }

    window.addEventListener('quickQuestion', handleQuickQuestion)
    window.addEventListener('clearHistory', handleClearHistory)
    return () => {
      window.removeEventListener('quickQuestion', handleQuickQuestion)
      window.removeEventListener('clearHistory', handleClearHistory)
    }
  }, [loading])

  useEffect(() => {
    if (onMessagesChange) {
      onMessagesChange(messages)
    }
  }, [messages, onMessagesChange])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage])

  const updateStreamingMessage = (updater) => {
    setStreamingMessage((prev) => {
      const next = updater(prev || createAssistantMessage())
      streamingMessageRef.current = next
      return next
    })
  }

  const finalizeStreamingMessage = () => {
    const draft = streamingMessageRef.current
    if (!draft) return

    setMessages((prev) => [...prev, draft])
    setStreamingMessage(null)
    streamingMessageRef.current = null
  }

  const handleSendWithText = async (text) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    const aiMessage = createAssistantMessage()
    streamingMessageRef.current = aiMessage
    setStreamingMessage(aiMessage)

    try {
      const requestBody = {
        query: trimmed,
        session_id: 'default-session',
      }

      const url = selectedModel
        ? `/api/chat?model=${encodeURIComponent(selectedModel)}`
        : '/api/chat'

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error: ${response.status}`)
      }

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
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (!data || data === '[DONE]') continue

          try {
            const event = JSON.parse(data)
            handleSSEEvent(event)
          } catch (parseError) {
            console.error('Failed to parse SSE event:', parseError, data)
          }
        }
      }

      finalizeStreamingMessage()
      setLoading(false)
    } catch (requestError) {
      console.error('Chat request failed:', requestError)
      updateStreamingMessage((prev) => ({
        ...prev,
        error: requestError.message || 'Request failed',
      }))
      finalizeStreamingMessage()
      setError(requestError.message || 'Request failed')
      setLoading(false)
    }
  }

  const handleSend = () => {
    handleSendWithText(input)
  }

  const handleSSEEvent = (event) => {
    switch (event.type) {
      case 'tool_start':
        updateStreamingMessage((prev) => ({
          ...prev,
          tools: [
            ...(prev.tools || []),
            {
              name: event.name,
              display: event.display,
              status: 'running',
              data: null,
            },
          ],
        }))
        break

      case 'tool_data':
        updateStreamingMessage((prev) => ({
          ...prev,
          tools: (prev.tools || []).map((tool) =>
            tool.name === event.tool
              ? { ...tool, status: 'completed', data: event.data }
              : tool
          ),
        }))
        break

      case 'chunk':
        updateStreamingMessage((prev) => ({
          ...prev,
          content: `${prev.content || ''}${event.text || ''}`,
        }))
        break

      case 'done':
        updateStreamingMessage((prev) => ({
          ...prev,
          verified: event.verified,
          sources: Array.isArray(event.sources) ? event.sources : [],
          request_id: event.request_id,
        }))
        break

      case 'error':
        updateStreamingMessage((prev) => ({
          ...prev,
          error: event.message,
        }))
        setError(`${event.message} (${event.code})`)
        break

      default:
        break
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && !streamingMessage && (
          <div className="flex h-full flex-col items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center mb-6">
              <svg className="w-12 h-12 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>

            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Financial Asset QA System
            </h2>
            <p className="max-w-2xl text-center text-gray-500 mb-8">
              Ask market questions, financial concept questions, or event-driven
              questions. The system will fetch data first and then explain it.
            </p>

            <div className="mb-8 flex flex-wrap justify-center gap-4">
              {WELCOME_ACTIONS.map((action) => (
                <div
                  key={action.label}
                  className="rounded-lg border border-gray-200 bg-white px-6 py-3 text-center shadow-sm"
                >
                  <div className="text-xs uppercase tracking-wide text-blue-600">
                    {action.icon}
                  </div>
                  <div className="mt-1 text-sm text-gray-700">{action.label}</div>
                </div>
              ))}
            </div>

            <div className="w-full max-w-3xl">
              <p className="text-sm text-gray-500 mb-3">Quick questions</p>
              <div className="flex flex-wrap gap-2">
                {QUICK_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    onClick={() => handleSendWithText(question)}
                    className="rounded-full bg-blue-50 px-4 py-2 text-sm text-blue-700 hover:bg-blue-100 transition-colors"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-8 max-w-2xl text-xs text-gray-400 text-center">
              Chat history is kept only in local component state and clears on refresh.
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {streamingMessage && <MessageBubble message={streamingMessage} streaming />}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <span className="font-semibold">Error:</span> {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 bg-gray-50 p-4">
        <div className="mx-auto max-w-4xl">
          <div className="flex space-x-3">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about prices, trends, financial concepts, or the reason behind a market move."
              disabled={loading}
              rows={2}
              className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="rounded-lg bg-blue-600 px-8 py-3 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-gray-400">
            Press Enter to send. Press Shift + Enter for a new line.
            {selectedModel ? ` Current model: ${selectedModel}` : ''}
          </p>
        </div>
      </div>
    </div>
  )
}

const MessageBubble = ({ message, streaming = false }) => {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-3xl ${isUser ? 'ml-12' : 'mr-12'}`}>
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'
          }`}
        >
          {!isUser && Array.isArray(message.tools) && message.tools.length > 0 && (
            <div className="mb-3 space-y-3">
              {message.tools.map((tool) => (
                <div key={`${tool.name}-${tool.display}`}>
                  <div className="mb-2 flex items-center space-x-2 text-sm">
                    {tool.status === 'running' ? (
                      <svg className="h-4 w-4 animate-spin text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.37 0 0 5.37 0 12h4zm2 5.29A7.95 7.95 0 014 12H0c0 3.04 1.14 5.82 3 7.94l3-2.65z"></path>
                      </svg>
                    ) : (
                      <svg className="h-4 w-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                    )}
                    <span className="text-gray-700">{tool.display}</span>
                  </div>

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

          <div className="whitespace-pre-wrap break-words">
            {message.content}
            {streaming && <span className="ml-1 inline-block h-4 w-2 animate-pulse bg-current"></span>}
          </div>

          {!isUser && Array.isArray(message.sources) && message.sources.length > 0 && (
            <div className="mt-3 border-t border-gray-200 pt-3">
              <p className="mb-1 text-xs text-gray-500">Sources</p>
              <div className="space-y-1">
                {message.sources.map((source, index) => (
                  <div key={`${source.name || 'source'}-${index}`} className="text-xs text-gray-600">
                    {formatSource(source)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!isUser && message.verified && (
            <div className="mt-2 flex items-center text-xs text-green-600">
              <svg className="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.71-9.29a1 1 0 00-1.42-1.42L9 10.59 7.71 9.29a1 1 0 00-1.42 1.42l2 2a1 1 0 001.42 0l4-4z" clipRule="evenodd" />
              </svg>
              Verified against tool outputs
            </div>
          )}

          {!isUser && message.error && (
            <div className="mt-2 text-xs text-red-600">
              {message.error}
            </div>
          )}
        </div>

        <div className={`mt-1 text-xs text-gray-400 ${isUser ? 'text-right' : 'text-left'}`}>
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  )
}

function formatSource(source) {
  if (!source || typeof source !== 'object') return String(source || '')
  if (source.name && source.timestamp) {
    return `${source.name} · ${new Date(source.timestamp).toLocaleString('zh-CN')}`
  }
  return source.name || JSON.stringify(source)
}

export default ChatPanel
