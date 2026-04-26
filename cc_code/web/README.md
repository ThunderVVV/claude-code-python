# CC Code Python - Web UI

基于 Vite + Vue 3 的 Web 界面。

## 技术栈

- **Vite** - 构建工具
- **Vue 3** - 前端框架 (Composition API + `<script setup>`)
- **Tailwind CSS** - 样式框架
- **Marked** - Markdown 渲染
- **Highlight.js** - 代码高亮
- **Diff2Html** - Diff 可视化

## 目录结构

```
cc_code/web/
├── index.html           # 入口 HTML
├── package.json         # 依赖配置
├── vite.config.js       # Vite 配置
├── tailwind.config.js   # Tailwind 配置
├── postcss.config.js    # PostCSS 配置
├── src/
│   ├── main.js          # 入口脚本
│   ├── App.vue          # 根组件
│   ├── style.css        # 全局样式
│   ├── components/      # Vue 组件
│   │   └── MessageItem.vue
│   ├── composables/     # 组合式函数
│   │   └── useChat.js   # 聊天逻辑
│   └── utils/           # 工具函数
│       ├── markdown.js
│       ├── format.js
│       └── diffViewer.js
└── dist/                # 构建输出 (自动生成)
    ├── index.html
    └── assets/
```

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器 (带 API 代理)
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 构建说明

- 开发时 API 请求会自动代理到 `http://localhost:8000`
- 生产构建输出到 `dist/` 目录
- 后端会自动优先使用 `dist/` 目录，回退到 `static/` 目录

## 从旧版迁移

原 `static/` 目录中的文件保留作为备份，新的 Vite 项目使用 `src/` 目录结构：

| 旧版 (CDN) | 新版 (Vite) |
|-----------|------------|
| Vue 3 CDN | `vue` npm 包 |
| Tailwind CDN | `tailwindcss` + PostCSS |
| Marked CDN | `marked` npm 包 |
| Highlight.js CDN | `highlight.js` npm 包 |
| Diff2Html CDN | `diff2html` + `diff` npm 包 |
| 单 HTML 文件 | 组件化拆分 |
