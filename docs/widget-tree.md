# Widget 布局树

本文档记录 TUI 界面的完整 Widget 层级结构。

## 完整布局树

```
REPLScreen (Screen)
│
├─ ScrollableContainer (id="content-area")  ← 滚动容器，自动吸底
│   │
│   ├─ WelcomeWidget (id="welcome-widget")
│   │   └─ Horizontal (classes="welcome-horizontal")
│   │       ├─ Container (id="left-panel")
│   │       │   ├─ Label (classes="welcome-message")
│   │       │   ├─ Clawd (VerticalGroup)
│   │       │   │   ├─ Static (classes="clawd-line")
│   │       │   │   ├─ Static (classes="clawd-line")
│   │       │   │   └─ Static (classes="clawd-line")
│   │       │   ├─ Label (classes="model-info")
│   │       │   └─ Label (classes="cwd-info")
│   │       │
│   │       └─ Container (id="right-panel")
│   │           ├─ Label (classes="section-title")
│   │           ├─ Label (classes="section-content")
│   │           ├─ Label (classes="section-title")
│   │           └─ Label (classes="section-content")
│   │
│   └─ MessageList (id="message-list", VerticalGroup)
│       │
│       ├─ [MessageWidget 或 AssistantMessageWidget] (多个...)
│       │   │
│       │   ├─ MessageWidget (非流式消息: USER/SYSTEM/TOOL)
│       │   │   ├─ [可选] Label (classes="message-role")
│       │   │   ├─ [可选] ThinkingBlockWidget (VerticalGroup)
│       │   │   │   └─ Collapsible (classes="thinking-collapsible")
│       │   │   │       └─ ThinkingWidget (TranscriptMarkdownWidget → Markdown)
│       │   │   ├─ [可选] Static (classes="message-content") 或 StreamingTextWidget
│       │   │   ├─ [可选] ToolUseWidget (VerticalGroup)
│       │   │   │   └─ Collapsible (classes="tool-collapsible")
│       │   │   │       └─ VerticalGroup (classes="tool-detail-body")
│       │   │   │           ├─ Static (classes="tool-param")
│       │   │   │           ├─ [可选] DiffView
│       │   │   │           ├─ [可选] Label (classes="tool-output-label")
│       │   │   │           └─ [可选] Static (classes="tool-result-preview")
│       │   │   └─ [可选] Static (classes="tool-result") + Static (classes="tool-result-preview")
│       │   │
│       │   └─ AssistantMessageWidget (流式消息: ASSISTANT)
│       │       └─ VerticalGroup (classes="message-content")
│       │           ├─ [可选] ThinkingBlockWidget (VerticalGroup)
│       │           │   └─ Collapsible (classes="thinking-collapsible")
│       │           │       └─ ThinkingWidget (TranscriptMarkdownWidget → Markdown)
│       │           ├─ [可选] StreamingTextWidget (TranscriptMarkdownWidget → Markdown)
│       │           └─ [可选] ToolUseWidget (多个...)
│       │               └─ Collapsible (classes="tool-collapsible")
│       │                   └─ VerticalGroup (classes="tool-detail-body")
│       │                       ├─ Static (classes="tool-param")
│       │                       ├─ [可选] DiffView
│       │                       ├─ [可选] Label (classes="tool-output-label")
│       │                       └─ [可选] Static (classes="tool-result-preview")
│       │
│
└─ VerticalGroup (id="input-area")
    ├─ Horizontal (id="processing-row")
    │   ├─ LoadingIndicator (id="processing-indicator")
    │   └─ Label (id="processing-label")
    ├─ InputTextArea (id="user-input", TextArea)
    └─ Label (id="context-usage")
```

## 关键文件路径

| 组件 | 文件 |
|------|------|
| REPLScreen | `claude_code/ui/screens.py` |
| MessageList | `claude_code/ui/message_widgets.py` |
| MessageWidget | `claude_code/ui/message_widgets.py` |
| AssistantMessageWidget | `claude_code/ui/message_widgets.py` |
| WelcomeWidget | `claude_code/ui/widgets.py` |
| InputTextArea | `claude_code/ui/widgets.py` |

## 自动滚动相关说明

**需要自动吸底的容器**: `ScrollableContainer (id="content-area")`

### Textual 官方最佳实践

1. **使用 `is_vertical_scroll_end`** 检查用户是否已在底部
2. **使用 `is_vertical_scrollbar_grabbed`** 检查用户是否正在拖动滚动条
3. **使用 `scroll_end(immediate=False)`** - 内部会自动调用 `call_after_refresh` 等待布局更新

### 避免的做法

- ❌ 不要多层嵌套 `call_after_refresh`
- ❌ 不要用 `set_timer` 做 hack
- ❌ 不要手搓 `_auto_follow_output` 状态，直接用内置属性
