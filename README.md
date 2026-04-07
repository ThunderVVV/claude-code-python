
# Claude Code Python

Python 版本的 Claude Code - AI 编程助手。这是基于原始 TypeScript 版本重写的核心功能实现。

## 功能特性

- 核心查询引擎和对话循环
- OpenAI 兼容 API 支持
- 工具系统：
  - `read` - 读取文本文件
  - `write` - 写入文本文件
  - `edit` - 编辑文本文件
  - `glob` - 文件搜索
  - `grep` - 内容搜索
  - `bash` - 执行 shell 命令
- CLI 交互模式
- Textual TUI 界面（实验性）

## 安装

### 要求

- Python 3.12+

### 开发安装

```bash
cd claude-code-python
pip install -e .
```

或使用 Bun（如果已安装）：

```bash
bun install
```

## 配置

### 环境变量

创建 `.env` 文件：

```env
CLAUDE_CODE_API_URL=https://api.openai.com/v1
CLAUDE_CODE_API_KEY=your-api-key-here
CLAUDE_CODE_MODEL=gpt-4
```

### 命令行参数

也可以直接通过命令行参数配置：

```bash
claude-code --api-url https://api.openai.com/v1 --api-key your-key --model gpt-4
```

## 使用方法

### CLI 模式

```bash
claude-code
```

### TUI 模式（实验性）

```bash
claude-code --tui
```

### 使用示例

1. 启动 Claude Code：
```bash
claude-code
```

2. 询问问题或请求任务：
```
You: 创建一个简单的 Python 脚本
```

3. 助手会使用工具来完成任务：
```
Assistant: 我来帮你创建一个简单的 Python 脚本。

[Tool: write]
Input: {'path': 'hello.py', 'content': 'print("Hello, World!")\n'}

✓ Result:
Successfully wrote file: hello.py

Content:
print("Hello, World!")

Assistant: 已经创建了 `hello.py` 文件。这是一个简单的 Hello World 程序。
```

## 项目结构

```
claude-code-python/
├── pyproject.toml          # 项目配置
├── claude_code/
│   ├── __init__.py
│   ├── cli.py              # CLI 入口点
│   ├── core/
│   │   ├── messages.py     # 消息类型和数据模型
│   │   ├── tools.py        # 工具系统基础
│   │   └── query_engine.py # 核心查询引擎
│   ├── tools/
│   │   ├── file_tools.py   # 文件相关工具
│   │   └── bash_tool.py    # Bash 工具
│   ├── services/
│   │   └── openai_client.py # OpenAI API 客户端
│   └── ui/
│       ├── app.py          # Textual TUI 应用
│       └── app.css         # TUI 样式
└── README.md
```

## 架构说明

### 核心模块

1. **`claude_code/core/messages.py`**
   - 消息类型定义
   - 内容块（文本、工具使用、工具结果）
   - 查询状态管理

2. **`claude_code/core/tools.py`**
   - 工具接口定义
   - 工具注册表
   - 工具上下文

3. **`claude_code/core/query_engine.py`**
   - 核心查询循环
   - 事件系统
   - 工具执行编排

4. **`claude_code/services/openai_client.py`**
   - OpenAI 兼容 API 客户端
   - 流式响应处理
   - 消息格式转换

5. **`claude_code/tools/`**
   - 具体工具实现
   - 文件操作工具
   - Bash 执行工具

### 数据流

```
用户输入
  ↓
CLI/TUI 界面
  ↓
QueryEngine.submit_message()
  ↓
查询循环 (query_loop)
  ↓
OpenAIClient.chat_completion()
  ↓
流式响应处理
  ↓
工具调用 (如需要)
  ↓
工具执行
  ↓
结果反馈
  ↓
UI 更新
  ↓
循环 (直到任务完成)
```

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black claude_code/
ruff check claude_code/
```

## 许可证

MIT License
