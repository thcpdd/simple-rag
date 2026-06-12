import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, type SessionResponse, type SessionDetailResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
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
  Sparkles,
  Search,
  Trash2,
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

  // Prevent loadConversation from overwriting streaming state during local send
  const streamingRef = useRef(false)

  // Source references
  const [showSources, setShowSources] = useState<Record<string, boolean>>({})

  // Delete confirmation state
  const [deleteConfirmTarget, setDeleteConfirmTarget] = useState<string | null>(null)

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

  // Load conversation history when threadId changes (skip during local send)
  useEffect(() => {
    if (threadId) {
      setCurrentThreadId(threadId)
      if (!streamingRef.current) {
        loadConversation(threadId)
      }
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

    streamingRef.current = true

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
      // 1. Invoke the chat (pass thread_id when continuing existing conversation)
      const invokeRes = await api.post<{ thread_id: string; session_id: number }>('/chat/invoke', {
        query,
        ...(currentThreadId ? { thread_id: currentThreadId } : {}),
      })
      const tid = invokeRes.thread_id
      setCurrentThreadId(tid)
      if (tid !== threadId) {
        navigate(`/chat/${tid}`, { replace: true })
      }

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
          streamingRef.current = false
          setStreaming(false)
        },
        () => {
          streamingRef.current = false
          setStreaming(false)
          loadSessions()
        },
        controller.signal,
      )
    } catch (err) {
      streamingRef.current = false
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

  const handleDeleteSession = (e: React.MouseEvent, tid: string) => {
    e.stopPropagation()
    setDeleteConfirmTarget(tid)
  }

  const confirmDeleteSession = async () => {
    const tid = deleteConfirmTarget
    if (!tid) return
    setDeleteConfirmTarget(null)
    // 如果正在流式输出中，先中止
    if (streaming && tid === currentThreadId) {
      abortControllerRef.current?.abort()
      setStreaming(false)
      streamingRef.current = false
    }
    try {
      await api.delete(`/session/${tid}`)
      setSessions((prev) => prev.filter((s) => s.thread_id !== tid))
      if (tid === currentThreadId) {
        handleNewChat()
      }
    } catch {
      alert('删除会话失败')
    }
  }

  return (
    <>
    <div className="flex h-full">
      {/* Session sidebar */}
      <div className="w-72 min-w-0 border-l border-slate-200/80 flex flex-col bg-white/80 shrink-0 order-last">
        <div className="p-3">
          <Button
            variant="outline"
            className="w-full justify-start gap-2 border-slate-200/80 hover:bg-slate-50 hover:border-slate-300 transition-all duration-200"
            onClick={handleNewChat}
          >
            <Plus className="h-4 w-4" />
            新建对话
          </Button>
        </div>
        <Separator className="bg-slate-100" />
        <div className="flex-1 overflow-y-auto min-w-0">
          {loadingSessions ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-lg bg-slate-100" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-8 text-center">
              <div className="rounded-full bg-slate-50 w-12 h-12 flex items-center justify-center mx-auto mb-3">
                <MessageSquare className="h-5 w-5 text-slate-300" />
              </div>
              <p className="text-sm text-slate-400">暂无对话记录</p>
              <p className="text-xs text-slate-300 mt-1">开始新的对话吧</p>
            </div>
          ) : (
            <div className="p-2 space-y-0.5">
              {sessions.map((s) => (
                <button
                  key={s.thread_id}
                  onClick={() => navigate(`/chat/${s.thread_id}`)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-200 flex items-start gap-2.5 group ${
                    s.thread_id === currentThreadId
                      ? 'bg-blue-50 text-blue-700'
                      : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <MessageSquare className={`h-4 w-4 mt-0.5 shrink-0 transition-colors ${
                    s.thread_id === currentThreadId ? 'text-blue-500' : 'text-slate-400 group-hover:text-slate-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">{s.title || '新对话'}</p>
                    <p className={`text-xs mt-0.5 ${
                      s.thread_id === currentThreadId ? 'text-blue-400' : 'text-slate-400'
                    }`}>
                      {new Date(s.updated_at).toLocaleDateString('zh-CN')}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(e, s.thread_id)}
                    className="p-1.5 rounded-md opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all duration-200 shrink-0"
                    title="删除会话"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col bg-white">
        {/* Messages */}
        <ScrollArea className="flex-1 p-0">
          <div className="px-6 py-8">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[65vh] text-center">
                <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 p-5 mb-5 shadow-sm animate-avatar-float">
                  <Sparkles className="h-10 w-10 text-blue-500" />
                </div>
                <h2 className="text-xl font-semibold text-slate-800 mb-2">AI 智能客服</h2>
                <p className="text-slate-500 text-sm max-w-md leading-relaxed">
                  我是您的智能客服助手。您可以向我咨询产品信息、使用帮助等问题，我会基于知识库为您提供准确的回答。
                </p>
                <div className="mt-6 flex items-center gap-1.5 text-xs text-slate-400">
                  <Search className="h-3 w-3" />
                  <span>输入问题开始对话</span>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((msg, idx) => (
                  <div
                    key={msg.id}
                    className={`message-enter flex gap-3 ${
                      msg.role === 'user' ? 'justify-end' : ''
                    }`}
                    style={{ animationDelay: `${idx * 0.05}s` }}
                  >
                    {msg.role === 'assistant' && (
                      <div className="flex-shrink-0 mt-1">
                        <div className="rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-2 shadow-sm">
                          <Bot className="h-4 w-4 text-white" />
                        </div>
                      </div>
                    )}

                    <div className={`${msg.role === 'user' ? 'max-w-[78%]' : 'flex-1 min-w-0'} ${msg.role === 'user' ? 'order-1' : ''}`}>
                      {msg.role === 'user' ? (
                        <div className="flex items-end gap-2">
                          <div className="bg-gradient-to-br from-blue-600 to-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm shadow-sm shadow-blue-200">
                            {msg.content}
                          </div>
                          <div className="rounded-full bg-slate-100 p-1.5 shrink-0">
                            <User className="h-3.5 w-3.5 text-slate-500" />
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="px-4 py-3">
                            <div className="prose prose-sm max-w-none markdown-content text-slate-700">
                              {msg.content ? (
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {msg.content}
                                </ReactMarkdown>
                              ) : (
                                <span className="text-slate-400 flex items-center gap-2">
                                  <span className="inline-flex items-center gap-1">
                                    <span className="typing-dot" />
                                    <span className="typing-dot" />
                                    <span className="typing-dot" />
                                  </span>
                                  <span className="ml-1">思考中...</span>
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Source references */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="animate-fade-in">
                              <button
                                onClick={() => toggleSources(msg.id)}
                                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors px-1"
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
                                      className="text-xs bg-slate-50 border border-slate-100 rounded-lg p-3 text-slate-500 animate-slide-in-left"
                                      style={{ animationDelay: `${idx * 0.05}s` }}
                                    >
                                      <div className="font-medium text-slate-700 mb-0.5">
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
                            <div className="flex items-center gap-1.5 px-1 animate-fade-in">
                              <button className="p-1.5 rounded-md text-slate-300 hover:text-blue-500 hover:bg-blue-50 transition-all duration-200">
                                <ThumbsUp className="h-3.5 w-3.5" />
                              </button>
                              <button className="p-1.5 rounded-md text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all duration-200">
                                <ThumbsDown className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input area */}
        <div className="border-t border-slate-100 bg-white">
          <div className="px-6 py-4">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="请输入您的问题..."
                  disabled={streaming}
                  className="pr-20 h-11 bg-slate-50 border-slate-200 focus:bg-white focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all rounded-xl"
                  maxLength={500}
                />
                <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 select-none">
                  {input.length}/500
                </span>
              </div>
              {streaming ? (
                <Button
                  variant="secondary"
                  onClick={handleStop}
                  className="h-11 px-4 bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 border-0 transition-all duration-200 active:scale-95 rounded-xl"
                >
                  <StopCircle className="h-4 w-4 mr-1.5" />
                  停止
                </Button>
              ) : (
                <Button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="h-11 px-5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white shadow-sm shadow-blue-200 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl"
                >
                  <Send className="h-4 w-4 mr-1.5" />
                  发送
                </Button>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-2.5 text-center">
              AI 回答仅供参考，请以官方信息为准
            </p>
          </div>
        </div>
      </div>
    </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteConfirmTarget !== null} onOpenChange={(open) => !open && setDeleteConfirmTarget(null)}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>删除会话</DialogTitle>
            <DialogDescription>
              确定要删除该会话吗？删除后无法恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmTarget(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDeleteSession}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
