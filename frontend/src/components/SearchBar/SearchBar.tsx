/**
 * SearchBar — pane-aware query input with Discovery Chips.
 */

import { useState, useCallback } from 'react'
import { usePaneContext } from '../../contexts/PaneContext'
import { useSearch } from '../../hooks/useSearch'
import { DiscoveryChips } from './DiscoveryChips'

export function SearchBar() {
  const { pane, setQuery } = usePaneContext()
  const { executeSearch } = useSearch()
  const [inputValue, setInputValue] = useState(pane.query)

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      const trimmed = inputValue.trim()
      if (!trimmed) return
      setQuery(trimmed)
      executeSearch(trimmed)
    },
    [inputValue, setQuery, executeSearch],
  )

  const handleChipSelect = useCallback(
    (chipQuery: string) => {
      setInputValue(chipQuery)
      setQuery(chipQuery)
      executeSearch(chipQuery)
    },
    [setQuery, executeSearch],
  )

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Natural language query — e.g. 'Find drug-like peptides near proteases in all vertebrates'"
          className="
            flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2
            text-sm text-white placeholder-gray-500
            focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500
            disabled:opacity-50
          "
          disabled={pane.isLoading}
        />
        <button
          type="submit"
          disabled={pane.isLoading || !inputValue.trim()}
          className="
            px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600
            text-white text-sm font-medium rounded-lg transition-colors
            disabled:cursor-not-allowed whitespace-nowrap
          "
        >
          {pane.isLoading ? (
            <span className="flex items-center gap-1.5">
              <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Searching…
            </span>
          ) : (
            'Search'
          )}
        </button>
      </form>

      <DiscoveryChips onSelect={handleChipSelect} />
    </div>
  )
}
