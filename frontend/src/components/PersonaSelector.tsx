/**
 * PersonaSelector — Three-mode selector for business/student/researcher.
 */

import type { Persona } from '../types'
import { useSearchStore } from '../store/searchStore'

const PERSONAS: { id: Persona; label: string; description: string }[] = [
  {
    id: 'business',
    label: 'Business',
    description: 'Plain English, commercial relevance',
  },
  {
    id: 'student',
    label: 'Student',
    description: 'Educational, concepts explained',
  },
  {
    id: 'researcher',
    label: 'Researcher',
    description: 'Full technical detail + Cypher',
  },
]

export function PersonaSelector() {
  const { persona, setPersona } = useSearchStore()

  return (
    <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          onClick={() => setPersona(p.id)}
          title={p.description}
          className={`
            flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
            ${
              persona === p.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-700'
            }
          `}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
