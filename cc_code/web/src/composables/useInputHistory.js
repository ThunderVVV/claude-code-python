import { ref, nextTick } from 'vue'

const readInputHistory = () => {
    try {
        return JSON.parse(localStorage.getItem('inputHistory') || '[]')
    } catch {
        return []
    }
}

export function useInputHistory({ inputText, messageInput, autoResize }) {
    const inputHistory = ref(readInputHistory())
    const navItems = ref([])
    const historyIndex = ref(0)

    const resetHistoryNavigation = () => {
        navItems.value = [...inputHistory.value, '']
        historyIndex.value = navItems.value.length - 1
    }

    const navigateHistory = (direction) => {
        if (navItems.value.length === 0) return

        navItems.value[historyIndex.value] = inputText.value

        historyIndex.value += direction
        historyIndex.value = Math.max(0, Math.min(historyIndex.value, navItems.value.length - 1))

        inputText.value = navItems.value[historyIndex.value] || ''
        nextTick(() => autoResize({ target: messageInput.value }))
    }

    const addToHistory = (text) => {
        if (text.trim() && (inputHistory.value.length === 0 || inputHistory.value[inputHistory.value.length - 1] !== text)) {
            inputHistory.value.push(text)
            if (inputHistory.value.length > 1000) inputHistory.value.shift()
            localStorage.setItem('inputHistory', JSON.stringify(inputHistory.value))
        }
        resetHistoryNavigation()
    }

    resetHistoryNavigation()

    return {
        addToHistory,
        navigateHistory,
    }
}
