import { useRef, useEffect, useCallback, useState } from 'react'

interface Agent {
  agent_id: string; name: string; position: [number, number]
  health: number; max_health: number; energy: number
  online: boolean; held: string
}

interface GameMapProps {
  mapData: any
  agents: Agent[]
  selectedAgent: Agent | null
  onSelectAgent: (agent: Agent | null) => void
}

interface HoverInfo {
  x: number; y: number; screenX: number; screenY: number
  tile: any; agents: Agent[]; creatures: any[]
}

const TERRAIN_COLORS: Record<string, string> = {
  flat: '#468a30', sand: '#c2b280', rock: '#6e6558',
  water: '#1e50a0', trench: '#372a1e',
}
const TERRAIN_LABELS: Record<string, string> = {
  flat: '平地 Flat', sand: '沙地 Sand', rock: '基岩 Rock (永久地板)',
  water: '水域 Water', trench: '沟壑 Trench',
}
const ORE_COLORS: Record<string, string> = {
  copper: '#d27d2d', iron: '#b8a090', uranium: '#50c83c', gold: '#ffd728',
}
const ORE_LABELS: Record<string, string> = {
  copper: '铜矿 Copper', iron: '铁矿 Iron', uranium: '铀矿 Uranium', gold: '金矿 Gold',
}
const VEG_COLORS: Record<string, string> = {
  ashbush: '#786428', greytree: '#37412d', wallmoss: '#5a826e', rubble: '#666',
}
const VEG_LABELS: Record<string, string> = {
  ashbush: '余烬灌木 (木质×1)', greytree: '灰木树 (木质×2)',
  wallmoss: '壁生苔 (木质×1)', rubble: '碎石堆 (得石料×1)',
}
const STRUCT_COLORS: Record<string, string> = {
  wall: '#777', door: '#964', workbench: '#08f', furnace: '#f80', power_node: '#0ff',
}
const STRUCT_LABELS: Record<string, string> = {
  wall: '墙壁', door: '门', workbench: '工作台', furnace: '熔炉', power_node: '能源节点',
}
const CREATURE_COLORS: Record<string, string> = {
  ash_crawler: '#d27d2d', rock_spider: '#b8a090', dryad_ape: '#50c83c', swamp_worm: '#7a4aaa',
}
const CREATURE_LABELS: Record<string, string> = {
  ash_crawler: '灰烬爬虫', rock_spider: '岩石蛛', dryad_ape: '树猿', swamp_worm: '沼泽虫',
}

export default function GameMap({ mapData, agents, selectedAgent, onSelectAgent }: GameMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const size = Math.min(canvas.width, canvas.height) * zoom
    const tileSize = size / 200
    const ox = pan.x + (canvas.width - size) / 2
    const oy = pan.y + (canvas.height - size) / 2

    // Draw tiles
    if (mapData?.tiles) {
      for (let y = 0; y < mapData.tiles.length; y++) {
        for (let x = 0; x < mapData.tiles[y].length; x++) {
          const tile = mapData.tiles[y][x]
          const px = ox + x * tileSize * 2
          const py = oy + y * tileSize * 2
          if (px + tileSize * 2 < 0 || px > canvas.width || py + tileSize * 2 < 0 || py > canvas.height) continue

          ctx.fillStyle = TERRAIN_COLORS[tile.l1] || '#333'
          ctx.fillRect(px, py, tileSize * 2, tileSize * 2)

          if (tile.stone) {
            ctx.fillStyle = 'rgba(130,130,125,0.7)'
            ctx.fillRect(px, py, tileSize * 2, tileSize * 2)
          }
          if (tile.ore && tile.stone) {
            ctx.fillStyle = (ORE_COLORS[tile.ore] || '#fff') + '88'
            ctx.fillRect(px, py, tileSize * 2, tileSize * 2)
          }
          if (tile.veg) {
            ctx.fillStyle = (VEG_COLORS[tile.veg] || '#0f0') + '99'
            ctx.fillRect(px, py, tileSize * 2, tileSize * 2)
          }
          if (tile.structure && STRUCT_COLORS[tile.structure]) {
            ctx.fillStyle = STRUCT_COLORS[tile.structure]
            ctx.fillRect(px + 1, py + 1, tileSize * 2 - 2, tileSize * 2 - 2)
          }
        }
      }
    }

    // Draw drop pod shield ranges
    if (mapData?.drop_pods) {
      for (const pod of mapData.drop_pods) {
        const [px, py] = [pod.x, pod.y]
        const cpx = ox + px * tileSize
        const cpy = oy + py * tileSize
        const sr = pod.shield_range * tileSize
        // Shield circle (approximate with square for pixel style)
        ctx.strokeStyle = 'rgba(0, 212, 170, 0.3)'
        ctx.lineWidth = 1
        ctx.strokeRect(cpx - sr, cpy - sr, sr * 2, sr * 2)
        ctx.fillStyle = 'rgba(0, 212, 170, 0.08)'
        ctx.fillRect(cpx - sr, cpy - sr, sr * 2, sr * 2)
        // Drop pod marker
        ctx.fillStyle = '#00d4aa'
        ctx.fillRect(cpx - tileSize/2, cpy - tileSize/2, tileSize, tileSize)
        ctx.fillStyle = '#0a0e17'
        ctx.fillRect(cpx - tileSize/3, cpy - tileSize/3, tileSize*2/3, tileSize*2/3)
      }
    }

    // Draw structures (at full world coords from structures list)
    if (mapData?.structures) {
      for (const s of mapData.structures) {
        const spx = ox + s.x * tileSize
        const spy = oy + s.y * tileSize
        if (spx + tileSize < 0 || spx > canvas.width || spy + tileSize < 0 || spy > canvas.height) continue
        const sc = STRUCT_COLORS[s.type] || '#fff'
        ctx.fillStyle = sc
        ctx.fillRect(spx, spy, tileSize * 2, tileSize * 2)
        ctx.strokeStyle = 'rgba(255,255,255,0.3)'
        ctx.lineWidth = 0.5
        ctx.strokeRect(spx, spy, tileSize * 2, tileSize * 2)
      }
    }

    // Draw creatures as diamonds
    if (mapData?.creatures) {
      for (const creature of mapData.creatures) {
        const cpx = ox + creature.x * tileSize
        const cpy = oy + creature.y * tileSize
        if (cpx + tileSize < 0 || cpx > canvas.width || cpy + tileSize < 0 || cpy > canvas.height) continue

        const color = CREATURE_COLORS[creature.type] || '#f0f'
        const r = Math.max(tileSize * 0.8, 2)
        const cx = cpx + tileSize / 2
        const cy = cpy + tileSize / 2

        ctx.beginPath()
        ctx.moveTo(cx, cy - r)
        ctx.lineTo(cx + r, cy)
        ctx.lineTo(cx, cy + r)
        ctx.lineTo(cx - r, cy)
        ctx.closePath()
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = 'rgba(0,0,0,0.5)'
        ctx.lineWidth = 0.5
        ctx.stroke()

        // HP bar
        if (creature.hp < creature.max_hp) {
          const hpPct = creature.hp / creature.max_hp
          ctx.fillStyle = hpPct > 0.5 ? '#0f0' : hpPct > 0.25 ? '#ff0' : '#f00'
          ctx.fillRect(cpx, cpy - 4, tileSize * hpPct, 2)
        }
      }
    }

    // Draw agents
    for (const agent of agents) {
      if (!agent.online) continue
      const [ax, ay] = agent.position
      const px = ox + ax * tileSize
      const py = oy + ay * tileSize
      if (px + tileSize < 0 || px > canvas.width || py + tileSize < 0 || py > canvas.height) continue

      const isSelected = selectedAgent?.agent_id === agent.agent_id
      ctx.fillStyle = isSelected ? '#00d4aa' : '#0099ff'
      ctx.fillRect(px - 2, py - 2, tileSize + 4, tileSize + 4)
      ctx.fillStyle = '#0a0e17'
      ctx.fillRect(px, py, tileSize, tileSize)

      const hpPct = agent.health / agent.max_health
      ctx.fillStyle = hpPct > 0.5 ? '#0f0' : hpPct > 0.25 ? '#ff0' : '#f00'
      ctx.fillRect(px, py - 4, tileSize * hpPct, 2)

      ctx.fillStyle = '#fff'
      ctx.font = `${Math.max(6, 8 * zoom)}px monospace`
      ctx.fillText(agent.name, px, py - 6)
    }

    if (selectedAgent?.online) {
      const [sx, sy] = selectedAgent.position
      ctx.strokeStyle = '#00d4aa'
      ctx.lineWidth = 2
      ctx.strokeRect(ox + sx * tileSize - 3, oy + sy * tileSize - 3, tileSize + 6, tileSize + 6)
    }
  }, [mapData, agents, selectedAgent, zoom, pan])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const resize = () => {
      canvas.width = canvas.parentElement?.clientWidth || 800
      canvas.height = canvas.parentElement?.clientHeight || 600
      draw()
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [draw])

  const screenToWorld = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const mx = clientX - rect.left
    const my = clientY - rect.top
    const size = Math.min(canvas.width, canvas.height) * zoom
    const tileSize = size / 200
    const ox = pan.x + (canvas.width - size) / 2
    const oy = pan.y + (canvas.height - size) / 2
    const worldX = Math.floor((mx - ox) / tileSize)
    const worldY = Math.floor((my - oy) / tileSize)
    const mapX = Math.floor(worldX / 2)
    const mapY = Math.floor(worldY / 2)
    return { mx, my, mapX, mapY, worldX, worldY, tileSize }
  }, [zoom, pan])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(z => Math.max(0.5, Math.min(4, z * delta)))
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      setDragging(true)
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    }
  }, [pan])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
      return
    }
    const coords = screenToWorld(e.clientX, e.clientY)
    if (!coords || !mapData?.tiles) { setHover(null); return }
    const { mapX, mapY, worldX, worldY } = coords
    if (mapY < 0 || mapY >= mapData.tiles.length || mapX < 0 || mapX >= mapData.tiles[0]?.length) {
      setHover(null); return
    }
    const tile = mapData.tiles[mapY]?.[mapX] || null
    const agentsHere = agents.filter(a => {
      const [ax, ay] = a.position
      return Math.abs(ax - worldX) <= 1 && Math.abs(ay - worldY) <= 1 && a.online
    })
    const creaturesHere = (mapData?.creatures || []).filter((c: any) => {
      return Math.abs(c.x - worldX) <= 1 && Math.abs(c.y - worldY) <= 1
    })
    setHover({ x: worldX, y: worldY, screenX: e.clientX, screenY: e.clientY, tile, agents: agentsHere, creatures: creaturesHere })
  }, [dragging, dragStart, screenToWorld, mapData, agents])

  const handleMouseUp = useCallback(() => { setDragging(false) }, [])
  const handleMouseLeave = useCallback(() => { setHover(null); setDragging(false) }, [])

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (dragging) return
    const canvas = canvasRef.current
    if (!canvas) return
    const coords = screenToWorld(e.clientX, e.clientY)
    if (!coords) return
    const { tileSize, mx, my } = coords
    const size = Math.min(canvas.width, canvas.height) * zoom
    const ox = pan.x + (canvas.width - size) / 2
    const oy = pan.y + (canvas.height - size) / 2
    for (const agent of agents) {
      if (!agent.online) continue
      const [ax, ay] = agent.position
      const apx = ox + ax * tileSize
      const apy = oy + ay * tileSize
      if (mx >= apx - 4 && mx <= apx + tileSize + 4 && my >= apy - 4 && my <= apy + tileSize + 4) {
        onSelectAgent(agent); return
      }
    }
    onSelectAgent(null)
  }, [agents, onSelectAgent, dragging, screenToWorld, pan, zoom])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', imageRendering: 'pixelated', cursor: dragging ? 'grabbing' : 'crosshair' }}
        onClick={handleClick}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
      />
      {/* Zoom controls */}
      <div style={{ position: 'absolute', bottom: 12, right: 12, display: 'flex', gap: 4 }}>
        <button onClick={() => setZoom(z => Math.min(4, z * 1.2))} style={zoomBtnStyle}>+</button>
        <button onClick={() => setZoom(z => Math.max(0.5, z / 1.2))} style={zoomBtnStyle}>−</button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} style={zoomBtnStyle}>⌂</button>
      </div>
      <div style={{ position: 'absolute', top: 8, left: 8, fontSize: 10, color: '#555' }}>
        {zoom.toFixed(1)}x | 拖拽移动 · 滚轮缩放
      </div>

      {/* Hover Tooltip */}
      {hover && hover.tile && !dragging && (
        <div style={{
          position: 'fixed', left: hover.screenX + 16, top: hover.screenY - 10,
          background: '#11151f', border: '1px solid #2a3040', borderRadius: 6,
          padding: '10px 14px', fontSize: 11, lineHeight: '18px', zIndex: 1000,
          pointerEvents: 'none', maxWidth: 280, boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
        }}>
          <div style={{ color: '#00d4aa', fontSize: 12, fontWeight: 'bold', marginBottom: 6, borderBottom: '1px solid #2a3040', paddingBottom: 4 }}>
            📍 ({hover.x}, {hover.y})
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: TERRAIN_COLORS[hover.tile.l1] || '#333', display: 'inline-block' }} />
            <span style={{ color: '#ccc' }}>{TERRAIN_LABELS[hover.tile.l1] || hover.tile.l1}</span>
          </div>
          {hover.tile.stone && (
            <div style={{ marginLeft: 16, color: '#aaa' }}>🪨 L2 石料矿层 (可开采)</div>
          )}
          {hover.tile.ore && hover.tile.stone && (
            <div style={{ marginLeft: 16, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 1, background: ORE_COLORS[hover.tile.ore] || '#fff', display: 'inline-block' }} />
              <span style={{ color: ORE_COLORS[hover.tile.ore] || '#ffd700' }}>💎 {ORE_LABELS[hover.tile.ore]} <span style={{ color: '#888' }}>(裸露)</span></span>
            </div>
          )}
          {!hover.tile.ore && hover.tile.stone && <div style={{ marginLeft: 16, color: '#666' }}>· 无可见矿脉 (scan可探明)</div>}
          {hover.tile.veg && (
            <div style={{ marginLeft: 16, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 1, background: VEG_COLORS[hover.tile.veg] || '#0f0', display: 'inline-block' }} />
              <span style={{ color: '#8f8' }}>🌿 {VEG_LABELS[hover.tile.veg]}</span>
            </div>
          )}
          {hover.tile.structure && (
            <div style={{ marginLeft: 16, color: '#0ff' }}>🏗 {STRUCT_LABELS[hover.tile.structure]}</div>
          )}
          {hover.agents.length > 0 && (
            <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid #2a3040' }}>
              {hover.agents.map(a => <div key={a.agent_id} style={{ color: '#0099ff', fontSize: 10 }}>👤 {a.name} HP:{a.health}</div>)}
            </div>
          )}
          {hover.creatures.length > 0 && (
            <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid #2a3040' }}>
              {hover.creatures.map((c: any) => (
                <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                  <span style={{ width: 8, height: 8, background: CREATURE_COLORS[c.type] || '#f0f', display: 'inline-block', transform: 'rotate(45deg)', transformOrigin: 'center' }} />
                  <span style={{ color: CREATURE_COLORS[c.type] || '#f0f' }}>{CREATURE_LABELS[c.type] || c.type}</span>
                  <span style={{ color: '#888' }}>HP:{c.hp}/{c.max_hp}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const zoomBtnStyle: React.CSSProperties = {
  width: 28, height: 28, background: '#11151f', color: '#ccc',
  border: '1px solid #2a3040', borderRadius: 4, cursor: 'pointer',
  fontFamily: 'monospace', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
}
