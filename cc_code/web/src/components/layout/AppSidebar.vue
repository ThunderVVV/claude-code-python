<template>
    <aside v-show="!isDesktopSidebarCollapsed" class="sidebar-panel hidden md:flex">
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

        <div class="sidebar-section-header">
            <span>Recent Chats</span>
            <span>{{ sessions.length }}</span>
        </div>

        <div class="sidebar-list">
            <SessionList
                :sessions-loading="sessionsLoading"
                :sessions="sessions"
                :active-session-id="sessionId"
                @select="$emit('select-session', $event)"
            />
        </div>

        <div class="sidebar-footer">
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
</template>

<script setup>
import SessionList from '../navigation/SessionList.vue'

defineProps({
    isDesktopSidebarCollapsed: {
        type: Boolean,
        required: true,
    },
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

defineEmits(['open-new-chat', 'select-session', 'open-settings'])
</script>

<style scoped>
.sidebar-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 4px 6px;
    color: var(--text-faint);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 700;
}

.sidebar-footer {
    padding-top: 8px;
}
</style>
