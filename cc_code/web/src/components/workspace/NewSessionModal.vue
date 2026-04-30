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

<style scoped>
.workspace-toolbar {
    display: flex;
    gap: 10px;
    align-items: center;
}

.workspace-toolbar__actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
}

.workspace-input {
    width: 100%;
    min-height: 38px;
    border: 1px solid rgba(59, 66, 82, 0.12);
    border-radius: var(--radius-sm);
    background: #ffffff;
    color: var(--text-strong);
    padding: 0 10px;
}

.workspace-input:focus {
    outline: none;
    border-color: rgba(155, 128, 96, 0.22);
    box-shadow: 0 0 0 4px rgba(155, 128, 96, 0.08);
}

.workspace-root-list {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 8px;
}

.workspace-root-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 30px;
    padding: 0 10px;
    border-radius: 999px;
    border: 1px solid rgba(59, 66, 82, 0.12);
    background: rgba(255, 255, 255, 0.7);
    color: var(--text-main);
    cursor: pointer;
    transition: transform 0.18s ease, background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.workspace-root-pill:hover {
    background: #f7f3ed;
    border-color: var(--border-strong);
}

.workspace-root-pill--active {
    background: #ddd0bf;
    color: #4a3d31;
    border-color: #ddd0bf;
}

.workspace-current {
    margin-top: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-soft);
    border-radius: var(--radius-xl);
    background: #ffffff;
}

.workspace-current__label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 700;
}

.workspace-current__path {
    margin-top: 4px;
    font-family: var(--font-mono);
    font-size: 0.79rem;
    overflow-wrap: anywhere;
    color: var(--text-muted);
    line-height: 1.55;
}

.workspace-error {
    margin-top: 8px;
    color: #991b1b;
    font-size: 0.9rem;
}

.workspace-browser {
    max-height: min(42vh, 420px);
    overflow-y: auto;
    padding: 10px 12px 12px;
    background: #f8fafc;
}

.workspace-list {
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: #ffffff;
}

.workspace-browser__empty {
    min-height: 10rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-main);
}

.workspace-browser__empty--muted {
    color: var(--text-muted);
}

.workspace-entry {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 0 12px;
    min-height: 42px;
    border-radius: 0;
    border: none;
    border-bottom: 1px solid rgba(59, 66, 82, 0.08);
    background: #ffffff;
    color: inherit;
    cursor: pointer;
}

.workspace-entry:last-child {
    border-bottom: none;
}

.workspace-entry:hover {
    background: #f7f7f8;
}

.workspace-entry__main {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex: 1;
}

.workspace-entry__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 7px;
    background: #d5c4b1;
    color: #6f5a45;
    flex-shrink: 0;
}

.workspace-entry__title {
    color: var(--text-strong);
    font-weight: 700;
    font-size: 0.95rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.workspace-entry__meta {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-faint);
    flex-shrink: 0;
}

.workspace-entry__link {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

@media (max-width: 767px) {
    .workspace-toolbar,
    .workspace-toolbar__actions,
    .modal-toolbar--footer {
        flex-direction: column;
    }

    .workspace-toolbar__actions {
        width: 100%;
    }

    .workspace-browser {
        max-height: none;
        flex: 1;
    }
}
</style>
