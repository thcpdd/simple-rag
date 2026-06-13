import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import {
  MessageSquare,
  BookOpen,
  PanelLeftClose,
  PanelLeft,
  LogOut,
  User,
} from 'lucide-react'

const navItems = [
  { to: '/chat', label: '智能对话', icon: MessageSquare },
  { to: '/knowledge', label: '知识库', icon: BookOpen },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const userEmail = localStorage.getItem('user_email') || 'user@example.com'

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_email')
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50/90 to-white">
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r border-slate-200/70 bg-white/95 backdrop-blur-sm transition-all duration-300 ease-in-out ${
          collapsed ? 'w-16' : 'w-60'
        } shrink-0`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-16 shrink-0">
          <div className="rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-2 shadow-md shadow-blue-500/20 shrink-0 ring-1 ring-white/20">
            <MessageSquare className="h-5 w-5 text-white" />
          </div>
          <div className={`overflow-hidden transition-all duration-300 ${collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
            <span className="font-heading font-semibold text-sm text-slate-800 whitespace-nowrap">AI 智能客服</span>
          </div>
        </div>

        <div className="px-3">
          <Separator className="bg-slate-100/80" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/chat'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 group relative ${
                  isActive
                    ? 'bg-blue-50/80 text-blue-700 font-medium shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                } ${collapsed ? 'justify-center px-2' : ''}`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active indicator bar */}
                  {isActive && !collapsed && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-blue-600 rounded-full shadow-sm shadow-blue-600/30" />
                  )}
                  <item.icon className={`h-4 w-4 shrink-0 transition-all duration-200 ${
                    isActive ? 'scale-110 text-blue-600' : 'group-hover:scale-105'
                  }`} />
                  {!collapsed && (
                    <span className="truncate">{item.label}</span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-3">
          <Separator className="bg-slate-100/80" />
        </div>

        {/* Collapse toggle */}
        <div className="p-2.5">
          <Button
            variant="ghost"
            size="sm"
            className={`w-full text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-all duration-200 ${
              collapsed ? 'px-0' : 'justify-between px-3'
            }`}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <PanelLeft className="h-4 w-4 mx-auto" />
            ) : (
              <>
                <span className="text-xs">收起侧栏</span>
                <PanelLeftClose className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>

        {/* User */}
        <div className="p-2.5 border-t border-slate-100/80">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={`w-full transition-all duration-200 hover:bg-slate-50 ${
                  collapsed ? 'px-0 justify-center' : 'justify-start gap-2.5 px-3'
                }`}
              >
                <Avatar className="h-7 w-7 ring-2 ring-slate-100 ring-offset-2">
                  <AvatarFallback className="text-xs font-medium bg-gradient-to-br from-blue-500 to-indigo-600 text-white">
                    {userEmail.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                {!collapsed && (
                  <div className="flex-1 text-left min-w-0">
                    <p className="text-xs font-medium text-slate-700 truncate">
                      {userEmail.split('@')[0]}
                    </p>
                    <p className="text-[10px] text-slate-400 truncate">
                      {userEmail.split('@')[1] || ''}
                    </p>
                  </div>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="right" className="w-52 p-1.5 rounded-xl border-slate-200/70 shadow-xl">
              <div className="flex items-center gap-3 px-2 py-2 mb-1">
                <Avatar className="h-9 w-9 ring-2 ring-slate-100">
                  <AvatarFallback className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-sm">
                    {userEmail.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">
                    {userEmail.split('@')[0]}
                  </p>
                  <p className="text-xs text-slate-400 truncate">{userEmail}</p>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled className="rounded-md py-2 text-slate-400 cursor-default">
                <User className="h-4 w-4 mr-2.5" />
                个人信息
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleLogout}
                className="rounded-md py-2 text-red-600 focus:text-red-700 focus:bg-red-50 cursor-pointer"
              >
                <LogOut className="h-4 w-4 mr-2.5" />
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
