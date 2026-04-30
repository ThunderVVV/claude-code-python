<template>
    <div class="modal-overlay modal-overlay--padded">
        <div class="modal-backdrop" @click="$emit('close')"></div>
        <div class="modal-surface modal-surface--wide">
            <div class="modal-toolbar">
                <div class="modal-title-group">
                    <h2>Select Working Directory</h2>
                    <p>Save the directory now, then create the new chat when the first message is sent.</p>
                </div>
                <button @click="$emit('close')" class="modal-close" aria-label="Close new chat dialog">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>

            <div class="modal-section">
                <form class="workspace-toolbar" @submit.prevent="$emit('submit-workspace-browser-path')">
                    <input
                        v-model="workspaceBrowserInputValue"
                        type="text"
                        class="workspace-input"
                        placeholder="Enter a directory path"
                    >
                    <div class="workspace-toolbar__actions">
                        <button
                            type="button"
                            @click="$emit('browse-workspace-parent')"
                            :disabled="workspaceBrowserLoading || !workspaceBrowserParentPath"
                            class="secondary-action"
                        >
                            Up
                        </button>
                        <button
                            type="submit"
                            :disabled="workspaceBrowserLoading"
                            class="primary-action primary-action--compact"
                        >
                            Open
                        </button>
                    </div>
                </form>

                <div class="workspace-root-list">
                    <button
                        v-for="root in workspaceBrowserRoots"
                        :key="root.path"
                        type="button"
                        @click="$emit('browse-workspace', root.path)"
                        class="workspace-root-pill"
                        :class="{ 'workspace-root-pill--active': root.path === workspaceBrowserPath }"
                    >
                        {{ root.name }}
                    </button>
                </div>

                <div class="workspace-current">
                    <div class="workspace-current__label">Current Directory</div>
                    <div class="workspace-current__path">{{ workspaceBrowserPath || 'Not selected' }}</div>
                </div>

                <div v-if="workspaceBrowserError" class="workspace-error">{{ workspaceBrowserError }}</div>
            </div>

            <div class="workspace-browser">
                <div v-if="workspaceBrowserLoading" class="workspace-browser__empty">Loading directories...</div>
                <div v-else-if="workspaceBrowserDirectories.length === 0" class="workspace-browser__empty workspace-browser__empty--muted">
                    No child directories are available here
                </div>
                <div v-else class="workspace-list">
                    <button
                        v-for="directory in workspaceBrowserDirectories"
                        :key="directory.path"
                        type="button"
                        @click="$emit('browse-workspace', directory.path)"
                        class="workspace-entry"
                    >
                        <div class="workspace-entry__main">
                            <div class="workspace-entry__icon">
                                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                                </svg>
                            </div>
                            <div class="workspace-entry__title">{{ directory.name }}</div>
                        </div>
                        <div class="workspace-entry__meta">
                            <span v-if="directory.is_symlink" class="workspace-entry__link">Link</span>
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                            </svg>
                        </div>
                    </button>
                </div>
            </div>

            <div class="modal-toolbar modal-toolbar--footer">
                <div class="text-sm text-slate-500">
                    The new chat will use the selected directory as its workspace.
                </div>
                <div class="flex items-center gap-3">
                    <button @click="$emit('close')" class="secondary-action">
                        Cancel
                    </button>
                    <button
                        @click="$emit('start-new-session', workspaceBrowserPath)"
                        :disabled="workspaceBrowserLoading || !workspaceBrowserPath"
                        class="primary-action primary-action--compact"
                    >
                        Start Chat Here
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
    workspaceBrowserLoading: {
        type: Boolean,
        required: true,
    },
    workspaceBrowserError: {
        type: String,
        default: '',
    },
    workspaceBrowserPath: {
        type: String,
        default: '',
    },
    workspaceBrowserInput: {
        type: String,
        default: '',
    },
    workspaceBrowserParentPath: {
        type: String,
        default: '',
    },
    workspaceBrowserDirectories: {
        type: Array,
        required: true,
    },
    workspaceBrowserRoots: {
        type: Array,
        required: true,
    },
})

const emit = defineEmits([
    'close',
    'update:workspaceBrowserInput',
    'browse-workspace',
    'browse-workspace-parent',
    'submit-workspace-browser-path',
    'start-new-session',
])

const workspaceBrowserInputValue = computed({
    get: () => props.workspaceBrowserInput,
    set: (value) => emit('update:workspaceBrowserInput', value),
})
</script>
