# 前端 — AI 智能客服系统

基于 React 19 + TypeScript + Vite 构建的 SPA 前端，服务于 RAG (Retrieval-Augmented Generation) 智能客服系统。

## 技术栈

| 层面 | 技术 |
|------|------|
| 框架 | React 19, TypeScript 6 |
| 构建 | Vite 8, @vitejs/plugin-react |
| 样式 | Tailwind CSS v4 (via @tailwindcss/vite) |
| UI 组件 | shadcn/ui (Radix UI primitives + class-variance-authority) |
| 图标 | lucide-react |
| 路由 | react-router-dom v7 |
| Markdown | react-markdown + rehype-highlight + remark-gfm |
| 包管理 | pnpm |

## 快速开始

```bash
# 安装依赖
pnpm install

# 开发服务器 (端口 5173)
pnpm dev

# 构建生产版本
pnpm build

# 代码检查
pnpm lint
```

## 开发代理

开发模式下，Vite 将 `/api/*` 请求代理到后端 `http://127.0.0.1:7500`（自动剥离 `/api` 前缀）。无需处理 CORS。

## 项目结构

```
src/
├── components/
│   ├── auth/          # ProtectedRoute (JWT 路由守卫)
│   ├── chat/          # 聊天页面组件
│   ├── knowledge/     # 知识库管理组件
│   └── ui/            # shadcn/ui 原子组件
├── layouts/
│   └── AppLayout.tsx  # 侧边栏 + Outlet 布局
├── pages/
│   ├── ChatPage.tsx       # 聊天页面 (SSE 流式输出)
│   ├── KnowledgePage.tsx  # 文档管理与知识库配置
│   ├── LoginPage.tsx      # 登录
│   └── RegisterPage.tsx   # 注册
├── lib/
│   ├── api.ts         # API 客户端 (fetch 封装 + SSE 流)
│   └── utils.ts       # Tailwind class 合并工具
├── App.tsx            # 路由定义 (react-router-dom)
├── main.tsx           # 入口
└── index.css          # Tailwind v4 入口
```

## 页面说明

- **登录/注册**: JWT 认证，token 存储在 localStorage，通过 `Authorization: Bearer` 请求头携带
- **聊天**: SSE 流式渲染 AI 回复，支持工具调用中间状态展示、消息点赞/点踩、对话历史
- **知识库**: 知识库 CRUD 管理，文档上传（自动解析 → 切片 → 向量化）、状态轮询

## 环境要求

- Node.js >= 18
- pnpm >= 8
- 后端服务运行在 `http://127.0.0.1:7500`
