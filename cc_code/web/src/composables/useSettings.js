import { computed, ref, watch } from 'vue'

export function useSettings({ loadModels }) {
    const showSettingsModal = ref(false)
    const activeSettingsTab = ref('models')
    const settings = ref({})
    const settingsLoading = ref(false)
    const selectedProvider = ref('')
    const availableModels = ref([])
    const selectedModels = ref([])

    const loadSettings = async () => {
        settingsLoading.value = true
        try {
            const res = await fetch('/api/settings')
            if (res.ok) {
                settings.value = await res.json()
                if (settings.value.providers && Object.keys(settings.value.providers).length > 0) {
                    selectedProvider.value = Object.keys(settings.value.providers)[0]
                }
            }
        } catch (error) {
            console.error('Failed to load settings:', error)
        } finally {
            settingsLoading.value = false
        }
    }

    const fetchProviderModels = async () => {
        if (!selectedProvider.value) return
        try {
            const res = await fetch(`/api/providers/${selectedProvider.value}/models`)
            if (res.ok) {
                const data = await res.json()
                availableModels.value = data.models
                selectedModels.value = []
            }
        } catch (error) {
            console.error('Failed to fetch provider models:', error)
            alert(`Failed to fetch models: ${error.message}`)
        }
    }

    const addSelectedModels = () => {
        if (!selectedProvider.value || selectedModels.value.length === 0) return
        const provider = settings.value.providers[selectedProvider.value]
        if (!provider) return
        if (!provider.models) provider.models = {}
        selectedModels.value.forEach(modelId => {
            const model = availableModels.value.find(m => m.id === modelId)
            if (model) {
                provider.models[modelId] = {
                    model_name: model.name,
                    context: model.context || 32000
                }
            }
        })
        selectedModels.value = []
        availableModels.value = []
    }

    const deleteModel = (modelId) => {
        if (!selectedProvider.value) return
        const provider = settings.value.providers[selectedProvider.value]
        if (provider && provider.models) {
            delete provider.models[modelId]
        }
    }

    const saveSettings = async () => {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings.value)
            })
            if (res.ok) {
                alert('Settings saved')
                showSettingsModal.value = false
                loadModels()
            } else {
                const err = await res.json()
                alert(`Failed to save settings: ${err.detail || 'Unknown error'}`)
            }
        } catch (error) {
            console.error('Failed to save settings:', error)
            alert(`Failed to save settings: ${error.message}`)
        }
    }

    const currentProvider = computed(() => {
        if (!selectedProvider.value || !settings.value.providers) return {}
        return settings.value.providers[selectedProvider.value] || {}
    })

    watch(showSettingsModal, (val) => {
        if (val) {
            loadSettings()
            availableModels.value = []
            selectedModels.value = []
        }
    })

    return {
        showSettingsModal,
        activeSettingsTab,
        settings,
        settingsLoading,
        selectedProvider,
        availableModels,
        selectedModels,
        currentProvider,
        loadSettings,
        fetchProviderModels,
        addSelectedModels,
        deleteModel,
        saveSettings,
    }
}
