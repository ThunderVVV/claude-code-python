"""TUI CSS styles - aligned with TypeScript theme"""

TUI_CSS = """
/* Claude Code Python TUI Styles */
/* Color theme aligned with TypeScript version: rgb(215,119,87) - Claude Orange */

/* App-level styles */
ClaudeCodeApp {
    background: #1a1a1a;
    color: #ffffff;
}

REPLScreen {
    background: #1a1a1a;
    color: #ffffff;
}

/* Main content scrollable area */
#content-area {
    height: 1fr;
    overflow-y: auto;
    padding: 0 1;
}

/* Scrollbar styling - Claude Orange theme */
ScrollableContainer {
    scrollbar-size: 1 1;
    scrollbar-background: #2a2a2a;
    scrollbar-background-hover: #3a3a3a;
    scrollbar-color: rgb(215,119,87);
    scrollbar-color-hover: rgb(235,159,127);
}

ScrollableContainer:focus {
    scrollbar-color: rgb(235,159,127);
    scrollbar-color-hover: rgb(255,179,147);
}

/* Welcome widget with border */
WelcomeWidget {
    width: 100%;
    height: auto;
    border: round rgb(215,119,87);
    padding: 0 1;
    margin: 0 1 1 1;
}

WelcomeWidget:focus {
    border: round rgb(235,159,127);
}

/* Left panel */
#left-panel {
    width: 1fr;
    height: auto;
    align: center top;
    padding: 0 1;
    min-height: 7;
}

/* Right panel */
#right-panel {
    width: 1fr;
    height: auto;
    min-height: 7;
    padding: 0 0 0 1;
    margin-left: 1;
    border-left: solid rgb(215,119,87);
}

/* Horizontal layout for welcome */
.welcome-horizontal {
    width: 100%;
    height: auto;
}

/* Welcome message */
.welcome-message {
    color: #ffffff;
    text-style: bold;
    text-align: center;
    margin: 0 0 1 0;
}

/* Clawd ASCII art */
.clawd-line {
    color: rgb(215,119,87);
    text-align: center;
}

/* Model info line */
.model-info {
    color: rgb(153,153,153);
    text-align: center;
}

/* CWD line */
.cwd-info {
    color: rgb(153,153,153);
    text-align: center;
}

/* Section title */
.section-title {
    color: rgb(215,119,87);
    text-style: bold;
    margin-top: 0;
}

/* Section content */
.section-content {
    color: rgb(153,153,153);
    margin-left: 1;
}

/* Message list container */
#message-list {
    height: auto;
    padding: 0 2;
}

/* Input area - fixed at bottom */
#input-area {
    height: auto;
    dock: bottom;
    padding: 1 2;
    background: #1a1a1a;
    border-top: solid rgb(215,119,87);
}

#user-input {
    width: 1fr;
    background: #2a2a2a;
}

#processing-row {
    width: 100%;
    height: 1;
    margin: 0 0 1 0;
    display: none;
}

#processing-indicator {
    width: 3;
    height: 1;
    min-width: 3;
    color: rgb(215,119,87);
    margin-right: 1;
}

#processing-label {
    width: auto;
    color: rgb(153,153,153);
}

/* Message roles */
.message-role {
    text-style: bold;
    width: auto;
    margin: 0;
    padding: 0 1;
    background: #262626;
}

.role-user {
    color: rgb(78,186,101);
    background: #1b2b1f;
}

.role-assistant {
    color: rgb(215,119,87);
    background: transparent;
}

.role-system {
    color: rgb(255,193,7);
    background: #2c2816;
}

.role-tool {
    color: rgb(235,159,127);
    background: #2d221d;
}

.message-block {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
    padding: 1 1;
    background: #171717;
}

.user-message-block {
    background: #2a2d31;
}

.assistant-message-block {
    margin: 0;
    padding: 0;
    background: transparent;
}

.system-message-block {
    border-left: solid rgb(255,193,7);
    background: #211f12;
}

.tool-result-block {
    border-left: solid rgb(235,159,127);
    background: #171a20;
}

.tool-use-block {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
    padding: 0 1;
    background: #141414;
}

.tool-inline-result {
    width: 100%;
    height: auto;
    margin-left: 0;
    margin-top: 0;
}

.tool-inline-summary {
    margin: 0;
}

/* Message content */
.message-content {
    margin-left: 0;
    margin-bottom: 0;
    padding: 0;
}

/* Streaming message content - inline update */
.streaming-content {
    width: 100%;
    margin-left: 0;
    margin-bottom: 1;
    padding: 0 1;
    color: #ffffff;
    background: transparent;
}

/* Tool styling */
.tool-header {
    color: rgb(235,159,127);
    text-style: bold;
}

.tool-param {
    color: rgb(153,153,153);
    margin-left: 1;
}

.tool-collapsible {
    background: transparent;
    border-top: none;
    padding: 0;
    margin: 0;
}

.tool-collapsible > Contents {
    padding: 0 0 0 1;
}

.tool-collapsible CollapsibleTitle {
    padding: 0;
    background: transparent;
}

.tool-use-details CollapsibleTitle {
    color: rgb(235,159,127);
}

.tool-result-preview-toggle CollapsibleTitle {
    color: rgb(153,153,153);
    margin-left: 2;
}

.tool-result {
    margin-left: 0;
    margin-bottom: 0;
    padding: 0 1;
}

.tool-success {
    color: rgb(78,186,101);
}

.tool-error {
    color: rgb(255,107,128);
}

.tool-result-summary {
    color: #ffffff;
    text-style: bold;
    margin: 0;
}

.tool-result-preview {
    color: rgb(210,210,210);
    margin-left: 2;
}

/* Focus styles */
Input:focus {
    border: tall rgb(215,119,87);
}

/* Header */
Header {
    background: #1a1a1a;
    color: rgb(215,119,87);
}

MessageList {
    width: 100%;
    height: auto;
}

MessageWidget, AssistantMessageWidget, ToolResultWidget {
    width: 100%;
    height: auto;
}

ToolUseWidget {
    width: 100%;
    height: auto;
}

.tool-result-body {
    width: 100%;
    height: auto;
}
"""
