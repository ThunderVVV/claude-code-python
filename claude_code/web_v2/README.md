# Web V2 (FastAPI + Vue 3) 重构说明

## 概述

这是 Claude Code Python Web UI 的现代化重构版本，使用 FastAPI + Vue 3 替代原来的 aiohttp + 原生 JavaScript。

## 代码量对比

| 组件 | 原版本 | 新版本 | 减少 |
|------|--------|--------|------|
| **后端** | | | |
| server.py | 254 行 | 227 行 | -11% |
| cli.py | 72 行 | 82 行 | +14% (uvicorn集成) |
| **前端** | | | |
| index.html | 117 行 | - | 合并 |
| app.js | 945 行 | - | 合并 |
| styles.css | 323 行 | - | 合并 |
| index.html (Vue) | - | 1053 行 | 整合版 |
| **总计** | **1711 行** | **1362 行** | **-20%** |

## 技术栈对比

### 原版本
- **后端**: aiohttp (手动路由、SSE 流)
- **前端**: 原生 JavaScript (手动状态管理、DOM 操作)
- **依赖**: 较少

### 新版本
- **后端**: FastAPI (自动文档、类型验证、Pydantic)
- **前端**: Vue 3 CDN 版本 (响应式、组件化)
- **依赖**: 增加 fastapi, uvicorn, pydantic

## 主要改进

### 后端改进

1. **FastAPI 优势**
   - 自动生成 OpenAPI 文档 (`/docs`)
   - Pydantic 模型验证请求
   - 更简洁的 SSE 流实现
   - 更好的类型提示

2. **代码对比**

```python
# 原版 aiohttp
@routes.post("/api/chat")
async def chat(request):
    data = await request.json()
    session_id = data.get("session_id")
    user_text = data.get("user_text", "")
    working_directory = data.get("working_directory", os.getcwd())
    
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    # ... 手动处理

# 新版 FastAPI
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_text: str
    working_directory: str = os.getcwd()

@app.post("/api/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
    )
```

### 前端改进

1. **Vue 3 优势**
   - 响应式数据绑定
   - 组件化架构
   - 更清晰的状态管理
   - 更少的 DOM 操作

2. **代码对比**

```javascript
// 原版 - 手动创建 DOM
const createUserMessage = (text, fileExpansions = []) => {
    const div = document.createElement('div');
    div.className = 'flex justify-end fade-in';
    div.innerHTML = `
        <div class="max-w-[90%]">
            <div class="message-user rounded-2xl rounded-tr-md px-4 py-3 shadow-lg">
                <p class="text-white whitespace-pre-wrap">${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    return div;
};

// 新版 - Vue 模板
<div v-if="message.type === 'user'" class="flex justify-end fade-in">
    <div class="max-w-[90%]">
        <div class="message-user rounded-2xl rounded-tr-md px-4 py-3 shadow-lg">
            <p class="text-white whitespace-pre-wrap">{{ message.text }}</p>
        </div>
    </div>
</div>
```

## 使用方法

### 安装依赖

```bash
pip install -e .
```

### 启动服务

```bash
# 1. 启动后端 gRPC 服务器
cc-server

# 2. 启动新版 Web UI
cc-web-v2

# 或使用旧版
cc-web
```

### 访问

- 新版: http://localhost:8080
- API 文档: http://localhost:8080/docs (FastAPI 自动生成)

## 功能完整性

新版完全保留原版所有功能：

✅ 流式响应显示
✅ Markdown 渲染
✅ Diff 可视化 (Edit/Write 工具)
✅ 会话管理 (创建、切换、恢复)
✅ 工具调用展示
✅ 输入历史导航
✅ Token 计数
✅ 状态指示器
✅ 响应式布局
✅ 深色主题

## 架构优势

### 可维护性
- Vue 组件化，逻辑更清晰
- FastAPI 自动文档，API 更易理解
- 类型提示完善，IDE 支持更好

### 可扩展性
- Vue 组件可复用
- FastAPI 中间件生态丰富
- 易于添加新功能

### 性能
- Vue 虚拟 DOM 更高效
- FastAPI 性能优于 aiohttp
- uvicorn ASGI 服务器高性能

## 文件结构

```
claude_code/web_v2/
├── __init__.py
├── cli.py          # CLI 入口
├── server.py       # FastAPI 服务器
└── static/
    └── index.html  # Vue 3 单页应用
```

## 注意事项

1. **CDN 依赖**: Vue 3 通过 CDN 加载，需要网络连接
2. **兼容性**: 保持与原版完全相同的行为和 API
3. **渐进迁移**: 两个版本可并存，方便对比测试

## 后续优化建议

1. **构建优化**: 使用 Vite 构建 Vue 应用，减少 CDN 依赖
2. **状态管理**: 复杂场景可引入 Pinia
3. **TypeScript**: 添加类型支持
4. **测试**: 添加单元测试和 E2E 测试
