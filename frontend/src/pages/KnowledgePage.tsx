import { useState, useEffect, useCallback } from 'react'
import { api, type KnowledgeDocResponse } from '@/lib/api'
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
    case 'processed':
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          就绪
        </Badge>
      )
    case 'pending':
    case 'processing':
      return (
        <Badge variant="warning" className="gap-1">
          <Clock className="h-3 w-3" />
          处理中
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="destructive" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          失败
        </Badge>
      )
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDocResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  const loadDocs = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<{ total: number; items: KnowledgeDocResponse[] }>('/knowledge/list')
      setDocs(data.items || [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDocs()
  }, [loadDocs])

  const handleUpload = async () => {
    if (!uploadFile) return
    setUploadError('')
    setUploading(true)

    const formData = new FormData()
    formData.append('file', uploadFile)

    try {
      await api.upload('/knowledge/upload', formData)
      setUploadOpen(false)
      setUploadFile(null)
      loadDocs()
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
    } catch {
      // ignore
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-lg font-semibold">知识库管理</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            管理知识库文档，支持 .txt 和 .md 格式
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadDocs}>
            <RefreshCw className="h-4 w-4 mr-1" />
            刷新
          </Button>
          <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Upload className="h-4 w-4 mr-1" />
                上传文档
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>上传知识文档</DialogTitle>
                <DialogDescription>
                  支持 .txt 和 .md 格式，单文件最大 10MB
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                {uploadError && (
                  <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md">
                    {uploadError}
                  </div>
                )}
                <div className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
                  onClick={() => document.getElementById('file-upload')?.click()}
                >
                  <Upload className="h-8 w-8 mx-auto mb-3 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    {uploadFile ? uploadFile.name : '点击选择文件或拖拽文件到此处'}
                  </p>
                  {uploadFile && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatFileSize(uploadFile.size)}
                    </p>
                  )}
                  <Input
                    id="file-upload"
                    type="file"
                    accept=".txt,.md"
                    className="hidden"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => { setUploadOpen(false); setUploadFile(null); setUploadError('') }}>
                  取消
                </Button>
                <Button onClick={handleUpload} disabled={!uploadFile || uploading}>
                  {uploading ? '上传中...' : '确认上传'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-6">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : docs.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <FileText className="h-12 w-12 text-muted-foreground/50 mb-4" />
                <p className="text-muted-foreground mb-2">暂无知识文档</p>
                <p className="text-sm text-muted-foreground/70 mb-4">
                  上传 .txt 或 .md 文件以构建知识库
                </p>
                <Button onClick={() => setUploadOpen(true)}>
                  <Upload className="h-4 w-4 mr-1" />
                  上传文档
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>文件名</TableHead>
                    <TableHead>大小</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>向量数量</TableHead>
                    <TableHead>上传时间</TableHead>
                    <TableHead className="w-20">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docs.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <span className="truncate max-w-[200px]">
                            {doc.original_filename}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatFileSize(doc.file_size)}
                      </TableCell>
                      <TableCell>{getStatusBadge(doc.status)}</TableCell>
                      <TableCell>{doc.chunk_count}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {formatDate(doc.created_at)}
                      </TableCell>
                      <TableCell>
                        <Dialog open={deleteConfirm === doc.id} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
                          <DialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() => setDeleteConfirm(doc.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>确认删除</DialogTitle>
                              <DialogDescription>
                                确定要删除「{doc.original_filename}」吗？
                                删除后对应的向量数据将同步清除，此操作不可撤销。
                              </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
                                取消
                              </Button>
                              <Button
                                variant="destructive"
                                onClick={() => handleDelete(doc.id)}
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
