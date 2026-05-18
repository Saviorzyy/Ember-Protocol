import { useRef, useEffect, useCallback, useState } from 'react'

interface Agent {
  agent_id: string; name: string; position: [number, number]
  health: number; max_health: number; energy: number
  online: boolean; held: string
  tutorial_phase: number | null
}

interface GameMapProps {
  mapData: any
  agents: Agent[]
  selectedAgent: Agent | null
  onSelectAgent: (agent: Agent | null) => void
  weather: string
  dayPhase?: string    // 'day' | 'night' | 'dawn' | 'dusk'
  events?: any[]       // event list for visual highlights
}

interface HoverInfo {
  x: number; y: number; screenX: number; screenY: number
  tile: any; agents: Agent[]; creatures: any[]
}

interface StormParticle {
  x: number; y: number
  vx: number; vy: number
  size: number; alpha: number
}

interface RadiationFog {
  x: number; y: number
  vx: number       // horizontal drift speed
  radius: number   // cloud patch size
  alpha: number    // base opacity
  phase: number    // pulse phase offset
}

interface EventAnim {
  id: string
  type: 'attack' | 'broadcast' | 'build'
  worldX: number; worldY: number
  startTime: number; duration: number
}

const TERRAIN_COLORS: Record<string, string> = {
  flat: '#468a30', sand: '#c2b280', rock: '#a09880',
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
  wall: '#4a4a5a', door: '#964', workbench: '#08f', furnace: '#f80', power_node: '#0ff',
}
const STRUCT_BORDER_COLORS: Record<string, string> = {
  wall: '#8888aa', door: '#ca8', workbench: '#0af', furnace: '#fa3', power_node: '#0ee',
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

export default function GameMap({ mapData, agents, selectedAgent, onSelectAgent, weather, dayPhase = 'day', events = [] }: GameMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [followAgentId, setFollowAgentId] = useState<string | null>(null)

  // --- Radiation storm particles ---
  const particlesRef = useRef<StormParticle[]>([])
  const stormFadeRef = useRef(0)          // 0-1 fade in/out lerp
  const prevWeatherRef = useRef(weather)

  // --- Area radiation fog (S-1 persistent) ---
  const fogRef = useRef<RadiationFog[]>([])
  const fogSpawnCounterRef = useRef(0)

  // --- Event animations ---
  const eventAnimsRef = useRef<EventAnim[]>([])
  const processedEventIdsRef = useRef<Set<string>>(new Set())

  // --- Double-click debounce ---
  const lastClickTimeRef = useRef(0)

  // ===================================================================
  //  1. DAY PHASE OVERLAY
  // ===================================================================
  function drawDayPhaseOverlay(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, ox: number, oy: number, tileSize: number) {
    if (dayPhase === 'day') return

    if (dayPhase === 'dusk') {
      // Warm orange gradient from the top
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height)
      grad.addColorStop(0, 'rgba(255, 140, 40, 0.35)')
      grad.addColorStop(0.3, 'rgba(255, 100, 30, 0.15)')
      grad.addColorStop(1, 'rgba(255, 60, 20, 0.0)')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    } else if (dayPhase === 'night') {
      // Use offscreen canvas so destination-out doesn't cut the main scene
      const nightCanvas = document.createElement('canvas')
      nightCanvas.width = canvas.width
      nightCanvas.height = canvas.height
      const nctx = nightCanvas.getContext('2d')!
      nctx.fillStyle = 'rgba(5, 8, 30, 0.65)'
      nctx.fillRect(0, 0, canvas.width, canvas.height)
      // Cut vision circles — only affects the offscreen overlay
      nctx.globalCompositeOperation = 'destination-out'
      for (const agent of agents) {
        if (!agent.online) continue
        const [ax, ay] = agent.position
        const cx = ox + ax * tileSize + tileSize / 2
        const cy = oy + ay * tileSize + tileSize / 2
        const radius = 5 * tileSize
        const grad = nctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
        grad.addColorStop(0, 'rgba(255,255,255,1)')
        grad.addColorStop(0.4, 'rgba(255,255,255,0.95)')
        grad.addColorStop(0.7, 'rgba(255,255,255,0.5)')
        grad.addColorStop(1, 'rgba(255,255,255,0)')
        nctx.fillStyle = grad
        nctx.beginPath()
        nctx.arc(cx, cy, radius, 0, Math.PI * 2)
        nctx.fill()
      }
      nctx.globalCompositeOperation = 'source-over'
      ctx.drawImage(nightCanvas, 0, 0)
    } else if (dayPhase === 'dawn') {
      // Cool light-blue gradient fading toward normal
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height)
      grad.addColorStop(0, 'rgba(120, 170, 255, 0.2)')
      grad.addColorStop(0.4, 'rgba(100, 150, 255, 0.08)')
      grad.addColorStop(1, 'rgba(80, 130, 255, 0.0)')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    }
  }

  // ===================================================================
  //  2. RADIATION STORM PARTICLES
  // ===================================================================
  function updateStormParticles(canvasW: number, canvasH: number) {
    // Smoothly interpolate fade toward target
    const target = weather === 'radiation_storm' ? 1 : 0
    stormFadeRef.current += (target - stormFadeRef.current) * 0.03
    if (Math.abs(stormFadeRef.current - target) < 0.001) stormFadeRef.current = target
    prevWeatherRef.current = weather

    if (stormFadeRef.current < 0.01) {
      particlesRef.current = []
      return
    }

    const particles = particlesRef.current

    // Spawn new particles at the top
    const spawnRate = Math.floor(2 + 2 * stormFadeRef.current)
    for (let i = 0; i < spawnRate; i++) {
      if (particles.length >= 120) break
      particles.push({
        x: Math.random() * canvasW,
        y: -10 - Math.random() * 30,
        vx: (Math.random() - 0.5) * 0.6,
        vy: 1 + Math.random() * 2,
        size: 2 + Math.random() * 3,
        alpha: 0.3 + Math.random() * 0.7,
      })
    }

    // Update existing particles
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i]
      p.x += p.vx
      p.y += p.vy
      if (p.y > canvasH + 10) {
        particles.splice(i, 1)
      }
    }
  }

  function drawStormParticles(ctx: CanvasRenderingContext2D, canvasW: number, canvasH: number) {
    if (stormFadeRef.current < 0.01) return

    ctx.save()
    const particles = particlesRef.current
    const now = Date.now()
    for (const p of particles) {
      // Subtle pulsing alpha on each particle + global fade
      const pulse = 0.6 + 0.4 * Math.sin(now / 600 + p.x * 0.1)
      const a = p.alpha * stormFadeRef.current * pulse
      ctx.fillStyle = `rgba(0, 255, 68, ${a})`
      ctx.fillRect(p.x, p.y, p.size, p.size)
    }
    ctx.restore()
  }

  // ===================================================================
  //  2b. AREA RADIATION FOG (S-1 persistent, zone-based)
  // ===================================================================

  function updateRadiationFog(canvasW: number, canvasH: number) {
    const fog = fogRef.current
    const now = Date.now()

    // Spawn new fog patches — rate proportional to visible Y-coverage
    // Spawn evenly across Y but bias toward edges using rad density
    fogSpawnCounterRef.current += 1
    const spawnInterval = fog.length > 60 ? 8 : 3
    if (fogSpawnCounterRef.current % spawnInterval === 0) {
      for (let attempt = 0; attempt < 5; attempt++) {
        // Pick Y biased by radiation probability: lerp(0, 0.30, w)
        const py = Math.random()
        const w = Math.abs(py - 0.5) * 2  // 0 at center, 1 at edge
        const density = 0.30 * w           // same curve as rad_prob
        if (Math.random() < density) {
          const y = py * canvasH
          fog.push({
            x: Math.random() * (canvasW + 200) - 100,
            y,
            vx: -0.15 - Math.random() * 0.2,
            radius: 40 + Math.random() * 80,
            alpha: 0.06 + Math.random() * 0.08,
            phase: Math.random() * Math.PI * 2,
          })
        }
      }
    }

    // Update existing fog patches — drift left, pulse, remove when off-screen
    for (let i = fog.length - 1; i >= 0; i--) {
      const f = fog[i]
      f.x += f.vx
      if (f.x + f.radius < -200 || f.x - f.radius > canvasW + 200) {
        fog.splice(i, 1)
      }
    }
  }

  function drawRadiationFog(ctx: CanvasRenderingContext2D, canvasW: number, canvasH: number) {
    const fog = fogRef.current
    if (fog.length === 0) return

    ctx.save()
    const now = Date.now()
    for (const f of fog) {
      const pulse = 0.7 + 0.3 * Math.sin(now / 3000 + f.phase)
      const a = f.alpha * pulse
      const grad = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, f.radius)
      grad.addColorStop(0, `rgba(180, 220, 40, ${a})`)
      grad.addColorStop(0.4, `rgba(160, 200, 30, ${a * 0.5})`)
      grad.addColorStop(1, 'rgba(180, 220, 40, 0)')
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
  }

  // ===================================================================
  //  3. EVENT HIGHLIGHTS
  // ===================================================================
  function updateEventAnimations() {
    const now = performance.now()
    eventAnimsRef.current = eventAnimsRef.current.filter(
      a => now - a.startTime < a.duration
    )
  }

  function drawEventAnimations(ctx: CanvasRenderingContext2D, ox: number, oy: number, tileSize: number) {
    const now = performance.now()
    const anims = eventAnimsRef.current
    if (anims.length === 0) return

    for (const anim of anims) {
      const elapsed = now - anim.startTime
      const progress = Math.min(elapsed / anim.duration, 1) // 0 → 1
      const sx = ox + anim.worldX * tileSize + tileSize / 2
      const sy = oy + anim.worldY * tileSize + tileSize / 2

      // Cull off-screen events
      if (sx < -100 || sx > ctx.canvas.width + 100 || sy < -100 || sy > ctx.canvas.height + 100) continue

      if (anim.type === 'attack') {
        // Expanding red flash circle
        const maxRadius = tileSize * 4
        const radius = maxRadius * progress
        const alpha = (1 - progress) * 0.7
        ctx.beginPath()
        ctx.arc(sx, sy, radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 40, 20, ${alpha})`
        ctx.fill()
        ctx.strokeStyle = `rgba(255, 80, 40, ${alpha * 0.8})`
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (anim.type === 'broadcast') {
        // Expanding ring ripple (3 concentric waves)
        const maxRadius = tileSize * 6
        const ringCount = 3
        for (let i = 0; i < ringCount; i++) {
          const ringProgress = (progress * 1.5 + i * 0.33) % 1.0
          const radius = maxRadius * ringProgress
          const alpha = (1 - ringProgress) * 0.5
          ctx.beginPath()
          ctx.arc(sx, sy, radius, 0, Math.PI * 2)
          ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`
          ctx.lineWidth = Math.max(1, 3 * (1 - ringProgress))
          ctx.stroke()
        }
      } else if (anim.type === 'build') {
        // Flashing green square
        const flash = Math.sin(progress * Math.PI * 6) * 0.5 + 0.5 // rapid blink
        const alpha = (1 - progress) * 0.6
        const size = tileSize * (1 + progress * 0.5)
        ctx.fillStyle = `rgba(0, 255, 68, ${alpha * flash})`
        ctx.fillRect(sx - size / 2, sy - size / 2, size, size)
        ctx.strokeStyle = `rgba(0, 255, 68, ${alpha})`
        ctx.lineWidth = 1
        ctx.strokeRect(sx - size / 2, sy - size / 2, size, size)
      }
    }
  }

  // ===================================================================
  //  EVENT PROCESSING (triggered when events prop changes)
  // ===================================================================
  useEffect(() => {
    if (!events || events.length === 0) return
    const now = performance.now()

    for (const event of events) {
      const eventId = event.id || `${event.type}_${event.tick}_${event.x || 0}_${event.y || 0}`
      if (processedEventIdsRef.current.has(eventId)) continue
      processedEventIdsRef.current.add(eventId)

      let animType: 'attack' | 'broadcast' | 'build' | null = null
      const msg = (event.message || '').toLowerCase()
      const t = (event.type || '').toLowerCase()

      if (t === 'attack' || t === 'combat' || msg.includes('attack') || msg.includes('hit') || msg.includes('damage') || msg.includes('strike')) {
        animType = 'attack'
      } else if (t === 'broadcast' || msg.includes('broadcast') || msg.includes('transmit') || msg.includes('signal') || msg.includes('radio')) {
        animType = 'broadcast'
      } else if (t === 'build' || t === 'construct' || msg.includes('build') || msg.includes('construct') || msg.includes('placed') || msg.includes('deploy')) {
        animType = 'build'
      }

      if (!animType) continue

      eventAnimsRef.current.push({
        id: eventId,
        type: animType,
        worldX: event.x ?? event.position?.[0] ?? 0,
        worldY: event.y ?? event.position?.[1] ?? 0,
        startTime: now,
        duration: 2000,
      })
    }

    // Evict old processed IDs to avoid memory leak
    if (processedEventIdsRef.current.size > 500) {
      const ids = Array.from(processedEventIdsRef.current)
      processedEventIdsRef.current = new Set(ids.slice(-250))
    }
  }, [events])

  // ===================================================================
  //  MAIN DRAW FUNCTION
  // ===================================================================
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Compute effective pan — in follow mode, center the followed agent
    let effectivePan = pan
    if (followAgentId) {
      const agent = agents.find(a => a.agent_id === followAgentId && a.online)
      if (agent) {
        const [ax, ay] = agent.position
        const size = Math.min(canvas.width, canvas.height) * zoom
        const ts = size / 200
        effectivePan = {
          x: canvas.width / 2 - (canvas.width - size) / 2 - ax * ts - ts / 2,
          y: canvas.height / 2 - (canvas.height - size) / 2 - ay * ts - ts / 2,
        }
      } else {
        // Agent went offline — clear follow on next render
        // (handled by the effect below)
      }
    }

    const size = Math.min(canvas.width, canvas.height) * zoom
    const tileSize = size / 200
    const ox = effectivePan.x + (canvas.width - size) / 2
    const oy = effectivePan.y + (canvas.height - size) / 2

    // Draw tiles
    if (mapData?.tiles) {
      for (let y = 0; y < mapData.tiles.length; y++) {
        for (let x = 0; x < mapData.tiles[y].length; x++) {
          const tile = mapData.tiles[y][x]
          const px = ox + x * tileSize
          const py = oy + y * tileSize
          if (px + tileSize < 0 || px > canvas.width || py + tileSize < 0 || py > canvas.height) continue

          ctx.fillStyle = TERRAIN_COLORS[tile.l1] || '#333'
          ctx.fillRect(px, py, tileSize, tileSize)

          if (tile.stone) {
            ctx.fillStyle = 'rgba(130,130,125,0.7)'
            ctx.fillRect(px, py, tileSize, tileSize)
          }
          if (tile.ore && tile.stone) {
            ctx.fillStyle = (ORE_COLORS[tile.ore] || '#fff') + '88'
            ctx.fillRect(px, py, tileSize, tileSize)
          }
          if (tile.veg) {
            ctx.fillStyle = (VEG_COLORS[tile.veg] || '#0f0') + '99'
            ctx.fillRect(px, py, tileSize, tileSize)
          }
          if (tile.structure && STRUCT_COLORS[tile.structure]) {
            ctx.fillStyle = STRUCT_COLORS[tile.structure]
            ctx.fillRect(px, py, tileSize, tileSize)
            const bc = STRUCT_BORDER_COLORS[tile.structure]
            if (bc) {
              ctx.strokeStyle = bc
              ctx.lineWidth = Math.max(0.5, tileSize * 0.1)
              ctx.strokeRect(px, py, tileSize, tileSize)
            }
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
        ctx.fillStyle = 'rgba(0, 212, 170, 0.06)'
        ctx.fillRect(cpx - sr, cpy - sr, sr * 2, sr * 2)
        ctx.strokeStyle = 'rgba(0, 212, 170, 0.5)'
        ctx.lineWidth = Math.max(1, tileSize * 0.3)
        ctx.setLineDash([tileSize * 0.8, tileSize * 0.4])
        ctx.strokeRect(cpx - sr, cpy - sr, sr * 2, sr * 2)
        ctx.setLineDash([])
        ctx.fillStyle = 'rgba(0, 212, 170, 0.6)'
        ctx.font = `${Math.max(7, tileSize * 0.8)}px monospace`
        ctx.fillText('⬡ 护盾', cpx - sr + 2, cpy - sr - 2)
        ctx.fillStyle = '#00d4aa'
        ctx.fillRect(cpx - tileSize * 0.4, cpy - tileSize * 0.4, tileSize * 0.8, tileSize * 0.8)
        ctx.fillStyle = '#0a0e17'
        ctx.fillRect(cpx - tileSize * 0.25, cpy - tileSize * 0.25, tileSize * 0.5, tileSize * 0.5)
        ctx.fillStyle = '#00d4aa'
        ctx.fillRect(cpx - tileSize * 0.12, cpy - tileSize * 0.12, tileSize * 0.25, tileSize * 0.25)
      }
    }

    // Draw structures (at full world coords from structures list)
    if (mapData?.structures) {
      for (const s of mapData.structures) {
        const spx = ox + s.x * tileSize
        const spy = oy + s.y * tileSize
        if (spx + tileSize < 0 || spx > canvas.width || spy + tileSize < 0 || spy > canvas.height) continue
        const sc = STRUCT_COLORS[s.type] || '#fff'
        const bc = STRUCT_BORDER_COLORS[s.type] || 'rgba(255,255,255,0.3)'
        ctx.fillStyle = sc
        ctx.fillRect(spx, spy, tileSize, tileSize)
        if (s.type === 'wall') {
          ctx.strokeStyle = bc
          ctx.lineWidth = Math.max(1, tileSize * 0.15)
          ctx.strokeRect(spx, spy, tileSize, tileSize)
          ctx.beginPath()
          ctx.moveTo(spx, spy + tileSize / 2)
          ctx.lineTo(spx + tileSize, spy + tileSize / 2)
          ctx.stroke()
          ctx.beginPath()
          ctx.moveTo(spx + tileSize * 0.25, spy)
          ctx.lineTo(spx + tileSize * 0.25, spy + tileSize / 2)
          ctx.moveTo(spx + tileSize * 0.75, spy + tileSize / 2)
          ctx.lineTo(spx + tileSize * 0.75, spy + tileSize)
          ctx.stroke()
        } else {
          ctx.strokeStyle = bc
          ctx.lineWidth = Math.max(0.5, tileSize * 0.1)
          ctx.strokeRect(spx, spy, tileSize, tileSize)
        }
      }
    }

    // Draw creatures as diamonds
    if (mapData?.creatures) {
      for (const creature of mapData.creatures) {
        const cpx = ox + creature.x * tileSize
        const cpy = oy + creature.y * tileSize
        if (cpx + tileSize < 0 || cpx > canvas.width || cpy + tileSize < 0 || cpy > canvas.height) continue

        const color = CREATURE_COLORS[creature.type] || '#f0f'
        const r = Math.max(tileSize * 0.4, 2)
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
      ctx.fillStyle = isSelected ? '#00d4aa' : '#4a9eff'
      ctx.fillRect(px + 1, py + 1, tileSize - 2, tileSize - 2)
      ctx.strokeStyle = isSelected ? '#00d4aa' : '#2a6eb0'
      ctx.lineWidth = 1
      ctx.strokeRect(px + 0.5, py + 0.5, tileSize - 1, tileSize - 1)

      const hpPct = agent.health / agent.max_health
      ctx.fillStyle = hpPct > 0.5 ? '#0f0' : hpPct > 0.25 ? '#ff0' : '#f00'
      ctx.fillRect(px, py - 3, tileSize * hpPct, 2)

      const enPct = agent.energy / 100
      ctx.fillStyle = '#1a1e2a'
      ctx.fillRect(px, py + tileSize + 1, tileSize, 2)
      ctx.fillStyle = '#00d4aa'
      ctx.fillRect(px, py + tileSize + 1, tileSize * enPct, 2)

      ctx.fillStyle = '#fff'
      ctx.font = `${Math.max(6, 8 * zoom)}px monospace`
      ctx.fillText(agent.name, px, py - 5)

      // Follow indicator
      if (followAgentId === agent.agent_id) {
        ctx.strokeStyle = '#ffd728'
        ctx.lineWidth = 2
        ctx.setLineDash([4, 3])
        ctx.strokeRect(px - 3, py - 3, tileSize + 6, tileSize + 6)
        ctx.setLineDash([])
        // Small eye icon
        ctx.fillStyle = '#ffd728'
        ctx.font = `${Math.max(8, 10 * zoom)}px monospace`
        ctx.fillText('👁', px + tileSize + 2, py + tileSize / 2 + 3)
      }
    }

    if (selectedAgent?.online) {
      const [sx, sy] = selectedAgent.position
      ctx.strokeStyle = '#00d4aa'
      ctx.lineWidth = 2
      ctx.strokeRect(ox + sx * tileSize - 2, oy + sy * tileSize - 2, tileSize + 4, tileSize + 4)
    }

    // --- OVERLAYS (drawn on top of game world) ---

    // 1. Day phase overlay
    drawDayPhaseOverlay(ctx, canvas, ox, oy, tileSize)

    // 1b. Area radiation fog (S-1 persistent — zone-based cloud patches)
    updateRadiationFog(canvas.width, canvas.height)
    drawRadiationFog(ctx, canvas.width, canvas.height)

    // 2. Radiation storm particles
    updateStormParticles(canvas.width, canvas.height)
    drawStormParticles(ctx, canvas.width, canvas.height)

    // 3. Event highlights
    updateEventAnimations()
    drawEventAnimations(ctx, ox, oy, tileSize)

    // 4. Existing storm overlay (red pulsing flash — kept as supplement)
    if (weather === 'radiation_storm') {
      const alpha = 0.08 + 0.04 * Math.sin(Date.now() / 500)
      ctx.fillStyle = `rgba(255, 60, 30, ${alpha})`
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    }
  }, [mapData, agents, selectedAgent, zoom, pan, weather, followAgentId, dayPhase])

  // ===================================================================
  //  CONTINUOUS ANIMATION LOOP
  // ===================================================================
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const resize = () => {
      canvas.width = canvas.parentElement?.clientWidth || 800
      canvas.height = canvas.parentElement?.clientHeight || 600
    }
    resize()
    window.addEventListener('resize', resize)

    let animFrameId: number
    const loop = () => {
      try {
        draw()
      } catch (e) {
        console.error('GameMap draw error:', e)
      }
      animFrameId = requestAnimationFrame(loop)
    }
    animFrameId = requestAnimationFrame(loop)

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animFrameId)
    }
  }, [draw])

  // Clean up follow when the followed agent goes offline
  useEffect(() => {
    if (followAgentId) {
      const agent = agents.find(a => a.agent_id === followAgentId && a.online)
      if (!agent) setFollowAgentId(null)
    }
  }, [followAgentId, agents])

  // ===================================================================
  //  EVENT HANDLERS
  // ===================================================================
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
    const mapX = worldX
    const mapY = worldY
    return { mx, my, mapX, mapY, worldX, worldY, tileSize }
  }, [zoom, pan])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    setFollowAgentId(null) // exit follow on zoom
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(z => Math.max(0.5, Math.min(4, z * delta)))
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      setFollowAgentId(null) // exit follow on drag
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

  // Single-click: agent selection / deselection
  // Uses a debounce to distinguish from double-click
  const handleClick = useCallback((e: React.MouseEvent) => {
    if (dragging) return

    const now = Date.now()
    if (now - lastClickTimeRef.current < 400) {
      // Rapid second click — let onDoubleClick handle it
      lastClickTimeRef.current = 0
      return
    }
    lastClickTimeRef.current = now

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
      if (mx >= apx && mx <= apx + tileSize && my >= apy && my <= apy + tileSize) {
        onSelectAgent(agent); return
      }
    }
    onSelectAgent(null)
  }, [agents, onSelectAgent, dragging, screenToWorld, pan, zoom])

  // Double-click: follow agent
  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    lastClickTimeRef.current = 0

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
      if (mx >= apx && mx <= apx + tileSize && my >= apy && my <= apy + tileSize) {
        setFollowAgentId(agent.agent_id)
        onSelectAgent(agent)
        return
      }
    }
    // Clicked empty space — cancel follow
    setFollowAgentId(null)
    onSelectAgent(null)
  }, [agents, screenToWorld, pan, zoom, onSelectAgent])

  // ===================================================================
  //  RENDER
  // ===================================================================
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', imageRendering: 'pixelated', cursor: dragging ? 'grabbing' : 'crosshair' }}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
      />
      {/* Zoom controls */}
      <div style={{ position: 'absolute', bottom: 12, right: 12, display: 'flex', gap: 4 }}>
        <button onClick={() => { setFollowAgentId(null); setZoom(z => Math.min(4, z * 1.2)) }} style={zoomBtnStyle}>+</button>
        <button onClick={() => { setFollowAgentId(null); setZoom(z => Math.max(0.5, z / 1.2)) }} style={zoomBtnStyle}>−</button>
        <button onClick={() => { setFollowAgentId(null); setZoom(1); setPan({ x: 0, y: 0 }) }} style={zoomBtnStyle}>⌂</button>
      </div>
      <div style={{ position: 'absolute', top: 8, left: 8, fontSize: 10, color: '#555' }}>
        {zoom.toFixed(1)}x | 拖拽移动 · 滚轮缩放
        {followAgentId && <span style={{ color: '#ffd728', marginLeft: 8 }}>· 跟随中 👁</span>}
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
