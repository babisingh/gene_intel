/**
 * SearchBar — Main query input with Discovery Chips.
 */

import { useState, useCallback } from 'react'
import { useSearchStore } from '../../store/searchStore'
import { useSearch } from '../../hooks/useSearch'
import { DiscoveryChips } from './DiscoveryChips'

export function SearchBar() {
  const { query, setQuery, isLoading } = useSearchStore()
  const { executeSearch } = useSearch()
  const [inputValue, setInputValue] = useState(query)

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
    <div className="space-y-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask about genes... e.g. 'Find drug-like peptides near cutting enzymes in human'"
          className="
            flex-1 bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5
            text-sm text-white placeholder-gray-500
            focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500
            disabled:opacity-50
          "
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !inputValue.trim()}
          className="
            px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600
            text-white text-sm font-medium rounded-lg transition-colors
            disabled:cursor-not-allowed
          "
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
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
