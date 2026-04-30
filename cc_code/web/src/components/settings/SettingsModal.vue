<template>
    <div class="modal-overlay">
        <div class="modal-backdrop" @click="$emit('close')"></div>
        <div class="modal-surface modal-surface--xl modal-surface--settings">
            <div class="modal-toolbar">
                <div class="modal-title-group">
                    <h2>Settings</h2>
                    <p>Manage providers, add models, and adjust context limits for this workspace.</p>
                </div>
                <button @click="$emit('close')" class="modal-close" aria-label="Close settings dialog">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>

            <div class="settings-layout">
                <div class="settings-nav">
                    <button
                        @click="activeTab = 'models'"
                        class="settings-nav__item"
                        :class="{ 'settings-nav__item--active': activeTab === 'models' }"
                    >
                        Models
                    </button>
                </div>

                <div class="settings-content">
                    <div v-if="activeTab === 'models'" class="settings-stack">
                        <div v-if="settingsLoading" class="settings-empty">Loading...</div>
                        <div v-else class="settings-stack">
                            <div class="settings-grid">
                                <div class="settings-field">
                                    <label>Provider</label>
                                    <div class="relative" data-provider-selector>
                                        <button
                                            type="button"
                                            @click="showProviderSelector = !showProviderSelector"
                                            class="settings-select-trigger"
                                        >
                                            <span class="truncate">{{ providerValue || 'Select a provider' }}</span>
                                            <svg class="h-4 w-4 text-slate-500 transition-transform" :class="{ 'rotate-180': showProviderSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                                            </svg>
                                        </button>

                                        <div v-if="showProviderSelector" class="floating-menu settings-select-menu absolute left-0 top-full z-50 mt-1.5">
                                            <div class="floating-menu__body">
                                                <div class="space-y-1">
                                                    <button
                                                        v-for="(provider, id) in settings.providers"
                                                        :key="id"
                                                        type="button"
                                                        @click="selectProvider(id)"
                                                        class="dropdown-item"
                                                        :class="{ 'dropdown-item--active': id === providerValue }"
                                                    >
                                                        <div class="min-w-0 flex-1 text-left">
                                                            <div class="dropdown-item__title">{{ id }}</div>
                                                        </div>
                                                        <span v-if="id === providerValue" class="dropdown-badge">Active</span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="settings-field">
                                    <label class="opacity-0">Action</label>
                                    <button @click="$emit('fetch-provider-models')" class="primary-action primary-action--compact w-full justify-center">
                                        Fetch Models
                                    </button>
                                </div>
                            </div>

                            <div v-if="availableModels.length > 0" class="settings-card">
                                <div class="settings-card__title">Available Models</div>
                                <div class="settings-list">
                                    <label v-for="model in availableModels" :key="model.id" class="settings-checkbox">
                                        <input
                                            :id="`model-${model.id}`"
                                            v-model="selectedModelsValue"
                                            type="checkbox"
                                            :value="model.id"
                                        >
                                        <span>{{ model.name }}</span>
                                    </label>
                                </div>
                                <button @click="$emit('add-selected-models')" class="secondary-action secondary-action--success">
                                    Add Selected Models
                                </button>
                            </div>

                            <div class="settings-card">
                                <div class="settings-card__title">Configured Models</div>
                                <div class="settings-model-list">
                                    <div v-for="(model, modelId) in currentProvider.models" :key="modelId" class="settings-model-row">
                                        <div class="min-w-0">
                                            <div class="settings-model-row__title">{{ model.model_name }}</div>
                                            <div class="settings-model-row__meta">{{ modelId }}</div>
                                        </div>
                                        <div class="settings-model-row__controls">
                                            <label class="settings-inline-field">
                                                <span>Context</span>
                                                <input
                                                    v-model.number="model.context"
                                                    type="number"
                                                    min="1"
                                                    class="settings-inline-input"
                                                >
                                            </label>
                                            <button @click="$emit('delete-model', modelId)" class="settings-delete">
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="settings-actions">
                                <button @click="$emit('save-settings')" class="primary-action primary-action--compact">
                                    Save Settings
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
    activeSettingsTab: {
        type: String,
        required: true,
    },
    settings: {
        type: Object,
        required: true,
    },
    settingsLoading: {
        type: Boolean,
        required: true,
    },
    selectedProvider: {
        type: String,
        required: true,
    },
    availableModels: {
        type: Array,
        required: true,
    },
    selectedModels: {
        type: Array,
        required: true,
    },
    currentProvider: {
        type: Object,
        required: true,
    },
})

const emit = defineEmits([
    'close',
    'update:activeSettingsTab',
    'update:selectedProvider',
    'update:selectedModels',
    'fetch-provider-models',
    'add-selected-models',
    'delete-model',
    'save-settings',
])

const showProviderSelector = ref(false)

const activeTab = computed({
    get: () => props.activeSettingsTab,
    set: (value) => emit('update:activeSettingsTab', value),
})

const providerValue = computed({
    get: () => props.selectedProvider,
    set: (value) => emit('update:selectedProvider', value),
})

const selectedModelsValue = computed({
    get: () => props.selectedModels,
    set: (value) => emit('update:selectedModels', value),
})

const selectProvider = (providerId) => {
    providerValue.value = providerId
    showProviderSelector.value = false
}

const handleGlobalKeydown = (e) => {
    if (e.key !== 'Escape') return

    if (showProviderSelector.value) {
        showProviderSelector.value = false
        return
    }

    emit('close')
}

const handleGlobalClick = (e) => {
    if (!showProviderSelector.value) return

    const providerSelector = document.querySelector('[data-provider-selector]')
    if (providerSelector && !providerSelector.contains(e.target)) {
        showProviderSelector.value = false
    }
}

onMounted(() => {
    document.addEventListener('keydown', handleGlobalKeydown)
    document.addEventListener('click', handleGlobalClick)
})

onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleGlobalKeydown)
    document.removeEventListener('click', handleGlobalClick)
})
</script>

<style scoped>
.settings-layout {
    display: flex;
    min-height: 0;
    flex: 1;
    overflow: hidden;
    padding: 12px 14px 14px;
    gap: 12px;
}

.settings-nav {
    width: 160px;
    padding: 8px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.64);
}

.settings-nav__item {
    width: 100%;
    display: block;
    text-align: left;
    padding: 9px 11px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    cursor: pointer;
    font-weight: 600;
    transition: transform 0.18s ease, background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.settings-nav__item:hover {
    background: #f7f3ed;
    border-color: var(--border-strong);
}

.settings-nav__item--active {
    background: #ffffff;
    color: var(--text-strong);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.24);
}

.settings-content {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    padding: 0;
}

.settings-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.settings-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
}

.settings-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.settings-field label,
.settings-inline-field span {
    color: var(--text-main);
    font-size: 0.82rem;
    font-weight: 600;
}

.settings-select-trigger {
    width: 100%;
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 0 10px;
    border: 1px solid rgba(59, 66, 82, 0.12);
    border-radius: var(--radius-sm);
    background: #ffffff;
    color: var(--text-strong);
    cursor: pointer;
    text-align: left;
}

.settings-select-trigger:hover {
    border-color: var(--border-interactive);
    background: #fffdf9;
}

.settings-select-trigger:focus-visible {
    outline: none;
    border-color: rgba(155, 128, 96, 0.22);
    box-shadow: 0 0 0 4px rgba(155, 128, 96, 0.08);
}

.settings-select-menu {
    width: 100%;
    min-width: 100%;
}

.settings-card {
    padding: 12px;
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-md);
    background: #ffffff;
}

.settings-card__title,
.settings-model-row__title {
    color: var(--text-strong);
    font-weight: 700;
}

.settings-model-row__meta {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.55;
}

.settings-list {
    max-height: 240px;
    overflow-y: auto;
    margin: 10px 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    background: #ffffff;
}

.settings-checkbox {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 10px;
    color: var(--text-main);
}

.settings-model-list {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.settings-model-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid rgba(59, 66, 82, 0.08);
}

.settings-model-row:last-child {
    border-bottom: none;
}

.settings-model-row__controls {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.settings-inline-field {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.settings-inline-input {
    width: 98px;
    min-height: 34px;
    border: 1px solid rgba(59, 66, 82, 0.12);
    border-radius: var(--radius-sm);
    background: #ffffff;
    color: var(--text-strong);
    padding: 0 10px;
}

.settings-inline-input:focus {
    outline: none;
    border-color: rgba(155, 128, 96, 0.22);
    box-shadow: 0 0 0 4px rgba(155, 128, 96, 0.08);
}

.settings-delete {
    color: #b42318;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
}

.settings-actions {
    display: flex;
    justify-content: flex-end;
    padding: 12px 0 0;
    margin-top: 2px;
    border-top: 1px solid rgba(59, 66, 82, 0.08);
}

.settings-actions :deep(.primary-action) {
    min-height: 38px;
}

@media (max-width: 1024px) {
    .settings-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 767px) {
    .settings-layout {
        flex-direction: column;
    }

    .settings-nav {
        width: 100%;
        border-right: none;
        border-bottom: 1px solid rgba(59, 66, 82, 0.08);
    }
}
</style>
