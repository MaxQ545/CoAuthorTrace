# 论文合作者追踪系统 - 前端

基于 React + Vite + Tailwind CSS 的可视化前端。

## 功能

- 📊 系统状态仪表板
- 🔍 作者搜索
- 👤 作者详情页（合作者、网络指标）
- 🕸️ 合作网络可视化

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

前端将在 http://localhost:3000 启动，并自动代理 API 请求到后端 (http://localhost:8000)。

### 3. 启动后端（需要先启动）

```bash
cd ..
source venv/bin/activate
python scripts/start_server.py
```

## 生产构建

```bash
npm run build
```

构建产物在 `dist/` 目录，可部署到任何静态文件服务器。

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── client.js       # API 客户端
│   ├── components/
│   │   ├── Layout.jsx      # 页面布局
│   │   ├── SearchBox.jsx   # 搜索框
│   │   ├── AuthorCard.jsx  # 作者卡片
│   │   ├── StatsCard.jsx   # 统计卡片
│   │   ├── NetworkGraph.jsx # 网络图
│   │   └── TopAuthorsTable.jsx
│   ├── pages/
│   │   ├── HomePage.jsx    # 首页
│   │   ├── AuthorPage.jsx  # 作者详情
│   │   └── NetworkPage.jsx # 网络可视化
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## 技术栈

- **React 18** - UI 框架
- **Vite** - 构建工具
- **Tailwind CSS** - 样式
- **React Router** - 路由
- **vis-network** - 网络图可视化
