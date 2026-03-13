/**
 * DomainBadges — Renders protein domain IDs as coloured pills.
 */

interface DomainBadgesProps {
  domains: string[]
  maxVisible?: number
}

function getDomainColor(domainId: string): string {
  if (domainId.startsWith('Pfam:')) return 'bg-blue-900/60 text-blue-300 border-blue-700'
  if (domainId.startsWith('InterPro:')) return 'bg-purple-900/60 text-purple-300 border-purple-700'
  if (domainId.startsWith('GO:')) return 'bg-green-900/60 text-green-300 border-green-700'
  if (domainId.startsWith('KEGG:')) return 'bg-amber-900/60 text-amber-300 border-amber-700'
  return 'bg-gray-800 text-gray-300 border-gray-600'
}

export function DomainBadges({ domains, maxVisible = 10 }: DomainBadgesProps) {
  if (domains.length === 0) {
    return <span className="text-gray-500 text-xs">No domains annotated</span>
  }

  const visible = domains.slice(0, maxVisible)
  const overflow = domains.length - visible.length

  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map((d) => (
        <span
          key={d}
          className={`text-xs px-2 py-0.5 rounded-full border font-mono ${getDomainColor(d)}`}
        >
          {d}
        </span>
      ))}
      {overflow > 0 && (
        <span className="text-xs text-gray-500 self-center">+{overflow} more</span>
      )}
    </div>
  )
}
