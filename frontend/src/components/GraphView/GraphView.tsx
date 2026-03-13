/**
 * GraphView — Sigma.js v3 WebGL graph renderer.
 *
 * Renders up to 300 gene nodes colour-coded by species.
 * Node size encodes CDS length.
 * Clicking a node opens the Analysis Drawer (graph stays static — Option B).
 *
 * Connected to:
 *   - sigmaConfig.ts: node/edge visual encoding
 *   - searchStore: selectedGene, setSelectedGene
 *   - uiStore: openDrawer
 */

import { useEffect, useRef, useCallback } from 'react'
import Graph from 'graphology'
import Sigma from 'sigma'
import { circular } from 'graphology-layout'
import type { GeneNode, GraphEdge } from '../../types'
import { getNodeColor, getNodeSize, EDGE_STYLES } from './sigmaConfig'
import { useSearchStore } from '../../store/searchStore'
import { useUiStore } from '../../store/uiStore'

interface GraphViewProps {
  nodes: GeneNode[]
  edges: GraphEdge[]
}

const MAX_NODES = 300

export function GraphView({ nodes, edges }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const graphRef = useRef<Graph | null>(null)

  const setSelectedGene = useSearchStore((s) => s.setSelectedGene)
  const openDrawer = useUiStore((s) => s.openDrawer)

  const buildGraph = useCallback(() => {
    const limitedNodes = nodes.slice(0, MAX_NODES)
    const nodeIds = new Set(limitedNodes.map((n) => n.gene_id))

    const graph = new Graph({ type: 'undirected' })

    limitedNodes.forEach((node) => {
      graph.addNode(node.gene_id, {
        label: node.name || node.gene_id,
        size: getNodeSize(node.cds_length),
        color: getNodeColor(node.species_taxon),
        x: Math.random(),
        y: Math.random(),
        // Store full gene data for click handler
        geneData: node,
      })
    })

    edges.forEach((edge, idx) => {
      if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
        const edgeStyle = EDGE_STYLES[edge.type] ?? EDGE_STYLES.CO_LOCATED_WITH
        try {
          graph.addEdge(edge.source, edge.target, {
            color: edgeStyle.color,
            size: edgeStyle.size,
            label: edge.type,
          })
        } catch {
          // Duplicate edge — skip
        }
      }
    })

    // Apply circular layout for initial positioning
    circular.assign(graph, { scale: 1 })

    return graph
  }, [nodes, edges])

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    // Clean up previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill()
      sigmaRef.current = null
    }

    const graph = buildGraph()
    graphRef.current = graph

    const sigma = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      allowInvalidContainer: true,
    })
    sigmaRef.current = sigma

    // Click handler — open Analysis Drawer
    sigma.on('clickNode', ({ node }) => {
      const attrs = graph.getNodeAttributes(node)
      if (attrs.geneData) {
        setSelectedGene(attrs.geneData as GeneNode)
        openDrawer()
      }
    })

    return () => {
      sigma.kill()
      sigmaRef.current = null
    }
  }, [nodes, edges, buildGraph, setSelectedGene, openDrawer])

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Search for genes to visualise the network
      </div>
    )
  }

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      {nodes.length >= MAX_NODES && (
        <div className="absolute top-2 right-2 bg-yellow-900/80 text-yellow-200 text-xs px-2 py-1 rounded">
          Showing first {MAX_NODES} results
        </div>
      )}
    </div>
  )
}
