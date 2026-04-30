<template>
    <div class="app-shell flex h-screen flex-row overflow-hidden">
        <!-- Left Sidebar -->
        <aside class="w-80 h-full bg-gray-50 border-r border-gray-200 flex flex-col hidden md:flex">
            <!-- Sidebar Header -->
            <div class="p-4 border-b border-gray-200">
                <button
                    @click="openNewSessionModal"
                    :disabled="isStreaming"
                    class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors text-sm font-medium disabled:text-gray-400 disabled:bg-gray-50 disabled:hover:bg-gray-50"
                >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                    新会话
                </button>
            </div>

            <!-- Session List -->
            <div class="flex-1 overflow-y-auto p-2">
                <div v-if="sessionsLoading" class="p-4 text-center text-gray-500 text-sm">加载中...</div>
                <div v-else-if="sessions.length === 0" class="p-4 text-center text-gray-400 text-xs">暂无会话</div>
                <div v-else class="space-y-0">
                    <div
                        v-for="sess in sessions"
                        :key="sess.session_id"
                        @click="loadSession(sess.session_id)"
                        class="session-item group flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors"
                        :class="{ 'bg-white shadow-sm border border-gray-200': sess.session_id === sessionId, 'hover:bg-white/60': sess.session_id !== sessionId }"
                    >
                        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                        </svg>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm text-gray-700 truncate font-medium">{{ sess.title || '未命名会话' }}</div>
                            <div class="text-xs text-gray-400 mt-0.5">{{ sess.message_count || 0 }} 条消息</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sidebar Footer: Settings Button -->
            <div class="p-2 border-t border-gray-200">
                <button
                    @click="showSettingsModal = true"
                    class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors text-sm"
                >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    设置
                </button>
            </div>
        </aside>

        <!-- Main Content -->
        <div class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
            <!-- Header -->
            <header class="h-12 border-b border-gray-200 flex items-center justify-between px-3 bg-white">
                <div class="flex items-center gap-2">
                    <!-- Mobile Menu Button -->
                    <button @click="showMobileSidebar = true" class="md:hidden p-1.5 rounded-lg hover:bg-gray-100 text-gray-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                        </svg>
                    </button>
                    <!-- Model Selector -->
                    <div class="relative" data-model-selector>
                        <button @click="showModelSelector = !showModelSelector" class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-gray-100 text-gray-700 text-sm font-medium transition-colors">
                            <span class="truncate max-w-[200px] sm:max-w-[320px]">{{ currentModelName || '选择模型' }}</span>
                            <svg class="w-4 h-4 text-gray-500" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                        </button>

                        <!-- Model Dropdown -->
                        <div v-if="showModelSelector" class="absolute left-0 top-full mt-1 w-80 bg-white rounded-xl shadow-lg z-50 border border-gray-200 py-1">
                            <div class="px-3 py-2 border-b border-gray-100">
                                <h3 class="text-sm font-medium text-gray-700">选择模型</h3>
                            </div>
                            <div class="max-h-72 overflow-y-auto py-1">
                                <div v-if="modelsLoading" class="p-4 text-center text-gray-500 text-sm">加载中...</div>
                                <div v-else-if="models.length === 0" class="p-4 text-center text-gray-500 text-sm">暂无可用模型</div>
                                <div v-else>
                                    <div
                                        v-for="model in models"
                                        :key="model.model_id"
                                        @click.stop="switchModel(model.model_id)"
                                        class="mx-1 px-3 py-2.5 cursor-pointer transition-colors hover:bg-gray-100 rounded-lg"
                                        :class="{ 'bg-gray-100 hover:bg-gray-200': model.model_id === currentModelId }"
                                    >
                                        <div class="flex items-center justify-between">
                                            <div class="flex-1 min-w-0">
                                                <div class="flex items-center gap-2">
                                                    <span class="text-sm font-medium text-gray-900 truncate">{{ model.model_name }}</span>
                                                    <span v-if="model.model_id === currentModelId" class="text-xs bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded font-medium">当前</span>
                                                </div>
                                                <div class="text-xs text-gray-500 mt-0.5">{{ model.model_id }}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </header>

            <!-- Chat Container -->
            <div class="flex-1 flex flex-col min-h-0 bg-white">
                <!-- Messages Area -->
                <div ref="messagesContainer" class="messages-area flex-1 overflow-y-auto overflow-x-hidden" @scroll="handleMessagesScroll">
                    <div class="chat-container py-6 space-y-1 px-4">
                        <!-- Welcome Message -->
                        <div v-if="messages.length === 0" class="text-center py-16">
                            <div class="w-16 h-16 mx-auto mb-6 bg-gray-100 rounded-2xl flex items-center justify-center">
                                <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                                </svg>
                            </div>
                            <h2 class="text-2xl font-semibold text-gray-900 mb-2">有什么可以帮你的吗？</h2>
                            <p class="text-gray-500">我可以帮你编写代码、调试问题、解释概念。</p>
                        </div>

                        <!-- Messages -->
                        <MessageItem
                            v-for="(msg, index) in messages"
                            :key="index"
                            :message="msg"
                            @toggle-collapse="toggleCollapse"
                        />

                        <!-- Typing Indicator -->
                        <div v-if="isTyping" class="flex justify-start fade-in">
                            <div class="w-full">
                                <div class="flex items-start gap-3">
                                    <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                                        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                        </svg>
                                    </div>
                                    <div class="message-assistant rounded-2xl rounded-tl-sm px-4 py-2 bg-gray-50">
                                        <div class="typing-indicator flex gap-1.5">
                                            <span class="w-2 h-2 rounded-full bg-gray-400"></span>
                                            <span class="w-2 h-2 rounded-full bg-gray-400"></span>
                                            <span class="w-2 h-2 rounded-full bg-gray-400"></span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Input Area -->
                <div class="composer-shell bg-white px-4 pb-6">
                    <div class="chat-container">
                        <form @submit.prevent="sendMessage">
                            <!-- Input Container with Border -->
                            <div class="relative bg-white border border-gray-300 rounded-2xl overflow-hidden focus-within:border-gray-400 transition-colors shadow-sm">
                                <!-- Textarea -->
                                <textarea
                                    ref="messageInput"
                                    v-model="inputText"
                                    rows="1"
                                    :placeholder="inputPlaceholder"
                                    class="w-full bg-transparent px-4 py-3.5 text-gray-900 placeholder-gray-500 focus:outline-none resize-none"
                                    style="max-height: 200px; min-height: 52px;"
                                    @input="autoResize"
                                    @keydown="handleKeydown"
                                    :disabled="isStreaming"
                                ></textarea>
                                <!-- Button Row (Last Line) -->
                                <div class="flex items-center justify-between px-3 py-2">
                                    <!-- Web Search Toggle (Left) -->
                                    <button
                                        type="button"
                                        @click="webSearchEnabled = !webSearchEnabled"
                                        class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors"
                                        :class="webSearchEnabled ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-100'"
                                        :disabled="isStreaming"
                                    >
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>
                                        </svg>
                                        联网搜索
                                    </button>
                                    <!-- Send/Interrupt Button (Right) -->
                                    <button
                                        v-if="!isStreaming"
                                        type="submit"
                                        :disabled="isLoading || !inputText.trim()"
                                        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 text-white text-xs font-medium disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
                                    >
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                                        </svg>
                                        发送
                                    </button>
                                    <button
                                        v-else
                                        type="button"
                                        @click="sendInterrupt"
                                        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium transition-colors"
                                    >
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
                                        </svg>
                                        停止
                                    </button>
                                </div>
                            </div>
                        </form>
                        <!-- Workspace & Token Info Bar -->
                        <div class="mt-2 flex items-center justify-between px-1">
                            <div class="flex items-center gap-2">
                                <!-- Workspace Button -->
                                <div class="relative">
                                    <button
                                        data-info-popover-trigger
                                        @click="toggleWorkspaceDetails"
                                        class="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                                    >
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                                        </svg>
                                        <span class="truncate max-w-[120px] sm:max-w-[200px]">{{ currentWorkspace ? currentWorkspace.split('/').pop() : '未设置' }}</span>
                                    </button>

                                    <!-- Workspace Details Popover -->
                                    <div v-if="showWorkspaceDetails" data-info-popover class="absolute bottom-full left-0 z-40 mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-gray-200 bg-white p-3 text-sm shadow-lg">
                                        <div class="flex items-center justify-between mb-2">
                                            <span class="font-medium text-gray-700">工作区</span>
                                            <button @click="showWorkspaceDetails = false" class="text-gray-400 hover:text-gray-600">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                                </svg>
                                            </button>
                                        </div>
                                        <div class="text-gray-600 break-all font-mono text-xs">{{ currentWorkspace || '未设置工作区' }}</div>
                                    </div>
                                </div>

                                <!-- Token Usage Button -->
                                <div class="relative">
                                    <button
                                        data-info-popover-trigger
                                        @click="toggleTokenDetails"
                                        class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                                    >
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                        </svg>
                                        <span>{{ formatTokens(tokenUsed) }} / {{ formatTokens(Number(currentModelContext) || 128000) }}</span>
                                    </button>

                                    <!-- Token Details Popover -->
                                    <div v-if="showTokenDetails" data-info-popover class="absolute bottom-full left-0 z-40 mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-gray-200 bg-white p-3 text-sm shadow-lg">
                                        <div class="flex items-center justify-between mb-2">
                                            <span class="font-medium text-gray-700">Token 使用情况</span>
                                            <button @click="showTokenDetails = false" class="text-gray-400 hover:text-gray-600">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                                </svg>
                                            </button>
                                        </div>
                                        <div class="space-y-1">
                                            <div class="flex items-center justify-between text-xs">
                                                <span class="text-gray-500">已使用</span>
                                                <span class="text-gray-700 font-medium">{{ formatTokens(tokenUsed) }}</span>
                                            </div>
                                            <div class="flex items-center justify-between text-xs">
                                                <span class="text-gray-500">上下文限制</span>
                                                <span class="text-gray-700 font-medium">{{ formatTokens(Number(currentModelContext) || 128000) }}</span>
                                            </div>
                                            <div class="flex items-center justify-between text-xs">
                                                <span class="text-gray-500">剩余</span>
                                                <span class="text-gray-700 font-medium">{{ formatTokens((Number(currentModelContext) || 128000) - tokenUsed) }}</span>
                                            </div>
                                            <div class="mt-2 pt-2 border-t border-gray-200">
                                                <div class="w-full bg-gray-200 rounded-full h-1.5">
                                                    <div
                                                        class="bg-purple-500 h-1.5 rounded-full transition-all duration-300"
                                                        :style="{ width: Math.min((tokenUsed / (Number(currentModelContext) || 128000)) * 100, 100) + '%' }"
                                                    ></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <span class="text-xs text-gray-400">AI 生成的内容可能不准确</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Mobile Sidebar Overlay -->
        <div v-if="showMobileSidebar" class="fixed inset-0 z-50 md:hidden" @click="showMobileSidebar = false">
            <div class="absolute inset-0 bg-black/50" @click="showMobileSidebar = false"></div>
            <aside class="absolute left-0 top-0 h-full w-80 bg-gray-50 border-r border-gray-200 flex flex-col">
                <!-- Mobile Sidebar Header -->
                <div class="p-4 border-b border-gray-200 flex items-center justify-between">
                    <span class="font-semibold text-gray-900">会话列表</span>
                    <button @click="showMobileSidebar = false" class="p-1 rounded-lg hover:bg-gray-200 text-gray-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <!-- Mobile Session List -->
                <div class="flex-1 overflow-y-auto p-2">
                    <button
                        @click="openNewSessionModal(); showMobileSidebar = false"
                        :disabled="isStreaming"
                        class="w-full flex items-center gap-2 px-3 py-2 mb-3 bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors text-sm disabled:text-gray-400 disabled:bg-gray-50 disabled:hover:bg-gray-50"
                    >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        新会话
                    </button>
                    <div v-if="sessionsLoading" class="p-4 text-center text-gray-500 text-sm">加载中...</div>
                    <div v-else-if="sessions.length === 0" class="p-4 text-center text-gray-400 text-xs">暂无会话</div>
                    <div v-else class="space-y-0">
                        <div
                            v-for="sess in sessions"
                            :key="sess.session_id"
                            @click="loadSession(sess.session_id); showMobileSidebar = false"
                            class="session-item group flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors"
                            :class="{ 'bg-white shadow-sm border border-gray-200': sess.session_id === sessionId, 'hover:bg-white/60': sess.session_id !== sessionId }"
                        >
                            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                            </svg>
                            <div class="flex-1 min-w-0">
                                <div class="text-sm text-gray-700 truncate font-medium">{{ sess.title || '未命名会话' }}</div>
                                <div class="text-xs text-gray-400 mt-0.5">{{ sess.message_count || 0 }} 条消息</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Mobile Sidebar Footer: Settings Button -->
                <div class="p-2 border-t border-gray-200">
                    <button
                        @click="showSettingsModal = true; showMobileSidebar = false"
                        class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors text-sm"
                    >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        设置
                    </button>
                </div>
            </aside>
        </div>

        <!-- New Session Modal -->
        <div v-if="showNewSessionModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div class="absolute inset-0 bg-black/50" @click="closeNewSessionModal"></div>
            <div class="relative bg-white rounded-2xl shadow-2xl w-[92vw] max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
                <div class="p-4 border-b border-gray-200 flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-semibold text-gray-900">选择工作目录</h2>
                        <p class="text-sm text-gray-500 mt-1">确认后只保存目录，首次发送消息时再创建新会话。</p>
                    </div>
                    <button @click="closeNewSessionModal" class="p-1 rounded-lg hover:bg-gray-100 text-gray-500">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <div class="p-4 border-b border-gray-200 space-y-3">
                    <form class="flex flex-col gap-2 sm:flex-row" @submit.prevent="submitWorkspaceBrowserPath">
                        <input
                            v-model="workspaceBrowserInput"
                            type="text"
                            class="flex-1 h-11 px-3 border border-gray-300 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-400"
                            placeholder="输入目录路径"
                        >
                        <div class="flex gap-2">
                            <button
                                type="button"
                                @click="browseWorkspaceParent"
                                :disabled="workspaceBrowserLoading || !workspaceBrowserParentPath"
                                class="h-11 px-3 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 disabled:text-gray-300 disabled:hover:bg-white"
                            >
                                上一级
                            </button>
                            <button
                                type="submit"
                                :disabled="workspaceBrowserLoading"
                                class="h-11 px-4 bg-gray-900 text-white rounded-lg text-sm font-medium disabled:bg-gray-300"
                            >
                                打开
                            </button>
                        </div>
                    </form>

                    <div class="flex flex-wrap gap-2">
                        <button
                            v-for="root in workspaceBrowserRoots"
                            :key="root.path"
                            type="button"
                            @click="browseWorkspace(root.path)"
                            class="px-3 py-1.5 rounded-full border text-xs transition-colors"
                            :class="root.path === workspaceBrowserPath ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-600 hover:bg-gray-100'"
                        >
                            {{ root.name }}
                        </button>
                    </div>

                    <div class="rounded-xl bg-gray-50 border border-gray-200 px-3 py-2">
                        <div class="text-xs text-gray-500 mb-1">当前目录</div>
                        <div class="font-mono text-sm text-gray-800 break-all">{{ workspaceBrowserPath || '未选择' }}</div>
                    </div>

                    <div v-if="workspaceBrowserError" class="text-sm text-red-600">{{ workspaceBrowserError }}</div>
                </div>

                <div class="flex-1 overflow-y-auto p-4 bg-gray-50/60">
                    <div v-if="workspaceBrowserLoading" class="h-full min-h-40 flex items-center justify-center text-sm text-gray-500">
                        正在加载目录...
                    </div>
                    <div v-else-if="workspaceBrowserDirectories.length === 0" class="h-full min-h-40 flex items-center justify-center text-sm text-gray-400">
                        当前目录下没有可浏览的子目录
                    </div>
                    <div v-else class="space-y-2">
                        <button
                            v-for="directory in workspaceBrowserDirectories"
                            :key="directory.path"
                            type="button"
                            @click="browseWorkspace(directory.path)"
                            class="w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl border border-gray-200 bg-white text-left hover:border-gray-300 hover:bg-gray-100 transition-colors"
                        >
                            <div class="min-w-0">
                                <div class="text-sm font-medium text-gray-800 truncate">{{ directory.name }}</div>
                                <div class="text-xs text-gray-500 font-mono truncate mt-1">{{ directory.path }}</div>
                            </div>
                            <div class="flex items-center gap-2 text-gray-400 flex-shrink-0">
                                <span v-if="directory.is_symlink" class="text-[11px] uppercase tracking-wide">Link</span>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                </svg>
                            </div>
                        </button>
                    </div>
                </div>

                <div class="p-4 border-t border-gray-200 flex items-center justify-between gap-3">
                    <div class="text-xs text-gray-500">
                        新会话将使用当前目录作为工作目录，并在首条消息发送时创建。
                    </div>
                    <div class="flex items-center gap-2">
                        <button @click="closeNewSessionModal" class="px-4 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-100">
                            取消
                        </button>
                        <button
                            @click="startNewSession(workspaceBrowserPath)"
                            :disabled="workspaceBrowserLoading || !workspaceBrowserPath"
                            class="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium disabled:bg-gray-300"
                        >
                            以此目录开始新会话
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Settings Modal -->
        <div v-if="showSettingsModal" class="fixed inset-0 z-50 flex items-center justify-center">
            <div class="absolute inset-0 bg-black/50" @click="showSettingsModal = false"></div>
            <div class="relative bg-white rounded-2xl shadow-2xl w-[90vw] max-w-4xl max-h-[80vh] flex flex-col overflow-hidden">
                <!-- Modal Header -->
                <div class="p-4 border-b border-gray-200 flex items-center justify-between">
                    <h2 class="text-lg font-semibold text-gray-900">设置</h2>
                    <button @click="showSettingsModal = false" class="p-1 rounded-lg hover:bg-gray-100 text-gray-500">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <!-- Modal Body (Double Column) -->
                <div class="flex flex-1 overflow-hidden">
                    <!-- Left Sidebar -->
                    <div class="w-48 border-r border-gray-200 bg-gray-50 p-2">
                        <div class="space-y-1">
                            <button
                                @click="activeSettingsTab = 'models'"
                                class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                                :class="{ 'bg-white shadow-sm text-gray-900': activeSettingsTab === 'models', 'text-gray-600 hover:bg-gray-100': activeSettingsTab !== 'models' }"
                            >
                                模型设置
                            </button>
                        </div>
                    </div>

                    <!-- Right Content -->
                    <div class="flex-1 overflow-y-auto p-4">
                        <!-- Model Settings -->
                        <div v-if="activeSettingsTab === 'models'" class="space-y-4">
                            <div v-if="settingsLoading" class="text-center text-gray-500 py-8">加载中...</div>
                            <div v-else>
                                <div class="space-y-4">
                                    <div class="grid grid-cols-2 gap-4">
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-1">供应商</label>
                                            <select v-model="selectedProvider" class="w-full h-10 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-500">
                                                <option v-for="(provider, id) in settings.providers" :key="id" :value="id">{{ id }}</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-1 opacity-0">操作</label>
                                            <button @click="fetchProviderModels" class="w-full h-10 px-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
                                                获取可用模型
                                            </button>
                                        </div>
                                    </div>

                                    <div v-if="availableModels.length > 0" class="space-y-2">
                                        <label class="block text-sm font-medium text-gray-700">可用模型</label>
                                        <div class="border border-gray-200 rounded-lg p-2 max-h-64 overflow-y-auto">
                                            <div v-for="model in availableModels" :key="model.id" class="flex items-center gap-2 px-2 py-2 hover:bg-gray-50 rounded">
                                                <input
                                                    type="checkbox"
                                                    :id="`model-${model.id}`"
                                                    :value="model.id"
                                                    v-model="selectedModels"
                                                    class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                                >
                                                <label :for="`model-${model.id}`" class="flex-1 text-sm text-gray-700 cursor-pointer">
                                                    {{ model.name }}
                                                </label>
                                            </div>
                                        </div>
                                        <button @click="addSelectedModels" class="px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm">
                                            添加选中模型
                                        </button>
                                    </div>

                                    <div class="space-y-2">
                                        <label class="block text-sm font-medium text-gray-700">已添加模型</label>
                                        <div class="border border-gray-200 rounded-lg divide-y divide-gray-100">
                                            <div v-for="(model, modelId) in currentProvider.models" :key="modelId" class="flex items-center justify-between px-3 py-2">
                                                <div class="flex items-center gap-4">
                                                    <div>
                                                        <div class="text-sm font-medium text-gray-900">{{ model.model_name }}</div>
                                                    </div>
                                                    <div class="flex items-center gap-1.5">
                                                        <span class="text-xs text-gray-500">上下文:</span>
                                                        <input
                                                            v-model.number="model.context"
                                                            type="number"
                                                            min="1"
                                                            class="w-24 px-2 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                                                        >
                                                        <span class="text-xs text-gray-500">tokens</span>
                                                    </div>
                                                </div>
                                                <button @click="deleteModel(modelId)" class="text-red-500 hover:text-red-700 text-xs">删除</button>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="pt-4 border-t border-gray-200">
                                        <button @click="saveSettings" class="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors">
                                            保存设置
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch } from 'vue'
import MessageItem from './components/MessageItem.vue'
import { useChat } from './composables/useChat'

const {
    messages,
    inputText,
    isLoading,
    isStreaming,
    isTyping,
    sessionId,
    tokenUsed,
    sessions,
    sessionsLoading,
    showMobileSidebar,
    showWorkspaceDetails,
    showTokenDetails,
    showModelSelector,
    models,
    modelsLoading,
    currentModelId,
    currentModelName,
    currentModelContext,
    currentWorkspace,
    showNewSessionModal,
    webSearchEnabled,
    sessionHasUsedWebSearch,
    workspaceBrowserLoading,
    workspaceBrowserError,
    workspaceBrowserPath,
    workspaceBrowserInput,
    workspaceBrowserParentPath,
    workspaceBrowserDirectories,
    workspaceBrowserRoots,
    showSettingsModal,
    activeSettingsTab,
    settings,
    settingsLoading,
    selectedProvider,
    availableModels,
    selectedModels,
    currentProvider,
    inputPlaceholder,
    messagesContainer,
    messageInput,
    autoResize,
    handleMessagesScroll,
    handleKeydown,
    sendMessage,
    sendInterrupt,
    startNewSession,
    openNewSessionModal,
    closeNewSessionModal,
    browseWorkspace,
    browseWorkspaceParent,
    submitWorkspaceBrowserPath,
    loadSession,
    switchModel,
    toggleCollapse,
    scrollToBottom,
    formatTokens,
    getCurrentWorkspace,
    loadSessions,
    loadModels,
    toggleWorkspaceDetails,
    toggleTokenDetails,
    closeInfoPopovers,
    syncViewportMetrics,
    fetchProviderModels,
    addSelectedModels,
    deleteModel,
    saveSettings,
} = useChat()

// Global keyboard shortcuts
const getSelectedText = () => {
    const activeElement = document.activeElement
    if (
        activeElement &&
        typeof activeElement.selectionStart === 'number' &&
        typeof activeElement.selectionEnd === 'number' &&
        typeof activeElement.value === 'string'
    ) {
        const { selectionStart, selectionEnd, value } = activeElement
        if (selectionStart !== selectionEnd) {
            return value.slice(selectionStart, selectionEnd)
        }
    }
    return window.getSelection()?.toString() || ''
}

const copySelectedText = async (e) => {
    const selectedText = getSelectedText()
    if (!selectedText || !navigator.clipboard?.writeText) return false

    try {
        e.preventDefault()
        await navigator.clipboard.writeText(selectedText)
        return true
    } catch (error) {
        console.error('Copy failed:', error)
        return false
    }
}

const handleGlobalKeydown = async (e) => {
    const key = e.key.toLowerCase()
    const isCopyShortcut = (e.metaKey || e.ctrlKey) && key === 'c' && !e.altKey

    if (isCopyShortcut) {
        await copySelectedText(e)
        return
    }

    if (e.key === 'Escape') {
        if (showNewSessionModal.value) {
            closeNewSessionModal()
        } else if (showModelSelector.value) {
            showModelSelector.value = false
        } else if (showWorkspaceDetails.value || showTokenDetails.value) {
            closeInfoPopovers()
        } else if (isStreaming.value) {
            e.preventDefault()
            sendInterrupt()
        }
    }
}

const handleGlobalClick = (e) => {
    if (showModelSelector.value) {
        const modelSelector = document.querySelector('[data-model-selector]')
        if (modelSelector && !modelSelector.contains(e.target)) {
            showModelSelector.value = false
        }
    }

    const target = e.target
    if (
        (showWorkspaceDetails.value || showTokenDetails.value) &&
        target?.closest &&
        !target.closest('[data-info-popover]') &&
        !target.closest('[data-info-popover-trigger]')
    ) {
        closeInfoPopovers()
    }
}

// Watch for model selector open
watch(showModelSelector, (val) => {
    if (val) loadModels()
})

// Lifecycle hooks
onMounted(() => {
    syncViewportMetrics()
    document.addEventListener('keydown', handleGlobalKeydown)
    document.addEventListener('click', handleGlobalClick)
    window.addEventListener('resize', syncViewportMetrics)
    window.visualViewport?.addEventListener('resize', syncViewportMetrics)
    window.visualViewport?.addEventListener('scroll', syncViewportMetrics)
    loadModels()
    getCurrentWorkspace()
    loadSessions()
})

onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleGlobalKeydown)
    document.removeEventListener('click', handleGlobalClick)
    window.removeEventListener('resize', syncViewportMetrics)
    window.visualViewport?.removeEventListener('resize', syncViewportMetrics)
    window.visualViewport?.removeEventListener('scroll', syncViewportMetrics)
})
</script>
