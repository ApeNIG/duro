import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitBranch, Loader2, ZoomIn, ZoomOut, RotateCcw, Search, ExternalLink, Play, Pause } from 'lucide-react'
import ArtifactModal from '@/components/ArtifactModal'

interface Node {
  id: string
  type: string
  title: string
  created_at: string
  x: number
  y: number
  vx: number
  vy: number
}

interface Edge {
  source: string
  target: string
  type: string
}

interface GraphData {
  nodes: Array<{ id: string; type: string; title: string; created_at: string }>
  edges: Edge[]
  stats: { total_nodes: number; total_edges: number; edge_types: Record<string, number> }
}

const typeColors: Record<string, string> = {
  fact: '#00FF88',
  decision: '#FF8800',
  episode: '#8888FF',
  log: '#666666',
  evaluation: '#FF44FF',
  skill_stats: '#44FFFF',
  incident_rca: '#FF4444',
  recent_change: '#FFFF44',
  decision_validation: '#AA88FF',
}

const edgeTypeColors: Record<string, string> = {
  used_decision: '#FF8800',
  used_skill: '#44FFFF',
  created_fact: '#00FF88',
  created_decision: '#FF8800',
  tested_in: '#8888FF',
  validates: '#AA88FF',
  evidence_from: '#8888FF',
  evaluates: '#FF44FF',
  caused_by: '#FF4444',
  superseded_by: '#666666',
}

const defaultColor = '#888888'

// Force simulation parameters
const REPULSION_STRENGTH = 500
const ATTRACTION_STRENGTH = 0.05
const DAMPING = 0.85
const CENTER_STRENGTH = 0.01
const MIN_DISTANCE = 40

function useForceSimulation(
  rawNodes: GraphData['nodes'],
  edges: Edge[],
  width: number,
  height: number,
  isRunning: boolean
) {
  const [nodes, setNodes] = useState<Node[]>([])
  const animationRef = useRef<number>()
  const nodesRef = useRef<Node[]>([])

  // Initialize nodes with random positions
  useEffect(() => {
    const initialized: Node[] = rawNodes.map((n) => ({
      ...n,
      x: width / 2 + (Math.random() - 0.5) * 300,
      y: height / 2 + (Math.random() - 0.5) * 300,
      vx: 0,
      vy: 0,
    }))
    nodesRef.current = initialized
    setNodes(initialized)
  }, [rawNodes, width, height])

  // Run simulation
  useEffect(() => {
    if (!isRunning || nodes.length === 0) {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
      return
    }

    const nodeMap = new Map(nodesRef.current.map(n => [n.id, n]))
    const centerX = width / 2
    const centerY = height / 2

    const simulate = () => {
      const currentNodes = nodesRef.current

      // Apply forces
      for (const node of currentNodes) {
        // Reset forces
        let fx = 0
        let fy = 0

        // Repulsion from other nodes
        for (const other of currentNodes) {
          if (other.id === node.id) continue

          const dx = node.x - other.x
          const dy = node.y - other.y
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), MIN_DISTANCE)
          const force = REPULSION_STRENGTH / (dist * dist)

          fx += (dx / dist) * force
          fy += (dy / dist) * force
        }

        // Attraction along edges
        for (const edge of edges) {
          let other: Node | undefined
          if (edge.source === node.id) {
            other = nodeMap.get(edge.target)
          } else if (edge.target === node.id) {
            other = nodeMap.get(edge.source)
          }

          if (other) {
            const dx = other.x - node.x
            const dy = other.y - node.y
            fx += dx * ATTRACTION_STRENGTH
            fy += dy * ATTRACTION_STRENGTH
          }
        }

        // Center gravity
        fx += (centerX - node.x) * CENTER_STRENGTH
        fy += (centerY - node.y) * CENTER_STRENGTH

        // Update velocity with damping
        node.vx = (node.vx + fx) * DAMPING
        node.vy = (node.vy + fy) * DAMPING

        // Update position
        node.x += node.vx
        node.y += node.vy

        // Bounds
        node.x = Math.max(50, Math.min(width - 50, node.x))
        node.y = Math.max(50, Math.min(height - 50, node.y))
      }

      setNodes([...currentNodes])
      animationRef.current = requestAnimationFrame(simulate)
    }

    animationRef.current = requestAnimationFrame(simulate)

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  }, [isRunning, nodes.length, edges, width, height])

  const updateNodePosition = useCallback((id: string, x: number, y: number) => {
    const node = nodesRef.current.find(n => n.id === id)
    if (node) {
      node.x = x
      node.y = y
      node.vx = 0
      node.vy = 0
      setNodes([...nodesRef.current])
    }
  }, [])

  return { nodes, updateNodePosition }
}

export default function Relationships() {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(Object.keys(typeColors)))
  const [viewingArtifactId, setViewingArtifactId] = useState<string | null>(null)
  const [isSimulationRunning, setIsSimulationRunning] = useState(true)
  const [dragNode, setDragNode] = useState<string | null>(null)
  const [isPanning, setIsPanning] = useState(false)
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 })

  const svgRef = useRef<SVGSVGElement>(null)

  const { data, isLoading, error } = useQuery<GraphData>({
    queryKey: ['relationships'],
    queryFn: async () => {
      const res = await fetch('/api/relationships?limit=200')
      if (!res.ok) throw new Error('Failed to fetch relationships')
      return res.json()
    },
  })

  // Filter nodes based on search and type
  const filteredRawNodes = useMemo(() => {
    if (!data?.nodes.length) return []

    return data.nodes.filter((node) => {
      if (!activeTypes.has(node.type)) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          node.title.toLowerCase().includes(query) ||
          node.id.toLowerCase().includes(query) ||
          node.type.toLowerCase().includes(query)
        )
      }
      return true
    })
  }, [data?.nodes, activeTypes, searchQuery])

  const filteredNodeIds = useMemo(() => new Set(filteredRawNodes.map(n => n.id)), [filteredRawNodes])

  // Filter edges to only include visible nodes
  const filteredEdges = useMemo(() => {
    if (!data?.edges) return []
    return data.edges.filter(e => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target))
  }, [data?.edges, filteredNodeIds])

  const { nodes: layoutNodes, updateNodePosition } = useForceSimulation(
    filteredRawNodes,
    filteredEdges,
    800,
    600,
    isSimulationRunning
  )

  const nodeMap = useMemo(() => new Map(layoutNodes.map(n => [n.id, n])), [layoutNodes])

  // Get connected edges for selected node
  const connectedEdges = useMemo(() => {
    if (!selectedNode) return []
    return filteredEdges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
  }, [selectedNode, filteredEdges])

  const toggleType = (type: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const toggleAllTypes = () => {
    if (activeTypes.size === Object.keys(typeColors).length) {
      setActiveTypes(new Set())
    } else {
      setActiveTypes(new Set(Object.keys(typeColors)))
    }
  }

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3))
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.3))
  const handleReset = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setSelectedNode(null)
  }

  // Mouse handlers for pan and drag
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0 && !dragNode) {
      setIsPanning(true)
      setLastMousePos({ x: e.clientX, y: e.clientY })
    }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning && !dragNode) {
      const dx = e.clientX - lastMousePos.x
      const dy = e.clientY - lastMousePos.y
      setPan(p => ({ x: p.x + dx, y: p.y + dy }))
      setLastMousePos({ x: e.clientX, y: e.clientY })
    }

    if (dragNode && svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect()
      const x = (e.clientX - rect.left - pan.x) / zoom
      const y = (e.clientY - rect.top - pan.y) / zoom
      updateNodePosition(dragNode, x, y)
    }
  }

  const handleMouseUp = () => {
    setIsPanning(false)
    setDragNode(null)
  }

  const handleNodeMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation()
    setDragNode(nodeId)
    setIsSimulationRunning(false)
  }

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    setZoom(z => Math.max(0.3, Math.min(3, z + delta)))
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center text-error">
        Failed to load relationships
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="w-5 h-5 text-accent" />
          <h2 className="font-display font-semibold text-lg">Relationships</h2>
          <span className="text-text-secondary text-sm">
            {layoutNodes.length} nodes · {filteredEdges.length} connections
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input
              type="text"
              placeholder="Search nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-card border border-border rounded pl-9 pr-4 py-1.5 text-sm w-48 focus:outline-none focus:border-accent/50"
            />
          </div>

          {/* Simulation control */}
          <button
            onClick={() => setIsSimulationRunning(!isSimulationRunning)}
            className={`p-2 rounded transition-colors ${
              isSimulationRunning ? 'bg-accent/20 text-accent' : 'hover:bg-white/5 text-text-secondary'
            }`}
            title={isSimulationRunning ? 'Pause simulation' : 'Resume simulation'}
          >
            {isSimulationRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <button onClick={handleZoomOut} className="p-2 hover:bg-white/5 rounded transition-colors">
              <ZoomOut className="w-4 h-4 text-text-secondary" />
            </button>
            <span className="text-xs text-text-secondary w-12 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button onClick={handleZoomIn} className="p-2 hover:bg-white/5 rounded transition-colors">
              <ZoomIn className="w-4 h-4 text-text-secondary" />
            </button>
            <button onClick={handleReset} className="p-2 hover:bg-white/5 rounded transition-colors">
              <RotateCcw className="w-4 h-4 text-text-secondary" />
            </button>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <button
          onClick={toggleAllTypes}
          className="px-2 py-1 rounded border border-border hover:border-accent/50 text-text-secondary hover:text-text-primary transition-colors"
        >
          {activeTypes.size === Object.keys(typeColors).length ? 'Hide All' : 'Show All'}
        </button>
        {Object.entries(typeColors).map(([type, color]) => {
          const isActive = activeTypes.has(type)
          return (
            <button
              key={type}
              onClick={() => toggleType(type)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded border transition-colors ${
                isActive ? 'border-white/20 bg-white/5' : 'border-transparent opacity-40 hover:opacity-70'
              }`}
            >
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-text-secondary">{type.replace('_', ' ')}</span>
            </button>
          )
        })}
      </div>

      {/* Graph */}
      <div
        className="flex-1 bg-card rounded-lg border border-border overflow-hidden relative"
        style={{ cursor: isPanning ? 'grabbing' : dragNode ? 'grabbing' : 'grab' }}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox="0 0 800 600"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {/* Edges */}
            <g>
              {filteredEdges.map((edge, i) => {
                const source = nodeMap.get(edge.source)
                const target = nodeMap.get(edge.target)
                if (!source || !target) return null

                const isHighlighted = selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id)
                const isHovered = hoveredEdge === edge
                const edgeColor = edgeTypeColors[edge.type] || '#444444'

                // Calculate midpoint for label
                const midX = (source.x + target.x) / 2
                const midY = (source.y + target.y) / 2

                return (
                  <g key={`${edge.source}-${edge.target}-${i}`}>
                    <line
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={isHighlighted || isHovered ? edgeColor : '#333333'}
                      strokeWidth={isHighlighted || isHovered ? 2 : 1}
                      strokeOpacity={selectedNode ? (isHighlighted ? 1 : 0.15) : 0.5}
                      onMouseEnter={() => setHoveredEdge(edge)}
                      onMouseLeave={() => setHoveredEdge(null)}
                      style={{ cursor: 'pointer' }}
                    />
                    {/* Edge label on hover */}
                    {isHovered && (
                      <g transform={`translate(${midX}, ${midY})`}>
                        <rect
                          x={-40}
                          y={-10}
                          width={80}
                          height={20}
                          fill="#1a1a1a"
                          rx={4}
                          stroke={edgeColor}
                          strokeWidth={1}
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fontSize={9}
                          fill="#ffffff"
                          fontFamily="JetBrains Mono"
                        >
                          {edge.type.replace('_', ' ')}
                        </text>
                      </g>
                    )}
                  </g>
                )
              })}
            </g>

            {/* Nodes */}
            <g>
              {layoutNodes.map((node) => {
                const isSelected = selectedNode?.id === node.id
                const isHovered = hoveredNode === node.id
                const isConnected = selectedNode && connectedEdges.some(e => e.source === node.id || e.target === node.id)
                const dimmed = selectedNode && !isSelected && !isConnected
                const color = typeColors[node.type] || defaultColor

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedNode(isSelected ? null : node)}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  >
                    {/* Glow for selected */}
                    {isSelected && (
                      <circle r={18} fill="none" stroke={color} strokeWidth={2} opacity={0.4} />
                    )}

                    {/* Node circle */}
                    <circle
                      r={isSelected ? 12 : isHovered ? 10 : 8}
                      fill={color}
                      opacity={dimmed ? 0.2 : 1}
                      stroke={isSelected ? '#ffffff' : 'none'}
                      strokeWidth={2}
                    />

                    {/* Label on hover/select */}
                    {(isHovered || isSelected) && (
                      <>
                        <rect
                          x={-60}
                          y={-28}
                          width={120}
                          height={18}
                          fill="#0c0c0c"
                          rx={4}
                          opacity={0.9}
                        />
                        <text
                          y={-16}
                          textAnchor="middle"
                          fontSize={10}
                          fill="#ffffff"
                          fontFamily="JetBrains Mono"
                        >
                          {node.title.slice(0, 20)}{node.title.length > 20 ? '...' : ''}
                        </text>
                      </>
                    )}
                  </g>
                )
              })}
            </g>
          </g>
        </svg>

        {/* Selected node info panel */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 right-4 bg-page/95 backdrop-blur border border-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: typeColors[selectedNode.type] || defaultColor }}
                  />
                  <span className="text-sm font-medium">{selectedNode.title}</span>
                </div>
                <div className="text-xs text-text-secondary mt-1">
                  {selectedNode.type.replace('_', ' ')} · {selectedNode.id}
                </div>
                <div className="text-xs text-text-secondary">
                  {new Date(selectedNode.created_at).toLocaleString()}
                </div>
                {/* Connection types */}
                {connectedEdges.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {Array.from(new Set(connectedEdges.map(e => e.type))).map(t => (
                      <span
                        key={t}
                        className="px-1.5 py-0.5 text-xs rounded"
                        style={{ backgroundColor: edgeTypeColors[t] + '30', color: edgeTypeColors[t] }}
                      >
                        {t.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="text-right flex flex-col items-end gap-2">
                <div>
                  <div className="text-sm text-accent">{connectedEdges.length} connections</div>
                  <div className="text-xs text-text-secondary">
                    {connectedEdges.filter(e => e.source === selectedNode.id).length} out ·{' '}
                    {connectedEdges.filter(e => e.target === selectedNode.id).length} in
                  </div>
                </div>
                <button
                  onClick={() => setViewingArtifactId(selectedNode.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-accent/20 text-accent border border-accent/30 rounded hover:bg-accent/30 transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  View Details
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edge stats overlay */}
        {data?.stats?.edge_types && Object.keys(data.stats.edge_types).length > 0 && (
          <div className="absolute top-4 right-4 bg-page/90 backdrop-blur border border-border rounded-lg p-3">
            <div className="text-xs text-text-secondary mb-2">Connection Types</div>
            <div className="space-y-1">
              {Object.entries(data.stats.edge_types).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between gap-4 text-xs">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: edgeTypeColors[type] || '#666' }}
                    />
                    {type.replace('_', ' ')}
                  </span>
                  <span className="text-text-secondary font-mono">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Artifact Detail Modal */}
      {viewingArtifactId && (
        <ArtifactModal artifactId={viewingArtifactId} onClose={() => setViewingArtifactId(null)} />
      )}
    </div>
  )
}
