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
