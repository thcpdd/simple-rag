import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type TokenResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { MessageSquare, Mail, Lock, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const data = await api.post<TokenResponse>('/auth/login', { email, password })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('user_email', data.user.email)
      navigate('/chat')
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-gradient-to-br from-blue-50 via-white to-slate-100">
      {/* Decorative background orbs */}
      <div className="gradient-orb w-[500px] h-[500px] bg-blue-400/10 -top-48 -right-48" />
      <div className="gradient-orb w-[400px] h-[400px] bg-indigo-400/10 -bottom-32 -left-32" />
      <div className="gradient-orb w-[300px] h-[300px] bg-cyan-400/8 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />

      <div className="w-full max-w-md animate-fade-in-up">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-2.5 shadow-lg shadow-blue-500/20">
            <MessageSquare className="h-6 w-6 text-white" />
          </div>
          <span className="text-xl font-semibold text-slate-800">AI 智能客服</span>
        </div>

        {/* Card */}
        <Card className="border-slate-200/60 shadow-xl shadow-slate-200/50 backdrop-blur-sm">
          <CardHeader className="space-y-1.5 pb-6">
            <CardTitle className="text-2xl text-center text-slate-800">欢迎回来</CardTitle>
            <CardDescription className="text-center text-slate-500">
              请输入您的邮箱和密码登录
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-5">
              {error && (
                <div className="bg-red-50 border border-red-100 text-red-600 text-sm p-3 rounded-lg animate-scale-in flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
                  {error}
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-700 text-sm font-medium">
                  邮箱
                </Label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                    className="pl-10 h-11 bg-white border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-700 text-sm font-medium">
                  密码
                </Label>
                <div className="relative group">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="pl-10 h-11 bg-white border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex flex-col gap-4 pb-6">
              <Button
                type="submit"
                className="w-full h-11 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white shadow-lg shadow-blue-500/20 transition-all duration-200 hover:shadow-xl hover:shadow-blue-500/30 active:scale-[0.98]"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    登录中...
                  </>
                ) : (
                  '登录'
                )}
              </Button>
              <p className="text-sm text-slate-500 text-center">
                还没有账号？{' '}
                <Link
                  to="/register"
                  className="text-blue-600 font-medium hover:text-blue-700 underline-offset-4 hover:underline transition-all"
                >
                  立即注册
                </Link>
              </p>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}
