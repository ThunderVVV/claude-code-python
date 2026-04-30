<template>
    <div class="conversation-surface">
        <div :ref="messagesContainerRef" class="messages-area" @scroll="handleMessagesScroll">
            <div class="chat-container conversation-column">
                <div v-if="messages.length === 0" class="welcome-stage">
                    <div class="welcome-card">
                        <div class="welcome-icon">
                            <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(252, 248, 242, 0.08));
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
    padding: 8px 16px 0;
}

.welcome-stage {
    padding: 0 0 6px;
    display: flex;
    justify-content: center;
}

.welcome-card,
.typing-bubble {
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-xl);
    background: #ffffff;
}

.welcome-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 620px;
    width: 100%;
    margin: 0 auto;
    padding: 18px 20px;
    border-color: rgba(155, 128, 96, 0.12);
    background: #fdfbf7;
    text-align: center;
}

.welcome-card h2 {
    margin: 0;
    color: var(--text-strong);
    font-family: 'Manrope', var(--font-sans);
    font-size: clamp(1.64rem, 2.15vw, 2.2rem);
    line-height: 1.04;
    max-width: 13ch;
    letter-spacing: -0.045em;
}

.welcome-card > p {
    max-width: 28rem;
    margin: 12px auto 0;
    color: #748094;
    font-size: 0.9rem;
    line-height: 1.5;
}

.welcome-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    margin: 0 auto 16px;
    border-radius: 16px;
    color: white;
    background: linear-gradient(135deg, #ddd1c1, #c2ad92);
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
    padding: 12px 14px;
}

.typing-indicator span {
    background: rgba(155, 128, 96, 0.4);
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
        padding: 20px 14px 12px;
    }

    .welcome-card {
        padding: 22px;
    }

    .welcome-card h2 {
        max-width: none;
        font-size: 2rem;
    }

    .typing-row {
        gap: 10px;
    }
}
</style>
