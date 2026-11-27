/**
 * Explanation: shows Agent C's text, which Claude writes in Markdown
 * (headings, bold, lists, rules). react-markdown turns it into React elements
 * and does not render raw HTML, so model output cannot inject markup.
 *
 * Used by App.tsx (the explanation under the search bar) and ExplainerCard.tsx.
 */

import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'

const heading = 'mt-4 mb-2 first:mt-0 font-semibold text-gray-100'

const components: Components = {
  h1: ({ children }) => <h3 className={`${heading} text-base`}>{children}</h3>,
  h2: ({ children }) => <h3 className={`${heading} text-base`}>{children}</h3>,
  h3: ({ children }) => <h4 className={heading}>{children}</h4>,
  h4: ({ children }) => <h4 className={heading}>{children}</h4>,
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold text-gray-100">{children}</strong>,
  hr: () => <hr className="my-4 border-gray-700" />,
  code: ({ children }) => (
    <code className="rounded bg-gray-800 px-1 py-0.5 font-mono text-xs">{children}</code>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-blue-400 underline hover:text-blue-300">
      {children}
    </a>
  ),
}

export function Explanation({ text }: { text: string }) {
  return <ReactMarkdown components={components}>{text}</ReactMarkdown>
}
