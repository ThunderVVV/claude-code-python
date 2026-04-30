<template>
    <div v-if="sessionsLoading" class="sidebar-empty">Loading...</div>
    <div v-else-if="sessions.length === 0" class="sidebar-empty sidebar-empty--muted">No chats yet</div>
    <div v-else class="space-y-2">
        <button
            v-for="session in sessions"
            :key="session.session_id"
            @click="$emit('select', session.session_id)"
            class="session-card"
            :class="{ 'session-card--active': session.session_id === activeSessionId }"
        >
            <div class="session-card__icon">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                </svg>
            </div>
            <div class="min-w-0 flex-1 text-left">
                <div class="session-card__title">{{ session.title || 'Untitled Chat' }}</div>
                <div class="session-card__meta">{{ session.message_count || 0 }} messages</div>
            </div>
        </button>
    </div>
</template>

<script setup>
defineProps({
    sessionsLoading: {
        type: Boolean,
        required: true,
    },
    sessions: {
        type: Array,
        required: true,
    },
    activeSessionId: {
        type: String,
        default: '',
    },
})

defineEmits(['select'])
</script>

<style scoped>
.sidebar-empty {
    border: 1px dashed rgba(59, 66, 82, 0.12);
    border-radius: var(--radius-md);
    padding: 14px;
    text-align: center;
    color: var(--text-main);
    background: rgba(255, 255, 255, 0.52);
}

.sidebar-empty--muted {
    color: var(--text-muted);
}

.session-card {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    background: #ffffff;
    padding: 10px 11px;
    color: inherit;
    cursor: pointer;
    transition: border-color 0.16s ease, background-color 0.16s ease;
}

.session-card:hover {
    border-color: var(--border-interactive);
    background: #faf6f0;
}

.session-card--active {
    border-color: var(--border-interactive);
    background: #f7f1e9;
}

.session-card__icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 9px;
    color: var(--accent-strong);
    background: rgba(193, 173, 148, 0.11);
    flex-shrink: 0;
}

.session-card--active .session-card__icon {
    background: rgba(193, 173, 148, 0.16);
}

.session-card__title {
    color: var(--text-strong);
    font-size: 0.88rem;
    font-weight: 620;
    line-height: 1.28;
    letter-spacing: -0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.session-card__meta {
    margin-top: 2px;
    color: #7b8798;
    font-size: 0.72rem;
    line-height: 1.2;
}
</style>
