const API_BASE = '/api'

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  isFormData?: boolean
}

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, isFormData = false } = options

  const token = localStorage.getItem('access_token')
  const requestHeaders: Record<string, string> = {
    ...headers,
  }

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`
  }

  if (!isFormData) {
    requestHeaders['Content-Type'] = 'application/json'
  }

  const config: RequestInit = {
    method,
    headers: requestHeaders,
  }

  if (body) {
    config.body = isFormData ? body as FormData : JSON.stringify(body)
  }

  const response = await fetch(`${API_BASE}${path}`, config)

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    const data = await response.json()
    if (!response.ok) {
      throw new ApiError(data.detail || data.message || '请求失败', response.status)
    }
    return data as T
  }

  if (!response.ok) {
    throw new ApiError('请求失败', response.status)
  }

  return undefined as T
}

// SSE streaming for chat
function createSSEStream(
  path: string,
  onToken: (content: string) => void,
  onSources: (sources: string[]) => void,
  onError: (message: string) => void,
  onDone: () => void,
  signal?: AbortSignal,
  onToolCall?: (name: string, args: Record<string, unknown>) => void,
  onToolResult?: (name: string, result: string) => void,
): () => void {
  const token = localStorage.getItem('access_token')

  fetch(`${API_BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    signal,
  }).then(async (response) => {
    if (!response.ok) {
      onError(`HTTP ${response.status}: 请求失败`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError('无法读取响应流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              switch (data.type) {
                case 'token':
                  onToken(data.content)
                  break
                case 'tool_call':
                  onToolCall?.(data.name, data.args)
                  break
                case 'tool_result':
                  onToolResult?.(data.name, data.result)
                  break
                case 'sources':
                  onSources(data.sources || [])
                  break
                case 'error':
                  onError(data.message || '未知错误')
                  break
                case 'done':
                  onDone()
                  reader.cancel()  // 主动关闭连接，不需要等服务端关闭
                  break
              }
            } catch {
              // skip malformed JSON lines
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError('流式读取中断')
      }
    }
  })

  return () => {}
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData, isFormData: true }),
  stream: createSSEStream,
  ApiError,
}

// Types matching backend schemas
export interface UserResponse {
  id: number
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

export interface SessionResponse {
  thread_id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  total: number
  items: SessionResponse[]
}

export interface SessionMessageResponse {
  id: string
  type: 'human' | 'ai' | 'tool'
  content: string | null
  result: string | null
  args: Record<string, unknown> | null
  user_rating: 'like' | 'dislike' | null
}

export interface SessionDetailResponse {
  thread_id: string
  title: string | null
  messages: SessionMessageResponse[]
}

export interface ChatInvokeResponse {
  thread_id: string
  session_id: number
}

export interface ChatStopResponse {
  message: string
  thread_id: string
}

export interface KnowledgeDocResponse {
  id: number
  file_path: string
  original_filename: string
  file_size: number
  content_hash: string
  status: string
  chunk_count: number
  error_message: string | null
  created_at: string
}

export interface KnowledgeListResponse {
  total: number
  items: KnowledgeDocResponse[]
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ChatInvokeRequest {
  query: string
}

export interface FeedbackRequest {
  message_id: string
  rating: 'like' | 'dislike'
  comment?: string
}

export interface FeedbackResponse {
  id: number
  message_id: string
  rating: string
  comment: string | null
  created_at: string
}

export interface FeedbackSummaryResponse {
  message_id: string
  like_count: number
  dislike_count: number
}
