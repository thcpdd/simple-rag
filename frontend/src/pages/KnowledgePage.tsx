import { useState, useEffect, useCallback, useRef } from 'react'
import { api, type KnowledgeDocResponse, type KnowledgeBaseItem } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Upload,
  FileText,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  FileUp,
  X,
  AlertTriangle,
  FolderOpen,
  Plus,
} from 'lucide-react'

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'ready':
      return (
        <Badge variant="success" className="gap-1 px-2.5 py-0.5">
          <CheckCircle2 className="h-3 w-3" />
          就绪
        </Badge>
      )
    case 'processing':
      return (
        <Badge variant="warning" className="gap-1 px-2.5 py-0.5">
          <Clock className="h-3 w-3" />
          处理中
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="destructive" className="gap-1 px-2.5 py-0.5">
          <AlertCircle className="h-3 w-3" />
          失败
        </Badge>
      )
    default:
      return <Badge variant="outline" className="px-2.5 py-0.5">{status}</Badge>
  }
}

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDocResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadKb, setUploadKb] = useState('')
  const [newKbName, setNewKbName] = useState('')
  const [useNewKb, setUseNewKb] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 知识库列表状态
  const [bases, setBases] = useState<KnowledgeBaseItem[]>([])
  const [selectedBase, setSelectedBase] = useState<string>('')

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const loadBases = useCallback(async () => {
    try {
      const data = await api.get<{ total: number; items: KnowledgeBaseItem[] }>('/knowledge/bases')
      setBases(data.items || [])
    } catch {
      // ignore
    }
  }, [])

  const loadDocs = useCallback(async () => {
    setLoading(true)
    try {
      const params = selectedBase ? `?knowledge_base=${encodeURIComponent(selectedBase)}` : ''
      const data = await api.get<{ total: number; items: KnowledgeDocResponse[] }>(`/knowledge/list${params}`)
      setDocs(data.items || [])
      if (!data.items?.some(d => d.status === 'processing')) {
        stopPoll()
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [selectedBase, stopPoll])

  // 组件卸载时停止轮询
  useEffect(() => {
    return () => stopPoll()
  }, [stopPoll])

  // 初始化加载
  useEffect(() => {
    loadBases()
  }, [loadBases])

  useEffect(() => {
    loadDocs()
  }, [loadDocs])

  const handleUpload = async () => {
    if (!uploadFile) return
    const kbName = useNewKb ? newKbName.trim() : uploadKb
    if (!kbName) {
      setUploadError('请选择或输入知识库名称')
      return
    }

    setUploadError('')
    setUploading(true)

    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('knowledge_base', kbName)

    try {
      await api.upload('/knowledge/upload', formData)
      setUploadOpen(false)
      setUploadFile(null)
      setUploadKb('')
      setNewKbName('')
      setUseNewKb(false)
      loadBases()
      loadDocs()
      stopPoll()
      pollRef.current = setInterval(loadDocs, 2000)
    } catch (err) {
      setUploadError(err instanceof api.ApiError ? err.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (docId: number) => {
    try {
      await api.delete(`/knowledge/${docId}`)
      setDeleteConfirm(null)
      loadDocs()
      loadBases()
    } catch {
      // ignore
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => {
    setDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file && (file.name.endsWith('.txt') || file.name.endsWith('.md'))) {
      setUploadFile(file)
      setUploadError('')
    } else {
      setUploadError('只支持 .txt 和 .md 格式的文件')
    }
  }

  const handleBaseChange = (base: string) => {
    setSelectedBase(base)
  }

  return (
    <div className="h-full flex flex-col bg-white/95">
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between shrink-0 border-b border-slate-100 bg-gradient-to-r from-white via-white to-slate-50/50">
        <div>
          <h1 className="font-heading text-lg font-semibold text-slate-800">知识库管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            管理知识库文档，支持 .txt 和 .md 格式
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => { loadDocs(); loadBases() }}
            className="border-slate-200 hover:bg-slate-50 hover:border-slate-300 transition-all duration-200"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
          <Dialog open={uploadOpen} onOpenChange={(open) => { setUploadOpen(open); if (!open) { setUploadFile(null); setUploadKb(''); setNewKbName(''); setUseNewKb(false); setUploadError('') } }}>
            <DialogTrigger asChild>
              <Button
                size="sm"
                className="bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-700 hover:to-indigo-600 text-white shadow-sm shadow-blue-200 transition-all duration-200"
              >
                <Upload className="h-4 w-4 mr-1.5" />
                上传文档
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="font-heading text-slate-800">上传知识文档</DialogTitle>
                <DialogDescription>
                  支持 .txt 和 .md 格式，单文件最大 10MB
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                {uploadError && (
                  <div className="bg-red-50/80 backdrop-blur-sm border border-red-100 text-red-600 text-sm p-3 rounded-lg flex items-center gap-2 animate-scale-in">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {uploadError}
                  </div>
                )}

                {/* 知识库选择 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">知识库</label>
                  {useNewKb ? (
                    <div className="flex gap-2">
                      <Input
                        placeholder="输入新知识库名称"
                        value={newKbName}
                        onChange={(e) => setNewKbName(e.target.value)}
                        className="flex-1"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => { setUseNewKb(false); setNewKbName('') }}
                        className="shrink-0"
                      >
                        选择已有
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <Select value={uploadKb} onValueChange={setUploadKb}>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="选择知识库" />
                          </SelectTrigger>
                          <SelectContent>
                            {bases.length === 0 ? (
                              <SelectItem value="default">默认知识库</SelectItem>
                            ) : (
                              bases.map((base) => (
                                <SelectItem key={base.name} value={base.name}>
                                  {base.name}（{base.doc_count} 篇）
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => { setUseNewKb(true); setUploadKb('') }}
                        className="shrink-0"
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        新建
                      </Button>
                    </div>
                  )}
                </div>

                {/* Drop zone */}
                <div
                  className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200 ${
                    dragOver
                      ? 'border-blue-400 bg-blue-50/60 scale-[1.01]'
                      : uploadFile
                        ? 'border-blue-300 bg-blue-50/40'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
                  }`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {uploadFile ? (
                    <div className="space-y-3">
                      <div className="rounded-full bg-blue-100 w-14 h-14 flex items-center justify-center mx-auto shadow-sm">
                        <FileText className="h-6 w-6 text-blue-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-700">{uploadFile.name}</p>
                        <p className="text-xs text-slate-400 mt-1">{formatFileSize(uploadFile.size)}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-slate-400 hover:text-red-500 hover:bg-red-50"
                        onClick={(e) => { e.stopPropagation(); setUploadFile(null); setUploadError('') }}
                      >
                        <X className="h-3.5 w-3.5 mr-1" />
                        移除文件
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="rounded-full bg-slate-50 w-14 h-14 flex items-center justify-center mx-auto group-hover:bg-slate-100 transition-colors">
                        <FileUp className="h-6 w-6 text-slate-400" />
                      </div>
                      <div>
                        <p className="text-sm text-slate-600">
                          <span className="font-medium text-blue-600">点击选择</span>
                          {' '}或拖拽文件到此处
                        </p>
                        <p className="text-xs text-slate-400 mt-1">.txt / .md 文件</p>
                      </div>
                    </div>
                  )}

                  <Input
                    ref={fileInputRef}
                    id="file-upload"
                    type="file"
                    accept=".txt,.md"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null
                      if (file) {
                        setUploadFile(file)
                        setUploadError('')
                      }
                    }}
                  />
                </div>
              </div>
              <DialogFooter className="gap-2">
                <Button
                  variant="outline"
                  onClick={() => { setUploadOpen(false); setUploadFile(null); setUploadKb(''); setNewKbName(''); setUseNewKb(false); setUploadError('') }}
                  className="border-slate-200"
                >
                  取消
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={!uploadFile || uploading || (useNewKb ? !newKbName.trim() : !uploadKb)}
                  className="bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-700 hover:to-indigo-600 transition-all duration-200"
                >
                  {uploading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      上传中...
                    </>
                  ) : (
                    '确认上传'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* 知识库标签栏 */}
      <div className="px-6 py-3 shrink-0 border-b border-slate-100 bg-slate-50/40">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleBaseChange('')}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer ${
              selectedBase === ''
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-200 ring-1 ring-blue-700/20'
                : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-800 border border-slate-200 hover:border-slate-300'
            }`}
          >
            全部
            <span className="ml-1.5 text-xs opacity-70">
              ({bases.reduce((sum, b) => sum + b.doc_count, 0)})
            </span>
          </button>
          {bases.map((base) => (
            <button
              key={base.name}
              onClick={() => handleBaseChange(base.name)}
              className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200 flex items-center gap-1.5 cursor-pointer ${
                selectedBase === base.name
                  ? 'bg-blue-600 text-white shadow-sm shadow-blue-200 ring-1 ring-blue-700/20'
                  : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-800 border border-slate-200 hover:border-slate-300'
              }`}
            >
              <FolderOpen className="h-3.5 w-3.5" />
              {base.name}
              <span className="text-xs opacity-70">({base.doc_count})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-lg bg-slate-100/80" />
              ))}
            </div>
          ) : docs.length === 0 ? (
            <Card className="border-slate-100 shadow-sm bg-white/50 backdrop-blur-sm">
              <CardContent className="flex flex-col items-center justify-center py-16">
                <div className="rounded-full bg-gradient-to-br from-slate-50 to-slate-100 w-16 h-16 flex items-center justify-center mb-4 shadow-sm">
                  <FileText className="h-7 w-7 text-slate-300" />
                </div>
                <p className="text-slate-600 font-medium mb-1">
                  {selectedBase ? `「${selectedBase}」暂无知识文档` : '暂无知识文档'}
                </p>
                <p className="text-sm text-slate-400 mb-6">
                  上传 .txt 或 .md 文件以构建知识库
                </p>
                <Button
                  onClick={() => setUploadOpen(true)}
                  className="bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-700 hover:to-indigo-600 shadow-sm shadow-blue-200 transition-all duration-200"
                >
                  <Upload className="h-4 w-4 mr-1.5" />
                  上传文档
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm bg-white">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/90 hover:bg-slate-50/90">
                    {!selectedBase && (
                      <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">知识库</TableHead>
                    )}
                    <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">文件名</TableHead>
                    <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">大小</TableHead>
                    <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">状态</TableHead>
                    <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">向量数量</TableHead>
                    <TableHead className="text-slate-500 font-semibold text-xs uppercase tracking-wider">上传时间</TableHead>
                    <TableHead className="w-20 text-slate-500 font-semibold text-xs uppercase tracking-wider">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docs.map((doc) => (
                    <TableRow
                      key={doc.id}
                      className="hover:bg-slate-50/70 transition-colors duration-150 border-b border-slate-100 last:border-0"
                    >
                      {!selectedBase && (
                        <TableCell>
                          <Badge variant="secondary" className="gap-1 px-2 py-0.5 text-xs font-normal">
                            <FolderOpen className="h-3 w-3" />
                            {doc.knowledge_base}
                          </Badge>
                        </TableCell>
                      )}
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2.5">
                          <FileText className="h-4 w-4 text-blue-500 shrink-0" />
                          <span className="truncate max-w-[200px] text-slate-700">
                            {doc.original_filename}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-500 text-sm">
                        {formatFileSize(doc.file_size)}
                      </TableCell>
                      <TableCell>{getStatusBadge(doc.status)}</TableCell>
                      <TableCell className="text-slate-700 tabular-nums">{doc.chunk_count}</TableCell>
                      <TableCell className="text-slate-400 text-sm">
                        {formatDate(doc.created_at)}
                      </TableCell>
                      <TableCell>
                        <Dialog open={deleteConfirm === doc.id} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
                          <DialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all duration-200"
                              onClick={() => setDeleteConfirm(doc.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                              <div className="flex items-center gap-3">
                                <div className="rounded-full bg-red-50 p-2">
                                  <AlertTriangle className="h-5 w-5 text-red-500" />
                                </div>
                                <div>
                                  <DialogTitle className="font-heading text-slate-800">确认删除</DialogTitle>
                                  <DialogDescription className="mt-1">
                                    此操作不可撤销
                                  </DialogDescription>
                                </div>
                              </div>
                            </DialogHeader>
                            <div className="py-3">
                              <p className="text-sm text-slate-600">
                                确定要删除「<span className="font-medium text-slate-800">{doc.original_filename}</span>」吗？
                              </p>
                              <p className="text-sm text-slate-500 mt-2">
                                删除后对应的向量数据将同步清除，此操作不可撤销。
                              </p>
                            </div>
                            <DialogFooter className="gap-2">
                              <Button
                                variant="outline"
                                onClick={() => setDeleteConfirm(null)}
                                className="border-slate-200"
                              >
                                取消
                              </Button>
                              <Button
                                variant="destructive"
                                onClick={() => handleDelete(doc.id)}
                                className="bg-red-600 hover:bg-red-700 transition-all duration-200"
                              >
                                确认删除
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
