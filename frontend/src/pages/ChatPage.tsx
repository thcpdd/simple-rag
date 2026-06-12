import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, type SessionResponse, type SessionDetailResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Send,
  Plus,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  FileText,
  ThumbsUp,
  ThumbsDown,
  StopCircle,
  Bot,
  User,
  Loader2,
  Sparkles,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

export default function ChatPage() {
  const { threadId } = useParams<{ threadId: string }>()
  const navigate = useNavigate()

  // Session list
  const [sessions, setSessions] = useState<SessionResponse[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)

  // Current conversation
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Source references
  const [showSources, setShowSources] = useState<Record<string, boolean>>({})

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Load sessions
  const loadSessions = useCallback(async () => {
    try {
      const data = await api.get<{ total: number; items: SessionResponse[] }>('/session/list')
      setSessions(data.items || [])
    } catch {
      // ignore
    } finally {
      setLoadingSessions(false)
    }
  }, [])

  // Load conversation history when threadId changes
  useEffect(() => {
    if (threadId) {
      setCurrentThreadId(threadId)
      loadConversation(threadId)
    } else {
      setMessages([])
      setCurrentThreadId(null)
    }
  }, [threadId])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadConversation = async (tid: string) => {
    try {
      const data = await api.get<SessionDetailResponse>(`/session/${tid}`)
      const msgs: Message[] = []
      for (const m of data.messages) {
        if (m.role === 'human') {
          msgs.push({ id: m.id, role: 'user', content: m.content })
        } else if (m.role === 'ai') {
          msgs.push({ id: m.id, role: 'assistant', content: m.content })
        }
      }
      setMessages(msgs)
    } catch {
      navigate('/chat')
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setCurrentThreadId(null)
    setInput('')
    navigate('/chat')
    inputRef.current?.focus()
  }

  const handleSend = async () => {
    const query = input.trim()
    if (!query || streaming) return
    if (query.length > 500) {
      alert('提问长度不能超过500字')
      return
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
    }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setStreaming(true)

    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
    }
    setMessages((prev) => [...prev, assistantMessage])

    try {
      // 1. Invoke the chat
      const invokeRes = await api.post<{ thread_id: string; session_id: number }>('/chat/invoke', { query })
      const tid = invokeRes.thread_id
      setCurrentThreadId(tid)
      navigate(`/chat/${tid}`, { replace: true })

      // 2. Stream the response
      const controller = new AbortController()
      abortControllerRef.current = controller

      let fullContent = ''
      const sources: string[] = []

      api.stream(
        `/chat/stream/${tid}`,
        (content) => {
          fullContent += content
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: fullContent } : m)),
          )
        },
        (srcs) => {
          sources.push(...srcs)
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, sources: [...sources] } : m)),
          )
        },
        (_err) => {
          // error
        },
        () => {
          setStreaming(false)
          loadSessions()
        },
        controller.signal,
      )
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: m.content || '抱歉，发生了错误，请稍后重试。' } : m,
        ),
      )
      setStreaming(false)
    }
  }

  const handleStop = () => {
    if (currentThreadId) {
      api.post('/chat/stop', { thread_id: currentThreadId }).catch(() => {})
    }
    abortControllerRef.current?.abort()
    setStreaming(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleSources = (msgId: string) => {
    setShowSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }))
  }

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      <div className="w-72 min-w-0 border-r flex flex-col bg-muted/10 shrink-0">
        <div className="p-3">
          <Button
            variant="outline"
            className="w-full justify-start gap-2"
            onClick={handleNewChat}
          >
            <Plus className="h-4 w-4" />
            新建对话
          </Button>
        </div>
        <Separator />
        <div className="flex-1 overflow-y-auto min-w-0">
          {loadingSessions ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              暂无对话记录
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {sessions.map((s) => (
                <button
                  key={s.thread_id}
                  onClick={() => navigate(`/chat/${s.thread_id}`)}
                  className={`w-full text-left px-3 py-2.5 rounded-md text-sm transition-colors flex items-start gap-2 group ${
                    s.thread_id === currentThreadId
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-accent text-foreground'
                  }`}
                >
                  <MessageSquare className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <p className="truncate">{s.title || '新对话'}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {new Date(s.updated_at).toLocaleDateString('zh-CN')}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <ScrollArea className="flex-1 p-0">
          <div className="max-w-3xl mx-auto px-4 py-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[60vh] text-center">
                <div className="rounded-full bg-primary/5 p-4 mb-4">
                  <Sparkles className="h-8 w-8 text-primary/60" />
                </div>
                <h2 className="text-xl font-semibold mb-2">AI 智能客服</h2>
                <p className="text-muted-foreground text-sm max-w-md">
                  我是您的智能客服助手。您可以向我咨询产品信息、使用帮助等问题，我会基于知识库为您提供准确的回答。
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    {msg.role === 'assistant' && (
                      <div className="flex-shrink-0 mt-1">
                        <div className="rounded-full bg-primary/10 p-2">
                          <Bot className="h-4 w-4 text-primary" />
                        </div>
                      </div>
                    )}

                    <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                      {msg.role === 'user' ? (
                        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
                          {msg.content}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="prose prose-sm dark:prose-invert max-w-none markdown-content">
                            {msg.content ? (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.content}
                              </ReactMarkdown>
                            ) : (
                              <span className="text-muted-foreground">
                                <Loader2 className="h-4 w-4 inline animate-spin mr-2" />
                                思考中...
                              </span>
                            )}
                          </div>

                          {/* Source references */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div>
                              <button
                                onClick={() => toggleSources(msg.id)}
                                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                              >
                                <FileText className="h-3 w-3" />
                                引用来源 ({msg.sources.length})
                                {showSources[msg.id] ? (
                                  <ChevronUp className="h-3 w-3" />
                                ) : (
                                  <ChevronDown className="h-3 w-3" />
                                )}
                              </button>
                              {showSources[msg.id] && (
                                <div className="mt-2 space-y-1.5">
                                  {msg.sources.map((src, idx) => (
                                    <div
                                      key={idx}
                                      className="text-xs bg-muted/50 border rounded-md p-2.5 text-muted-foreground"
                                    >
                                      <div className="font-medium text-foreground mb-0.5">
                                        {src.split('\n')[0]}
                                      </div>
                                      <div className="line-clamp-2">{src.split('\n').slice(1).join('\n')}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Feedback buttons */}
                          {msg.content && !streaming && (
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <button className="hover:text-foreground transition-colors">
                                <ThumbsUp className="h-3.5 w-3.5" />
                              </button>
                              <button className="hover:text-foreground transition-colors">
                                <ThumbsDown className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {msg.role === 'user' && (
                      <div className="flex-shrink-0 mt-1">
                        <div className="rounded-full bg-secondary p-2">
                          <User className="h-4 w-4" />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input area */}
        <div className="border-t bg-background">
          <div className="max-w-3xl mx-auto p-4">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="请输入您的问题..."
                  disabled={streaming}
                  className="pr-20"
                  maxLength={500}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  {input.length}/500
                </span>
              </div>
              {streaming ? (
                <Button variant="secondary" onClick={handleStop}>
                  <StopCircle className="h-4 w-4 mr-1" />
                  停止
                </Button>
              ) : (
                <Button onClick={handleSend} disabled={!input.trim()}>
                  <Send className="h-4 w-4 mr-1" />
                  发送
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              AI 回答仅供参考，请以官方信息为准
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
