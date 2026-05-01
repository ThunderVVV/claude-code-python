<template>
    <div class="conversation-surface">
        <div :ref="messagesContainerRef" class="messages-area" @scroll="handleMessagesScroll">
            <div class="chat-container conversation-column">
                <div v-if="messages.length === 0" class="welcome-stage">
                    <div class="welcome-card">
                        <div class="welcome-icon">
                            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"></path>
                            </svg>
                        </div>
                        <h2>What do you want to work on?</h2>
                        <p>I can help you write code, debug issues, and explain concepts.</p>
                    </div>
                </div>

                <MessageItem
                    v-for="(message, index) in messages"
                    :key="index"
                    :message="message"
                    @toggle-collapse="$emit('toggle-collapse', $event)"
                />

                <div v-if="isTyping" class="typing-row fade-in">
                    <div class="typing-avatar">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                        </svg>
                    </div>
                    <div class="typing-bubble">
                        <div class="typing-indicator flex gap-1.5">
                            <span class="h-2 w-2 rounded-full"></span>
                            <span class="h-2 w-2 rounded-full"></span>
                            <span class="h-2 w-2 rounded-full"></span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import MessageItem from '../MessageItem.vue'

defineProps({
    messages: {
        type: Array,
        required: true,
    },
    isTyping: {
        type: Boolean,
        required: true,
    },
    messagesContainerRef: {
        type: Function,
        required: true,
    },
    handleMessagesScroll: {
        type: Function,
        required: true,
    },
})

defineEmits(['toggle-collapse'])
</script>

<style scoped>
.conversation-surface {
    display: flex;
    flex: 1;
    min-height: 0;
    flex-direction: column;
    background: #ffffff;
}

.messages-area {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
}

.chat-container {
    width: min(100%, 1000px);
    margin: 0 auto;
}

.conversation-column {
    padding: 12px 18px 0;
}

.welcome-stage {
    padding: 8px 0 10px;
    display: flex;
    justify-content: center;
}

.welcome-card,
.typing-bubble {
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-md);
    background: #ffffff;
}

.welcome-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    column-gap: 12px;
    row-gap: 2px;
    align-items: start;
    max-width: 620px;
    width: 100%;
    margin: 0 auto;
    padding: 14px 16px;
    border-color: var(--border-subtle);
    background: #fbfcfe;
    text-align: left;
}

.welcome-card h2 {
    margin: 0;
    color: var(--text-strong);
    font-family: 'Manrope', var(--font-sans);
    font-size: 1.08rem;
    line-height: 1.25;
    max-width: none;
    letter-spacing: 0;
}

.welcome-card > p {
    grid-column: 2;
    max-width: none;
    margin: 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    line-height: 1.45;
}

.welcome-icon {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    grid-row: span 2;
    margin: 1px 0 0;
    border-radius: var(--radius-sm);
    color: var(--accent-strong);
    background: var(--accent-soft);
}

.typing-row {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    min-width: 0;
    align-items: flex-start;
}

.typing-avatar {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 11px;
    color: white;
    background: #c6b098;
    flex-shrink: 0;
}

.typing-bubble {
    padding: 9px 11px;
}

.typing-indicator span {
    background: rgba(100, 116, 139, 0.5);
    animation: blink 1.4s infinite both;
}

.typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
}

@media (max-width: 1024px) {
    .conversation-column {
        padding-left: 18px;
        padding-right: 18px;
    }
}

@media (max-width: 767px) {
    .conversation-column {
        padding: 14px 14px 12px;
    }

    .welcome-card {
        padding: 14px;
    }

    .welcome-card h2 {
        max-width: none;
        font-size: 1.05rem;
    }

    .typing-row {
        gap: 10px;
    }
}
</style>
