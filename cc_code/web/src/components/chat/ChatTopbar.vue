<template>
    <header class="topbar">
        <div class="topbar-left">
            <button @click="$emit('open-mobile-sidebar')" class="icon-button md:hidden" aria-label="Open chat list">
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
            <button
                @click="$emit('toggle-desktop-sidebar')"
                class="icon-button topbar-sidebar-toggle hidden md:inline-flex"
                :aria-label="isDesktopSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
            >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5v14"></path>
                    <path
                        v-if="isDesktopSidebarCollapsed"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M12 8l3 4-3 4"
                    ></path>
                    <path
                        v-else
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M16 8l-3 4 3 4"
                    ></path>
                </svg>
            </button>

            <div class="relative model-selector" data-model-selector>
                <button @click="$emit('toggle-model-selector')" class="model-pill">
                    <span class="model-pill__value">{{ currentModelName || 'Choose a model' }}</span>
                    <svg class="model-pill__chevron h-4 w-4 text-slate-500 transition-transform" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </button>

                <div v-if="showModelSelector" class="floating-menu model-menu absolute left-0 top-full z-50 mt-1.5">
                    <div class="floating-menu__body">
                        <div v-if="modelsLoading" class="dropdown-empty">Loading...</div>
                        <div v-else-if="models.length === 0" class="dropdown-empty">No models available</div>
                        <div v-else class="space-y-1">
                            <button
                                v-for="model in models"
                                :key="model.model_id"
                                @click.stop="$emit('switch-model', model.model_id)"
                                class="dropdown-item"
                                :class="{ 'dropdown-item--active': model.model_id === currentModelId }"
                            >
                                <div class="min-w-0 flex-1 text-left">
                                    <div class="dropdown-item__title">{{ model.model_name }}</div>
                                    <div class="dropdown-item__meta">{{ model.model_id }}</div>
                                </div>
                                <span v-if="model.model_id === currentModelId" class="dropdown-badge">Active</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </header>
</template>

<script setup>
defineProps({
    isDesktopSidebarCollapsed: {
        type: Boolean,
        required: true,
    },
    showModelSelector: {
        type: Boolean,
        required: true,
    },
    modelsLoading: {
        type: Boolean,
        required: true,
    },
    models: {
        type: Array,
        required: true,
    },
    currentModelId: {
        type: String,
        default: '',
    },
    currentModelName: {
        type: String,
        default: '',
    },
})

defineEmits([
    'open-mobile-sidebar',
    'toggle-desktop-sidebar',
    'toggle-model-selector',
    'switch-model',
])
</script>

<style scoped>
.topbar-left {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex-wrap: wrap;
}

.model-selector {
    width: fit-content;
}

.model-pill__value {
    max-width: 15.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-strong);
    font-weight: 700;
    letter-spacing: -0.015em;
}

.model-pill__chevron {
    margin-left: auto;
    flex-shrink: 0;
}

.topbar-sidebar-toggle {
    min-width: 36px;
    min-height: 36px;
    border-color: var(--border-interactive);
    background: #fffdf9;
    color: #5f6b7c;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.24);
}

.topbar-sidebar-toggle:hover {
    background: #f8f3ec;
    color: var(--text-strong);
}

.model-menu {
    width: max(100%, 440px);
    min-width: 440px;
}

@media (max-width: 767px) {
    .topbar-left {
        align-items: stretch;
    }

    .model-pill {
        justify-content: center;
    }
}
</style>
