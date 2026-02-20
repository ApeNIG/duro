import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitBranch, Loader2, ZoomIn, ZoomOut, RotateCcw, Search, ExternalLink } from 'lucide-react'
import ArtifactModal from '@/components/ArtifactModal'

interface Node {
  id: string
  type: string
  title: string
  created_at: string
  x?: number
  y?: number
}

interface Edge {
  source: string
  target: string
  type: string
}

interface GraphData {
  nodes: Node[]
  edges: Edge[]
}

const typeColors: Record<string, string> = {
  fact: '#00FF88',
  decision: '#FF8800',
  episode: '#8888FF',
  log: '#666666',
  evaluation: '#FF44FF',
  skill_stats: '#44FFFF',
  incident: '#FF4444',
  recent_change: '#FFFF44',
  decision_validation: '#AA88FF',
}

const defaultColor = '#888888'

export default function Relationships() {
  const [zoom, setZoom] = useState(1)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(Object.keys(typeColors)))
  const [viewingArtifactId, setViewingArtifactId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<GraphData>({
    queryKey: ['relationships'],
    queryFn: async () => {
      const res = await fetch('/api/relationships?limit=100')
      if (!res.ok) throw new Error('Failed to fetch relationships')
      return res.json()
    },
  })

  // Filter nodes based on search and type filters
  const filteredNodes = useMemo(() => {
    if (!data?.nodes.length) return []

    return data.nodes.filter((node) => {
      // Type filter
      if (!activeTypes.has(node.type)) return false

      // Search filter
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

  // Layout nodes in a force-directed style (simple version)
  const layoutNodes = useMemo(() => {
    if (!filteredNodes.length) return []

    const width = 800
    const height = 600
    const centerX = width / 2
    const centerY = height / 2

    // Group by type
    const byType: Record<string, Node[]> = {}
    filteredNodes.forEach((node) => {
      if (!byType[node.type]) byType[node.type] = []
      byType[node.type].push(node)
    })

    const types = Object.keys(byType)
    const angleStep = (2 * Math.PI) / Math.max(types.length, 1)

    const positioned: Node[] = []
    types.forEach((type, typeIndex) => {
      const typeAngle = typeIndex * angleStep
      const nodes = byType[type]
      const radius = 150 + nodes.length * 5

      nodes.forEach((node, nodeIndex) => {
        const nodeAngle = typeAngle + (nodeIndex - nodes.length / 2) * 0.2
        positioned.push({
          ...node,
          x: centerX + Math.cos(nodeAngle) * radius,
          y: centerY + Math.sin(nodeAngle) * radius,
        })
      })
    })

    return positioned
  }, [filteredNodes])

  const toggleType = (type: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
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

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.2, 3))
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.2, 0.3))
  const handleReset = () => {
    setZoom(1)
    setSelectedNode(null)
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

  const edges = data?.edges || []
  const nodeMap = new Map(layoutNodes.map((n) => [n.id, n]))

  // Get connected edges for selected node
  const connectedEdges = selectedNode
    ? edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
    : []

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="w-5 h-5 text-accent" />
          <h2 className="font-display font-semibold text-lg">Relationships</h2>
          <span className="text-text-secondary text-sm">
            {layoutNodes.length} nodes · {edges.length} connections
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

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleZoomOut}
              className="p-2 hover:bg-white/5 rounded transition-colors"
            >
              <ZoomOut className="w-4 h-4 text-text-secondary" />
            </button>
            <span className="text-xs text-text-secondary w-12 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-2 hover:bg-white/5 rounded transition-colors"
            >
              <ZoomIn className="w-4 h-4 text-text-secondary" />
            </button>
            <button
              onClick={handleReset}
              className="p-2 hover:bg-white/5 rounded transition-colors"
            >
              <RotateCcw className="w-4 h-4 text-text-secondary" />
            </button>
          </div>
        </div>
      </div>

      {/* Legend - clickable type filters */}
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
                isActive
                  ? 'border-white/20 bg-white/5'
                  : 'border-transparent opacity-40 hover:opacity-70'
              }`}
            >
              <span
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-text-secondary">{type}</span>
            </button>
          )
        })}
      </div>

      {/* Graph */}
      <div className="flex-1 bg-card rounded-lg border border-border overflow-hidden relative">
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 800 600"
          style={{ transform: `scale(${zoom})`, transformOrigin: 'center' }}
        >
          {/* Edges */}
          <g>
            {edges.map((edge, i) => {
              const source = nodeMap.get(edge.source)
              const target = nodeMap.get(edge.target)
              if (!source?.x || !target?.x) return null

              const isHighlighted =
                selectedNode &&
                (edge.source === selectedNode.id || edge.target === selectedNode.id)

              return (
                <line
                  key={`${edge.source}-${edge.target}-${i}`}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={isHighlighted ? '#00FF88' : '#333333'}
                  strokeWidth={isHighlighted ? 2 : 1}
                  strokeOpacity={selectedNode ? (isHighlighted ? 1 : 0.2) : 0.5}
                />
              )
            })}
          </g>

          {/* Nodes */}
          <g>
            {layoutNodes.map((node) => {
              if (!node.x || !node.y) return null

              const isSelected = selectedNode?.id === node.id
              const isHovered = hoveredNode === node.id
              const isConnected =
                selectedNode &&
                connectedEdges.some(
                  (e) => e.source === node.id || e.target === node.id
                )
              const dimmed = selectedNode && !isSelected && !isConnected

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {/* Glow for selected */}
                  {isSelected && (
                    <circle
                      r={16}
                      fill="none"
                      stroke={typeColors[node.type] || defaultColor}
                      strokeWidth={2}
                      opacity={0.5}
                    />
                  )}

                  {/* Node circle */}
                  <circle
                    r={isSelected ? 10 : isHovered ? 9 : 8}
                    fill={typeColors[node.type] || defaultColor}
                    opacity={dimmed ? 0.3 : 1}
                  />

                  {/* Label on hover/select */}
                  {(isHovered || isSelected) && (
                    <text
                      y={-14}
                      textAnchor="middle"
                      fontSize={10}
                      fill="#ffffff"
                      fontFamily="JetBrains Mono"
                    >
                      {node.title.slice(0, 30)}
                    </text>
                  )}
                </g>
              )
            })}
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
                    style={{
                      backgroundColor:
                        typeColors[selectedNode.type] || defaultColor,
                    }}
                  />
                  <span className="text-sm font-medium">{selectedNode.title}</span>
                </div>
                <div className="text-xs text-text-secondary mt-1">
                  {selectedNode.type} · {selectedNode.id}
                </div>
                <div className="text-xs text-text-secondary">
                  {new Date(selectedNode.created_at).toLocaleString()}
                </div>
              </div>
              <div className="text-right flex flex-col items-end gap-2">
                <div>
                  <div className="text-sm text-accent">
                    {connectedEdges.length} connections
                  </div>
                  <div className="text-xs text-text-secondary">
                    {connectedEdges.filter((e) => e.source === selectedNode.id).length} outgoing ·{' '}
                    {connectedEdges.filter((e) => e.target === selectedNode.id).length} incoming
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
      </div>

      {/* Artifact Detail Modal */}
      {viewingArtifactId && (
        <ArtifactModal
          artifactId={viewingArtifactId}
          onClose={() => setViewingArtifactId(null)}
        />
      )}
    </div>
  )
}
