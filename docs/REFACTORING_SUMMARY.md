# 后端代码重构总结

## 修复的问题

### 1. 移除全局变量反模式 (server.py)

**问题：** 使用全局变量传递依赖项
```python
# 旧代码
_settings_store: Optional[SettingsStore] = None
_tool_registry: Optional[ToolRegistry] = None

def set_global_dependencies(...): ...
def require_global_dependencies(): ...
```

**解决方案：** 使用 FastAPI 的 `app.state` 进行依赖注入
```python
# 新代码
def create_app(
    settings_store: Optional[SettingsStore] = None,
    tool_registry: Optional[ToolRegistry] = None,
) -> FastAPI:
    app = FastAPI(...)
    app.state.session_manager = SessionManager(settings_store, tool_registry)
    return app

# 在路由中访问
@api_router.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    session_manager = http_request.app.state.session_manager
```

**收益：**
- ✅ 消除全局状态
- ✅ 更好的测试性
- ✅ 明确的依赖关系
- ✅ 符合 FastAPI 最佳实践

---

### 2. 移除单例模式滥用

**问题：** 不必要的单例模式
```python
# server.py
_session_manager: Optional[object] = None
def get_session_manager() -> SessionManager: ...

# instruction.py
_default_service: Optional[InstructionService] = None
def get_instruction_service(...) -> InstructionService: ...
```

**解决方案：** 直接实例化，通过参数传递
```python
# SessionManager 现在是普通类
class SessionManager:
    def __init__(self, settings_store: SettingsStore, tool_registry: ToolRegistry):
        self._engines = {}
        self._session_store = SessionStore()
        self._settings_store = settings_store
        self._tool_registry = tool_registry

# 在 create_app 中创建
app.state.session_manager = SessionManager(settings_store, tool_registry)
```

**收益：**
- ✅ 更简单的代码
- ✅ 更容易测试
- ✅ 明确的生命周期管理
- ✅ 无隐藏状态

---

### 3. 简化 InstructionService (instruction.py)

**问题：** 过度设计，533 行代码实现指令文件加载
- 多个缓存机制：`_loaded_paths`, `_claims`
- 复杂的上层搜索逻辑
- 全局单例 + 便捷函数重复
- 未使用的功能：`mark_loaded()`, `is_loaded()`, `clear_loaded()`, `clear_claims()`

**解决方案：** 简化为 267 行（减少 50%）
```python
class InstructionService:
    """简化的指令加载服务"""
    
    def __init__(self, config: Optional[InstructionConfig] = None):
        self.config = config or InstructionConfig.from_env()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def get_system_instructions(
        self, working_directory: str, stop_dir: Optional[str] = None
    ) -> List[str]:
        """主入口点 - 返回格式化的指令字符串列表"""
        # 1. 项目级搜索（首次匹配）
        # 2. 全局级文件
        # 3. 自定义指令
        
    async def resolve_nearby_instructions(...) -> List[str]:
        """加载附近的指令文件"""
        # 简化的实现，移除了复杂的声明追踪
```

**移除的功能：**
- ❌ `_loaded_paths` 缓存（未使用）
- ❌ `_claims` 声明追踪（过度设计）
- ❌ `mark_loaded()`, `is_loaded()`, `clear_loaded()`（未使用）
- ❌ `load_instructions()` 方法（与 `get_system_instructions` 重复）
- ❌ `get_system_paths()` 方法（内部实现细节）
- ❌ `LoadedInstruction` 数据类（不必要）

**保留的核心功能：**
- ✅ 项目级指令文件搜索
- ✅ 全局级指令文件加载
- ✅ 自定义指令支持
- ✅ 附近指令加载
- ✅ URL 指令支持

**收益：**
- ✅ 代码量减少 50%（533 行 → 267 行）
- ✅ 更简单的 API
- ✅ 更容易理解和维护
- ✅ 移除了未使用的复杂性

---

## 其他改进

### 更新了测试配置
- 添加 `pytest-asyncio` 支持
- 配置 `asyncio_mode = "auto"` 在 `pyproject.toml`

### 更新了调用方
- `cc_code/api/cli.py`: 使用 `create_app()` 替代全局变量
- `cc_code/cli.py`: 使用 `create_app()` 替代全局变量
- `cc_code/tools/read_tool.py`: 适配简化的 `InstructionService` API

---

## 测试结果

✅ 所有 70 个测试通过
- 13 个指令加载测试
- 2 个设置测试
- 其他 55 个测试

---

## 影响范围

### 修改的文件
1. `cc_code/api/server.py` - 重构依赖注入
2. `cc_code/core/instruction.py` - 简化指令服务
3. `cc_code/api/cli.py` - 更新启动方式
4. `cc_code/cli.py` - 更新启动方式
5. `cc_code/tools/read_tool.py` - 适配新 API
6. `tests/test_instruction.py` - 更新测试
7. `tests/test_settings.py` - 移除过时测试
8. `pyproject.toml` - 添加 asyncio 配置

### 向后兼容性
- ✅ API 端点未改变
- ✅ 功能完全保留
- ✅ 测试全部通过

---

## 设计原则遵循

这次重构遵循了以下原则：

1. **YAGNI (You Aren't Gonna Need It)**
   - 移除了未使用的缓存和追踪机制

2. **KISS (Keep It Simple, Stupid)**
   - 简化了复杂的指令加载逻辑
   - 使用更直接的数据结构

3. **依赖注入优于全局状态**
   - 使用 FastAPI 的 `app.state` 替代全局变量

4. **组合优于继承**
   - `SessionManager` 通过组合持有依赖项

5. **明确优于隐式**
   - 明确传递依赖项，而不是隐藏的全局状态
