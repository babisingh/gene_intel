/**
 * MarkdownText — Lightweight markdown renderer for Agent C explanations.
 *
 * Handles the subset of markdown that Agent C produces:
 *   ## / ### headings, **bold**, `code`, bullet lists, numbered lists, paragraphs.
 * No external dependency needed.
 */

interface MarkdownTextProps {
  children: string
}

function parseInline(text: string): React.ReactNode[] {
  // Split on **bold** and `code` spans
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="px-1 py-0.5 bg-gray-800 rounded text-green-300 font-mono text-xs">{part.slice(1, -1)}</code>
    }
    return part
  })
}

export function MarkdownText({ children }: MarkdownTextProps) {
  const lines = children.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let key = 0

  const flushList = () => {
    if (listItems.length === 0) return
    const Tag = listType === 'ol' ? 'ol' : 'ul'
    const listClass = listType === 'ol'
      ? 'list-decimal list-inside space-y-1 my-2 text-gray-300'
      : 'list-disc list-inside space-y-1 my-2 text-gray-300'
    elements.push(
      <Tag key={key++} className={listClass}>
        {listItems.map((item, i) => (
          <li key={i}>{parseInline(item)}</li>
        ))}
      </Tag>
    )
    listItems = []
    listType = null
  }

  for (const line of lines) {
    // H2
    if (/^## /.test(line)) {
      flushList()
      elements.push(
        <h3 key={key++} className="text-white font-semibold text-base mt-4 mb-1 border-b border-gray-700 pb-1">
          {parseInline(line.slice(3))}
        </h3>
      )
      continue
    }
    // H3
    if (/^### /.test(line)) {
      flushList()
      elements.push(
        <h4 key={key++} className="text-gray-200 font-medium text-sm mt-3 mb-1">
          {parseInline(line.slice(4))}
        </h4>
      )
      continue
    }
    // Unordered list
    if (/^[-*] /.test(line)) {
      if (listType !== 'ul') { flushList(); listType = 'ul' }
      listItems.push(line.slice(2))
      continue
    }
    // Ordered list
    if (/^\d+\. /.test(line)) {
      if (listType !== 'ol') { flushList(); listType = 'ol' }
      listItems.push(line.replace(/^\d+\. /, ''))
      continue
    }
    // Blank line
    if (line.trim() === '') {
      flushList()
      continue
    }
    // Normal paragraph line
    flushList()
    elements.push(
      <p key={key++} className="my-1 text-gray-300">
        {parseInline(line)}
      </p>
    )
  }
  flushList()

  return <div className="space-y-0.5">{elements}</div>
}
