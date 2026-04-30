<template>
    <div class="mobile-overlay md:hidden" @click="$emit('close')">
        <div class="mobile-overlay__backdrop"></div>
        <aside class="mobile-sidebar" @click.stop>
            <div class="mobile-sidebar__header">
                <div>
                    <div class="eyebrow">Sessions</div>
                    <div class="mobile-sidebar__title">Chat List</div>
                </div>
                <button @click="$emit('close')" class="icon-button" aria-label="Close chat list">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>

            <button
                @click="$emit('open-new-chat')"
                :disabled="isStreaming"
                class="primary-action"
            >
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                </svg>
                New Chat
            </button>

            <div class="sidebar-list mt-4">
                <SessionList
                    :sessions-loading="sessionsLoading"
                    :sessions="sessions"
                    :active-session-id="sessionId"
                    @select="$emit('select-session', $event)"
                />
            </div>

            <div class="sidebar-footer mt-auto">
                <button
                    @click="$emit('open-settings')"
                    class="secondary-action secondary-action--ghost"
                >
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h6M14 6h6M4 12h10M18 12h2M4 18h2M10 18h10"></path>
                        <circle cx="12" cy="6" r="2"></circle>
                        <circle cx="16" cy="12" r="2"></circle>
                        <circle cx="8" cy="18" r="2"></circle>
                    </svg>
                    Settings
                </button>
            </div>
        </aside>
    </div>
</template>

<script setup>
import SessionList from '../navigation/SessionList.vue'

defineProps({
    isStreaming: {
        type: Boolean,
        required: true,
    },
    sessionsLoading: {
        type: Boolean,
        required: true,
    },
    sessions: {
        type: Array,
        required: true,
    },
    sessionId: {
        type: String,
        default: '',
    },
})

defineEmits(['close', 'open-new-chat', 'select-session', 'open-settings'])
</script>

<style scoped>
.mobile-sidebar__title {
    color: var(--text-strong);
    font-size: 1rem;
    font-weight: 650;
    line-height: 1.2;
}

.sidebar-footer {
    padding-top: 8px;
}
</style>
