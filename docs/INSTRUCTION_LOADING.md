# CLAUDE.md / AGENTS.md 加载与系统提示注入机制

本文档说明 claude-code-python 项目如何加载 CLAUDE.md、AGENTS.md 等文件并将其内容注入到系统提示中的完整机制。

---

## 概述

项目通过 `InstructionService` 服务模块自动查找、读取并注入项目级和全局级的配置指令文件到 AI 会话的系统提示中，使用户能够自定义 AI 的行为。

---

## 目标文件列表

系统会查找以下文件（按优先级顺序）：

| 文件名 | 是否默认启用 | 说明 |
|-------|-------------|------|
| `AGENTS.md` | 始终启用 | 代理指令配置 |
| `CLAUDE.md` | 默认启用 | Claude 指令配置（可通过环境变量禁用） |
| `CONTEXT.md` | 已弃用 | 上下文配置（保留兼容性） |

---

## 文件搜索路径

### 项目级别搜索

从当前工作目录向上搜索到工作区根目录，**找到第一个匹配项即停止**（避免多层级堆叠）：

```
当前目录/
├── AGENTS.md      ← 优先加载
├── CLAUDE.md      ← 次优先
└── CONTEXT.md     ← 兼容性
```

### 全局级别搜索

| 路径 | 条件 |
|-----|------|
| `$OPENCODE_CONFIG_DIR/AGENTS.md` | 当 `OPENCODE_CONFIG_DIR` 环境变量设置时 |
| `~/.config/opencode/AGENTS.md` | 默认全局配置目录 |
| `~/.claude/CLAUDE.md` | 当未禁用 CLAUDE.md 时 |

### 配置文件自定义指令

在 `settings.json` 中通过 `instructions` 字段指定：

```json
{
  "instructions": [
    "CUSTOM.md",
    "~/my-instructions.md",
    "/absolute/path/to/instructions.md",
    "https://example.com/instructions.md"
  ]
}
```

支持：
- 相对路径（从项目目录向上搜索）
- `~` 开头的用户主目录路径
- 绝对路径
- `http://` / `https://` 远程 URL

---

## 核心加载流程

### 流程图

```
1. get_system_paths() 收集路径
   ├─ 项目级别：从当前目录向上搜索 FILES
   ├─ 全局级别：检查 globalFiles() 路径
   └─ 配置级别：解析 settings.json 中的 instructions
         ↓
2. load_instructions() 读取内容
   ├─ 并发读取所有本地文件（8并发）
   ├─ 并发获取所有远程 URL（4并发）
   └─ 格式化为 "Instructions from: {path}\n{content}"
         ↓
3. 注入到系统提示（prompts.py）
   └─ 合并到 [...env, ...instructions]
```

---

## 注入到系统提示

### 最终系统提示组装顺序

```python
# 在 prompts.py 中
sections = [
    get_simple_intro_section(),
    get_simple_system_section(),
    get_simple_doing_tasks_section(),
    get_actions_section(),
    get_using_your_tools_section(),
    get_simple_tone_and_style_section(),
    get_output_efficiency_section(),
    compute_env_info(cwd, model_name),
    # ↓ 从 CLAUDE.md/AGENTS.md 加载的指令
    *instructions,
]
```

### 指令内容格式

每个加载的文件内容格式为：

```
Instructions from: /path/to/CLAUDE.md
[文件的实际内容]
```

---

## 关键源代码

### 1. instruction.py - 核心加载模块

文件路径：`claude_code/core/instruction.py`

```python
class InstructionService:
    """Service for loading and managing instruction files."""

    async def get_system_paths(self, working_directory: str) -> Set[str]:
        """Collect all instruction file paths that should be loaded."""
        paths: Set[str] = set()

        # 1. Project-level search (first match wins)
        if not self.config.disable_project_config:
            for filename in self.config.files:
                match = self._find_upward(filename, working_directory)
                if match:
                    paths.add(os.path.abspath(match))
                    break

        # 2. Global-level files
        for global_file in self._get_global_files():
            if os.path.isfile(global_file):
                paths.add(os.path.abspath(global_file))
                break

        # 3. Custom instructions from config
        for raw in self.config.custom_instructions:
            if not self._is_url(raw):
                resolved = self._resolve_path(raw, working_directory)
                if resolved and os.path.isfile(resolved):
                    paths.add(os.path.abspath(resolved))

        return paths

    async def load_instructions(self, working_directory: str) -> List[LoadedInstruction]:
        """Load all instruction files and return their contents."""
        paths = await self.get_system_paths(working_directory)
        urls = await self.get_system_urls()

        instructions: List[LoadedInstruction] = []

        # Load local files concurrently (8 concurrent)
        if paths:
            semaphore = asyncio.Semaphore(self.config.max_concurrent_files)
            # ... concurrent file reading

        # Fetch URLs concurrently (4 concurrent)
        if urls:
            semaphore = asyncio.Semaphore(self.config.max_concurrent_urls)
            # ... concurrent URL fetching

        return instructions
```

### 2. prompts.py - 系统提示注入点

文件路径：`claude_code/core/prompts.py`

```python
def create_default_system_prompt(
    cwd: Optional[str] = None,
    model_name: str = "claude-sonnet-4-6",
    instructions: Optional[List[str]] = None,
) -> str:
    """Create the default system prompt for the assistant."""
    sections = [
        # ... standard sections
    ]

    # Append instruction files (CLAUDE.md, AGENTS.md, etc.)
    if instructions:
        sections.extend(instructions)

    return "\n\n".join(sections)


async def create_system_prompt_with_instructions(
    cwd: Optional[str] = None,
    model_name: str = "claude-sonnet-4-6",
    instruction_config: Optional[InstructionConfig] = None,
) -> str:
    """Create system prompt with automatically loaded instructions."""
    instructions = await load_system_instructions(cwd, instruction_config)
    return create_default_system_prompt(cwd, model_name, instructions)
```

### 3. query_engine.py - 引擎集成

文件路径：`claude_code/core/query_engine.py`

```python
class QueryEngine:
    async def _load_instructions(self) -> List[str]:
        """Load instructions from CLAUDE.md, AGENTS.md, etc."""
        if self._cached_instructions is not None:
            return self._cached_instructions

        if self._instruction_service is None:
            return []

        self._cached_instructions = await self._instruction_service.get_system_instructions(
            self._cwd
        )
        return self._cached_instructions

    async def _build_system_prompt(self) -> str:
        """Build the system prompt with instructions."""
        instructions = await self._load_instructions()
        return create_default_system_prompt(
            cwd=self._cwd,
            model_name=self.client_config.model_name,
            instructions=instructions if instructions else None,
        )
```

---

## 配置目录结构

系统支持的完整配置目录结构：

```
项目根目录/
├── .claude-code-python/
│   └── settings.json   # 主配置文件
├── AGENTS.md           # 项目级代理指令
├── CLAUDE.md           # 项目级 Claude 指令
└── CONTEXT.md          # （已弃用）

全局配置/
├── ~/.config/opencode/
│   └── AGENTS.md       # 全局代理指令
└── ~/.claude/
    └── CLAUDE.md       # 全局 Claude 指令
```

---

## 环境变量控制

| 环境变量 | 功能 |
|---------|------|
| `OPENCODE_CONFIG_DIR` | 指定自定义配置目录 |
| `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` | 禁用 CLAUDE.md 加载（设为 `true` 或 `1`） |
| `OPENCODE_DISABLE_PROJECT_CONFIG` | 禁用项目级配置加载 |

---

## settings.json 配置示例

```json
{
  "current_model": "claude-sonnet",
  "theme": "atom-one-dark",
  "models": {
    "claude-sonnet": {
      "api_key": "your-api-key",
      "api_url": "https://api.anthropic.com/v1",
      "model_name": "claude-sonnet-4-6",
      "context": 200000
    }
  },
  "instructions": [
    "CUSTOM.md",
    "~/global-instructions.md",
    "https://example.com/team-instructions.md"
  ]
}
```

---

## 特性总结

- ✓ **层级搜索**：项目级 → 全局级 → 配置指定
- ✓ **就近加载**：读取文件时自动加载附近的指令文件
- ✓ **去重机制**：按 message 追踪已加载文件，避免重复注入
- ✓ **远程支持**：支持 HTTP/HTTPS URL 远程指令
- ✓ **并发读取**：8 并发本地文件，4 并发远程 URL
- ✓ **容错处理**：文件读取失败时优雅降级

---

## 使用示例

### 项目级配置

在项目根目录创建 `CLAUDE.md`：

```markdown
# Project Instructions

## Code Style
- Use Python 3.10+ type hints
- Follow PEP 8 naming conventions
- Prefer dataclasses over dict for structured data

## Testing
- Write pytest tests for all new functions
- Aim for 80% code coverage
```

### 全局配置

在 `~/.claude/CLAUDE.md` 创建全局指令：

```markdown
# Global Instructions

## Communication
- Be concise and direct
- Use bullet points for lists
- Include code examples when explaining concepts
```

### 远程指令

在 settings.json 中配置远程 URL：

```json
{
  "instructions": [
    "https://company.example.com/ai/instructions.md"
  ]
}
```

---

## 就近加载机制

当 AI 使用 Read 工具读取文件时，系统会自动加载该文件所在目录及其父目录中的指令文件。

### 工作原理

```
项目根目录/
├── AGENTS.md              # 启动时加载（系统级）
├── src/
│   ├── AGENTS.md          # 读取 src/ 下文件时加载
│   └── components/
│       ├── AGENTS.md      # 读取 components/ 下文件时加载
│       └── Button.tsx
```

当读取 `Button.tsx` 时：
1. 从 `components/` 目录开始向上搜索
2. 找到 `components/AGENTS.md` → 注入到当前消息
3. 继续向上找到 `src/AGENTS.md` → 注入到当前消息
4. 到达项目根目录停止（根目录的 `AGENTS.md` 已在启动时加载）

### 去重机制

- **按消息追踪**：每个 assistant message 有独立的已加载文件集合
- **跨消息去重**：检查历史消息中的 `loaded` metadata，避免重复加载
- **系统路径排除**：启动时已加载的系统级指令不会重复加载

### 代码示例

```python
# 在 ReadTool 中自动触发
async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
    # ... 读取文件内容 ...
    
    # 加载附近指令
    if context.instruction_service and context.message_id:
        instructions = await context.instruction_service.resolve_nearby_instructions(
            messages=context.messages,
            filepath=full_path,
            message_id=context.message_id,
            project_root=context.project_root,
        )
        # 将指令附加到结果中
```

---

## 测试

运行测试验证功能：

```bash
python -m pytest tests/test_instruction.py -v
```
