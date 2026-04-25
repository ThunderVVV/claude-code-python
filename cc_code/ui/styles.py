"""TUI CSS styles."""

TUI_CSS = """
CCCodeApp,
REPLScreen {
    background: $background;
    color: $foreground;
}

#content-area {
    height: 1fr;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 1 0 0;
    scrollbar-size: 1 1;
    scrollbar-background: $surface;
    scrollbar-background-hover: $surface;
    scrollbar-background-active: $surface;
    scrollbar-color: $primary-muted;
    scrollbar-color-hover: $primary;
    scrollbar-color-active: $primary;
    scrollbar-corner-color: $surface;
}

ScrollableContainer {
    scrollbar-size: 1 1;
    scrollbar-background: transparent;
    scrollbar-background-hover: transparent;
    scrollbar-background-active: transparent;
    scrollbar-color: transparent;
    scrollbar-color-hover: transparent;
    scrollbar-color-active: transparent;
    scrollbar-corner-color: transparent;
}

WelcomeWidget {
    width: 100%;
    height: auto;
    border: round $border;
    background: transparent;
    padding: 0 1;
    margin: 0 1 1 1;
}

WelcomeWidget:focus {
    border: round $primary;
}

#left-panel {
    width: 1fr;
    height: auto;
    align: center top;
    padding: 0 1;
    min-height: 7;
}

#right-panel {
    width: 1fr;
    height: auto;
    min-height: 7;
    padding: 0 0 0 1;
    margin-left: 1;
    border-left: solid $border;
}

.welcome-horizontal {
    width: 100%;
    height: auto;
}

.welcome-message {
    text-style: bold;
    text-align: center;
    margin: 0 0 1 0;
}

.clawd-line {
    color: $primary;
    text-align: center;
}

.model-info,
.cwd-info,
.section-content,
#processing-label,
.tool-param,
.thinking-content,
#context-usage {
    color: $text-muted;
}

.model-info,
.cwd-info {
    text-align: center;
}

.section-title {
    color: $primary;
    text-style: bold;
    margin-top: 0;
}

.section-content {
    margin-left: 1;
}

#message-list {
    height: auto;
    padding: 0 0;
}

#input-area {
    height: auto;
    dock: bottom;
    padding: 0 1 0 0;
    background: $background;
}

#user-input {
    width: 1fr;
    height: auto;
    min-height: 1;
    max-height: 10;
    background: transparent;
    color: $foreground;
    border-top: solid $foreground 80%;
    border-bottom: solid $foreground 80%;
    border-left: none;
    border-right: none;
    padding: 0 1;
}

#user-input .text-area--cursor-line {
    background: transparent;
}

#context-usage {
    width: 1fr;
    height: auto;
    min-height: 1;
    padding: 0 1;
    margin: 0;
}

#processing-row {
    width: 100%;
    height: 1;
    margin: 0 0 0 0;
    display: none;
}

#processing-indicator {
    width: 3;
    height: 1;
    min-width: 3;
    color: $primary;
    margin-right: 1;
    margin-left: 1;
}

.message-role {
    text-style: bold;
    width: auto;
    margin: 0;
    padding: 0 1;
    background: $surface;
}

.role-user {
    color: $success;
    background: $success-muted;
}

.role-assistant {
    color: $primary;
    background: transparent;
}

.role-system {
    color: $success;
    background: $success-muted;
}

.role-tool {
    color: $secondary;
    background: $secondary-muted;
}

.message-block {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
    padding: 0 1;
    background: $boost;
}

.user-message-block {
    padding: 1 2;
    background: $surface;
}

.assistant-message-block {
    margin: 0 0 1 0;
    padding: 0;
    background: transparent;
}

.system-message-block {
    background: $surface;
}

.tool-result-block {
    border-top: solid $surface;
    border-bottom: solid $surface;
    padding: 0 0;
}

.tool-result-static {
    width: 100%;
    height: auto;
    padding: 0;
    background: transparent;
    color: $foreground 55%;
}

.tool-use-block {
    width: 100%;
    height: auto;
    padding: 0;
    background: transparent;
}

.message-body {
    margin-left: 0;
    padding: 0;
    width: 100%;
    height: auto;
}

.message-content {
    margin-left: 0;
    padding: 0;
}

.streaming-content {
    width: 100%;
    height: auto;
    margin-left: 0;
    padding: 0;
    background: transparent;
}

.markdown-host {
    width: 100%;
    height: auto;
    padding: 0 2;
}

.transcript-block,
.thinking-block,
.tool-use-block,
.web-enabled-label,
.file-expansion-collapsible {
    margin: 0;
}

.tool-header {
    color: $secondary;
    text-style: bold;
}

.tool-collapsible {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}

.tool-collapsible > Contents {
    padding: 0 2;
}

.tool-collapsible CollapsibleTitle {
    padding: 0;
    background: transparent;
}

.tool-use-details CollapsibleTitle {
    color: $foreground;
}

.tool-param {
    color: $foreground 55%;
}

.tool-result {
    margin-left: 0;
    margin-bottom: 0;
    padding: 0;
}

.tool-success {
    color: $success;
}

.tool-error {
    color: $error;
}

.tool-result-preview {
    color: $foreground 55%;
    margin-left: 0;
}

.tool-result-collapsible {
    background: transparent;
    border: none;
    margin: 0;
    padding: 0;
}

.tool-result-collapsible > Contents {
    padding: 0;
}

.tool-result-collapsible CollapsibleTitle {
    color: $text-muted;
    background: transparent;
    padding: 0;
}

.tool-result-content {
    color: $foreground 55%;
    margin: 0;
    padding: 0;
}

TextArea:focus {
    border: tall $primary;
}

Header {
    background: $panel;
    color: $foreground;
}

MessageList,
MessageWidget,
ToolUseWidget {
    width: 100%;
    height: auto;
}

Markdown {
    color: $foreground;
    padding: 0;
    link-style: none;
    link-style-hover: bold;
}

MarkdownH1,
MarkdownH2,
MarkdownH3,
MarkdownH4,
MarkdownH5,
MarkdownH6 {
    text-style: bold;
    margin: 0 0 1 0;
}

Markdown > MarkdownParagraph {
    margin: 0;
}

MarkdownBlockQuote {
    margin: 0 0 1 0;
    padding: 0;
}

MarkdownBlockQuote > BlockQuote {
    margin-left: 1;
    margin-top: 0;
}

MarkdownFence {
    margin: 0 0 0 0;
}

MarkdownFence > Label {
    padding: 0;
}

MarkdownTable {
    margin-bottom: 1;
}

MarkdownHorizontalRule {
    padding-top: 0;
    margin: 0 0 0 0;
}

.tool-detail-body {
    width: 100%;
    height: auto;
}

.thinking-block {
    width: 100%;
    height: auto;
    padding: 0 0 1 0;
    background: transparent;
}

.thinking-collapsible {
    background: transparent;
    border-top: none;
    border-left: none;
    padding: 0;
    margin: 0;
}

.thinking-collapsible:focus-within {
    background-tint: 0%;
}

.thinking-collapsible CollapsibleTitle {
    color: $text-muted;
    text-style: none;
    background: transparent;
    padding: 0;
    margin: 0;
}

.thinking-collapsible CollapsibleTitle:hover {
    background: transparent;
    color: $text-muted;
}

.thinking-collapsible CollapsibleTitle:focus {
    background: transparent;
    color: $text-muted;
    text-style: none;
}

.thinking-collapsible > Contents {
    padding: 0 2;
}

.thinking-content {
    text-style: italic;
    padding: 0;
    margin-left: 0;
    margin: 0;
    background: transparent;
}

.file-expansion {
    width: 100%;
    margin: 0 0 1 0;
    padding: 0;
    background: $surface;
    border-left: solid $primary;
    color: $text-muted;
}

.web-enabled-label {
    width: auto;
    padding: 0;
    color: $primary;
    background: transparent;
    border: none;
}

.file-expansion-collapsible {
    width: 100%;
    background: transparent;
    border: none;
    padding: 0;
    height: auto;
}

.file-expansion-collapsible CollapsibleTitle {
    padding: 0;
    color: $primary;
    background: transparent;
}

.file-expansion-collapsible CollapsibleTitle:hover {
    background: transparent;
}

.file-expansion-collapsible CollapsibleTitle:focus {
    background: transparent;
}

.file-expansion-collapsible > Contents {
    padding: 0 2;
}

.file-expansion-content {
    color: $text-muted;
    padding: 0;
}
"""
