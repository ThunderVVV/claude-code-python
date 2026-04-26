export const formatTokens = (tokens) => {
    const num = Number(tokens)
    if (isNaN(num) || num < 0) {
        return '0'
    }
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M'
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K'
    } else {
        return num.toString()
    }
}

export const WEB_REFERENCE_PATTERN = /(^|[\s])@web(?=$|[\s,;:!?()])/

export const hasWebReference = (text) => WEB_REFERENCE_PATTERN.test(text || '')

export const getNonEmptyLines = (text) => (text || '').split('\n').filter(l => l.trim())

export const prefersCompactDiff = () => window.matchMedia('(max-width: 767px)').matches

export const updateAppViewportHeight = () => {
    const viewportHeight = window.visualViewport?.height || window.innerHeight
    document.documentElement.style.setProperty('--app-height', `${Math.round(viewportHeight)}px`)
}

export const isDiffContent = (content) =>
    content.includes('---') && content.includes('+++') ||
    content.includes('diff --git') ||
    (content.includes('-') && content.includes('+') && content.includes('@@'))
