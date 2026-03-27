/**
 * ExplainerCard — Renders Agent C's persona-aware narrative explanation.
 */

import type { Persona } from '../../types'
import { MarkdownText } from '../MarkdownText'

interface ExplainerCardProps {
  explanation: string
  persona: Persona
  cypherUsed?: string | null
}

const PERSONA_LABELS: Record<Persona, string> = {
  researcher: 'Technical Report',
}

export function ExplainerCard({ explanation, persona, cypherUsed }: ExplainerCardProps) {
  if (!explanation) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 uppercase tracking-wider">
          {PERSONA_LABELS[persona]}
        </span>
        <span className="flex-1 border-t border-gray-700" />
      </div>

      <div className="text-sm leading-relaxed">
        <MarkdownText>{explanation}</MarkdownText>
      </div>

      {persona === 'researcher' && cypherUsed && (
        <details className="mt-3">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">
            View Cypher query
          </summary>
          <pre className="mt-2 p-3 bg-gray-900 border border-gray-700 rounded text-xs text-green-300 overflow-x-auto font-mono">
            {cypherUsed}
          </pre>
        </details>
      )}
    </div>
  )
}
