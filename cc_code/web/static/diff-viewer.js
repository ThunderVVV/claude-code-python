(() => {
    const HIGHLIGHT_LANGUAGES = {
        cjs: 'javascript',
        htm: 'xml',
        html: 'xml',
        js: 'javascript',
        jsx: 'javascript',
        md: 'markdown',
        mjs: 'javascript',
        py: 'python',
        sh: 'bash',
        ts: 'typescript',
        tsx: 'typescript',
        vue: 'xml',
        yaml: 'yaml',
        yml: 'yaml',
        zsh: 'bash',
    };

    const DEMO_RENDER_CONFIG = {
        colorScheme: 'light',
        diffStyle: 'word',
        drawFileList: false,
        fileContentToggle: true,
        fileListStartVisible: false,
        fileListToggle: false,
        highlight: true,
        highlightLanguages: HIGHLIGHT_LANGUAGES,
        matching: 'words',
        matchingMaxComparisons: 2500,
        matchWordsThreshold: 0.25,
        maxLineLengthHighlight: 10000,
        maxLineSizeInBlockForComparison: 200,
        outputFormat: 'line-by-line',
        stickyFileHeaders: true,
        synchronisedScroll: true,
    };

    const normalizeDiffPath = (filePath) => {
        const path = String(filePath || 'file').replace(/\\/g, '/').replace(/^\/+/, '');
        return path || 'file';
    };

    const getDiffDisplayPath = (filePath) => {
        const normalizedPath = normalizeDiffPath(filePath);
        return normalizedPath.split('/').filter(Boolean).pop() || normalizedPath || 'file';
    };

    const getRenderedDisplayName = (fileName) => {
        const normalizedName = normalizeDiffPath(fileName).replace(/^(a|b)\//, '');
        return normalizedName.split('/').filter(Boolean).pop() || normalizedName || 'file';
    };

    const createDiff = (oldContent, newContent, filePath) => {
        if (!window.Diff?.createTwoFilesPatch) {
            throw new Error('Missing jsdiff createTwoFilesPatch implementation.');
        }

        const displayPath = getDiffDisplayPath(filePath);
        const patch = window.Diff.createTwoFilesPatch(
            `a/${displayPath}`,
            `b/${displayPath}`,
            oldContent,
            newContent,
            undefined,
            undefined,
            { context: Number.MAX_SAFE_INTEGER }
        );
        return `diff --git a/${displayPath} b/${displayPath}\n${patch}`;
    };

    const render = (container, diffData, config = {}) => {
        if (!container || !diffData) return null;
        if (!window.Diff2HtmlUI) {
            throw new Error('Missing Diff2HtmlUI implementation.');
        }

        container.classList.add('cc-diff-viewer');
        const diff2htmlUi = new window.Diff2HtmlUI(container, diffData, {
            ...DEMO_RENDER_CONFIG,
            ...config,
            drawFileList: false,
            fileListToggle: false,
            outputFormat: 'line-by-line',
            highlightLanguages: {
                ...HIGHLIGHT_LANGUAGES,
                ...(config.highlightLanguages || {}),
            },
        });
        diff2htmlUi.draw();
        container.querySelectorAll('.d2h-file-list-wrapper').forEach((element) => {
            element.remove();
        });
        container.querySelectorAll('.d2h-file-name').forEach((element) => {
            element.textContent = getRenderedDisplayName(element.textContent);
        });
        return diff2htmlUi;
    };

    window.CCCodeDiffViewer = {
        createDiff,
        render,
    };
})();
