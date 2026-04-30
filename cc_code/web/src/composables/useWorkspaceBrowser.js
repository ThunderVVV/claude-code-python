import { ref } from 'vue'

export function useWorkspaceBrowser({ isStreaming, showModelSelector, closeInfoPopovers }) {
    const currentWorkspace = ref('')
    const serverWorkspace = ref('')
    const showNewSessionModal = ref(false)
    const workspaceBrowserLoading = ref(false)
    const workspaceBrowserError = ref('')
    const workspaceBrowserPath = ref('')
    const workspaceBrowserInput = ref('')
    const workspaceBrowserParentPath = ref(null)
    const workspaceBrowserDirectories = ref([])
    const workspaceBrowserRoots = ref([])

    const getCurrentWorkspace = async () => {
        try {
            const response = await fetch('/api/workspace')
            const data = await response.json()
            if (data.workspace) {
                serverWorkspace.value = data.workspace
                currentWorkspace.value = data.workspace
            }
        } catch (error) {
            console.error('Failed to get current workspace:', error)
        }
    }

    const browseWorkspace = async (path = '') => {
        workspaceBrowserLoading.value = true
        workspaceBrowserError.value = ''

        try {
            const targetPath = typeof path === 'string' ? path.trim() : ''
            const url = targetPath
                ? `/api/workspace/browse?path=${encodeURIComponent(targetPath)}`
                : '/api/workspace/browse'
            const response = await fetch(url)
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to browse workspace')
            }

            workspaceBrowserPath.value = data.path || ''
            workspaceBrowserInput.value = data.path || ''
            workspaceBrowserParentPath.value = data.parent_path || null
            workspaceBrowserDirectories.value = data.directories || []
            workspaceBrowserRoots.value = data.roots || []
        } catch (error) {
            workspaceBrowserError.value = error.message || 'Failed to browse workspace'
        } finally {
            workspaceBrowserLoading.value = false
        }
    }

    const openNewSessionModal = async () => {
        if (isStreaming.value) return
        closeInfoPopovers()
        showModelSelector.value = false
        showNewSessionModal.value = true
        await browseWorkspace(currentWorkspace.value || serverWorkspace.value || '')
    }

    const closeNewSessionModal = () => {
        showNewSessionModal.value = false
        workspaceBrowserError.value = ''
    }

    const browseWorkspaceParent = async () => {
        if (!workspaceBrowserParentPath.value) return
        await browseWorkspace(workspaceBrowserParentPath.value)
    }

    const submitWorkspaceBrowserPath = async () => {
        await browseWorkspace(workspaceBrowserInput.value)
    }

    return {
        currentWorkspace,
        serverWorkspace,
        showNewSessionModal,
        workspaceBrowserLoading,
        workspaceBrowserError,
        workspaceBrowserPath,
        workspaceBrowserInput,
        workspaceBrowserParentPath,
        workspaceBrowserDirectories,
        workspaceBrowserRoots,
        getCurrentWorkspace,
        browseWorkspace,
        openNewSessionModal,
        closeNewSessionModal,
        browseWorkspaceParent,
        submitWorkspaceBrowserPath,
    }
}
