import { ref } from 'vue'

export function useModels({ sessionId, showModelSelector }) {
    const models = ref([])
    const modelsLoading = ref(false)
    const currentModelId = ref('')
    const currentModelName = ref('')
    const currentModelContext = ref('128000')

    const loadModels = async () => {
        modelsLoading.value = true
        try {
            const response = await fetch('/api/models')
            const data = await response.json()
            models.value = data.models || []
            currentModelId.value = data.current_model || ''

            const currentModel = models.value.find(m => m.model_id === currentModelId.value)
            currentModelName.value = currentModel ? currentModel.model_name : ''
            currentModelContext.value = currentModel ? currentModel.context : 128000
        } catch (error) {
            console.error('Failed to load models:', error)
        } finally {
            modelsLoading.value = false
        }
    }

    const switchModel = async (modelId) => {
        if (modelId === currentModelId.value) {
            showModelSelector.value = false
            return
        }

        try {
            const response = await fetch('/api/model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId.value || undefined,
                    model_id: modelId
                })
            })

            const data = await response.json()

            if (data.success) {
                currentModelId.value = modelId
                currentModelName.value = data.model_name
                currentModelContext.value = data.context || 128000
                showModelSelector.value = false
                loadModels()
            } else {
                throw new Error(data.detail || 'Failed to switch model')
            }
        } catch (error) {
            console.error('Failed to switch model:', error)
        }
    }

    return {
        models,
        modelsLoading,
        currentModelId,
        currentModelName,
        currentModelContext,
        loadModels,
        switchModel,
    }
}
