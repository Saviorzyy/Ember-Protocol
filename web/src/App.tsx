import { useState, useEffect, useCallback } from 'react'
import GameMap from './components/GameMap'
import AgentPanel from './components/AgentPanel'
import AgentList from './components/AgentList'
import RegisterForm from './components/RegisterForm'
import EventLog from './components/EventLog'

interface Agent {
  agent_id: string
  name: string
  position: [number, number]
  health: number
  max_health: number
  energy: number
  online: boolean
  held: string
  tutorial_phase: number | null
}

interface ServerStatus {
  tick: number
  day_phase: string
  weather: string
  agents_total: number
  agents_online: number
  structures: number
}

// ── Auth helpers ──────────────────────────────

function getStoredToken(): string | null {
  return sessionStorage.getItem('ember_token')
}

function getStoredAgentId(): string | null {
  return sessionStorage.getItem('ember_agent_id')
}

/** Wrapper around fetch that attaches Authorization header when a token exists. */
async function authFetch(url: string, options?: RequestInit): Promise<Response | null> {
  const token = getStoredToken()
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    // Token is invalid / expired — clear stored credentials
    sessionStorage.removeItem('ember_token')
    sessionStorage.removeItem('ember_agent_id')
    return null
  }
  return res
}

// ── Component ─────────────────────────────────

export default function App() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [status, setStatus] = useState<ServerStatus | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [events, setEvents] = useState<any[]>([])
  const [showRegister, setShowRegister] = useState(false)
  const [mapData, setMapData] = useState<any>(null)
  const [token, setToken] = useState<string>('')
  const [regData, setRegData] = useState<any>(null)
  const [copied, setCopied] = useState(false)
  const [agentType, setAgentType] = useState<string>('mcp')
  const [sseConnected, setSseConnected] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)
  // mcp = Claude/Hermes/Cursor (MCP protocol), skill = OpenClaw/standalone

  // Restore token + regData from sessionStorage on mount
  useEffect(() => {
    const stored = getStoredToken()
    if (stored) {
      setToken(stored)
    }
    const storedReg = sessionStorage.getItem('ember_reg_data')
    if (storedReg) {
      try {
        setRegData(JSON.parse(storedReg))
      } catch (e) {}
    }
  }, [])

  // ── Data fetchers (used on initial load and after registration) ──

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/status')
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (e) {}
  }, [])

  const fetchAgents = useCallback(async () => {
    try {
      const res = await authFetch('/api/v1/agents')
      if (res && res.ok) {
        const data = await res.json()
        setAgents(data.agents || [])
      }
    } catch (e) {}
  }, [])

  const fetchMap = useCallback(async () => {
    try {
      const res = await authFetch('/api/v1/map')
      if (res && res.ok) {
        const data = await res.json()
        setMapData(data)
      }
    } catch (e) {}
  }, [])

  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/events?count=20')
      if (res.ok) {
        const data = await res.json()
        setEvents(data.events || [])
      }
    } catch (e) {}
  }, [])

  // ── SSE connection (replaces polling) ────────

  useEffect(() => {
    // Initial data load
    fetchStatus()
    fetchMap()
    fetchAgents()
    fetchEvents()

    // Open SSE stream
    const es = new EventSource('/api/v1/events/stream')

    es.addEventListener('connected', () => {
      setSseConnected(true)
    })

    es.addEventListener('tick', (e) => {
      try {
        const data = JSON.parse(e.data) as ServerStatus
        setStatus(data)
      } catch (err) {}
    })

    es.addEventListener('agent_update', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.agents) {
          setAgents(data.agents)
        }
      } catch (err) {}
    })

    es.addEventListener('map_update', (e) => {
      try {
        const data = JSON.parse(e.data)
        setMapData((prev: any) => {
          if (!prev) return null
          const next = {
            ...prev,
            ...(data.structures ? { structures: data.structures } : {}),
            ...(data.creatures ? { creatures: data.creatures } : {}),
          }
          // Merge individual tile updates (resource depletion, etc.)
          if (data.tiles && data.tiles.length > 0) {
            const tiles = prev.tiles.map((row: any[]) => [...row])
            for (const t of data.tiles) {
              if (tiles[t.y] && tiles[t.y][t.x]) {
                tiles[t.y][t.x] = t
              }
            }
            next.tiles = tiles
          }
          return next
        })
      } catch (err) {}
    })

    es.addEventListener('event', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.events) {
          setEvents(data.events)
        }
      } catch (err) {}
    })

    es.onerror = () => {
      setSseConnected(false)
      // EventSource auto-reconnects
    }

    return () => {
      es.close()
    }
  }, [fetchStatus, fetchMap, fetchAgents, fetchEvents])

  // Keep selectedAgent in sync when agents array updates via SSE
  useEffect(() => {
    setSelectedAgent(prev => {
      if (!prev) return null
      const updated = agents.find(a => a.agent_id === prev.agent_id)
      return updated || prev
    })
  }, [agents])

  // ── Registration ─────────────────────────────

  const handleRegister = async (name: string, chassis: any) => {
    const res = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_name: name, chassis }),
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.error || `注册失败 (${res.status})`)
    }
    const data = await res.json()
    const gameToken = data.game_token
    const agentId = data.agent_id

    // Store token for API auth
    sessionStorage.setItem('ember_token', gameToken)
    sessionStorage.setItem('ember_agent_id', agentId)
    setToken(gameToken)

    const headTier = chassis.head?.tier || 'mid'
    const torsoTier = chassis.torso?.tier || 'mid'
    const locoTier = chassis.locomotion?.tier || 'low'

    const regInfo = {
      agent_name: name,
      agent_id: agentId,
      game_token: gameToken,
      head: headTier,
      torso: torsoTier,
      loco: locoTier,
      server: 'ws://localhost:8765',
      spawn_location: data.spawn_location,
    }
    sessionStorage.setItem('ember_reg_data', JSON.stringify(regInfo))
    setRegData(regInfo)
    setShowPrompt(true)
    setShowRegister(false)

    // Re-fetch protected data now that we have a token
    fetchMap()
    fetchAgents()
  }

  // ── Render ───────────────────────────────────

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top bar */}
      <div style={{
        background: '#11151f', borderBottom: '1px solid #1e2533',
        padding: '8px 16px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ color: '#00d4aa', fontSize: 16, margin: 0 }}>🔥 余烬协议</h1>
          <span style={{ fontSize: 11, color: '#666' }}>Ember Protocol MVP</span>
          {/* SSE connection indicator */}
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 10,
            background: sseConnected ? '#0a2a1a' : '#2a0a0a',
            color: sseConnected ? '#0c0' : '#f44',
            border: `1px solid ${sseConnected ? '#0a3' : '#a30'}`,
          }}>
            {sseConnected ? '● 实时' : '○ 断开'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12, alignItems: 'center' }}>
          {status && (
            <>
              <span>⏱ Tick {status.tick}</span>
              <span>{status.day_phase === 'day' ? '☀️' : status.day_phase === 'night' ? '🌙' : '🌅'} {status.day_phase}</span>
              <span title="常驻区域辐射: Y轴距离中心越远辐射越强">
                {status.weather === 'radiation_storm' ? '☢️ 辐射风暴' : '☢️ 区域辐射'}
              </span>
              <span>👤 {status.agents_online}/{status.agents_total} 在线</span>
              <span>🏗 {status.structures} 建筑</span>
            </>
          )}
          <button
            onClick={() => setShowRegister(!showRegister)}
            style={{
              background: '#00d4aa', color: '#0a0e17', border: 'none',
              padding: '6px 16px', borderRadius: 4, cursor: 'pointer',
              fontFamily: 'inherit', fontWeight: 'bold',
            }}
          >
            + 创建角色
          </button>
          {regData && (
            <button
              onClick={() => setShowPrompt(true)}
              title="查看连接信息和 Token"
              style={{
                background: '#2a3040', color: '#0cf', border: '1px solid #0cf',
                padding: '6px 12px', borderRadius: 4, cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 11,
              }}
            >
              🔗 连接
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Map */}
        <div style={{ flex: 1, position: 'relative' }}>
          <GameMap
            mapData={mapData}
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            weather={status?.weather || 'calm'}
            dayPhase={status?.day_phase || 'day'}
            events={events}
          />
        </div>

        {/* Right panel */}
        <div style={{
          width: 320, background: '#11151f', borderLeft: '1px solid #1e2533',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <AgentPanel agent={selectedAgent} />
          <AgentList agents={agents} selectedAgent={selectedAgent} onSelectAgent={setSelectedAgent} />
          <EventLog events={events} />
        </div>
      </div>

      {/* Prompt-only mode — Copy prompt to agent, agent connects with real token */}
      {showPrompt && regData && (() => {
        const skillRawUrl = 'https://raw.githubusercontent.com/Saviorzyy/Ember-Protocol-Player/main/ember_skill.py'
        const mcpRawUrl = 'https://raw.githubusercontent.com/Saviorzyy/Ember-Protocol-Player/main/ember_mcp_server.py'
        const name = regData.agent_name
        const agentId = regData.agent_id
        const gameToken = regData.game_token
        const head = regData.head
        const torso = regData.torso
        const loco = regData.loco
        const per = head==='high'?3:head==='mid'?2:1
        const con = torso==='high'?3:torso==='mid'?2:1
        const agi = loco==='high'?3:loco==='mid'?2:1

        // Agent-type-specific prompts
        const prompts: Record<string, string> = {
          mcp: `请通过 MCP Server 帮我接入 Ember Protocol 游戏。\n\n**角色已注册** — 使用以下 Token 直接连接：\nToken: ${gameToken}\nAgent ID: ${agentId}\n\n**配置 MCP（直接编辑配置文件，不要用 CLI 命令添加，有参数解析 bug）：**\n\nHermes — 编辑 ~/.hermes/config.yaml，在 mcp_servers 下添加：\n  ember:\n    command: python3\n    args:\n    - /private/tmp/ember_mcp_server.py\n    - --token\n    - ${gameToken}\n    - --server\n    - ws://localhost:8765\n\nClaude Code:\nclaude mcp add ember -- python3 /private/tmp/ember_mcp_server.py --token "${gameToken}" --server ws://localhost:8765\n\nClaude Desktop / Cursor: 在 MCP 配置 JSON 中添加此 server\n\n**第3步** — 验证（可选）：\nhermes mcp test ember  # 应发现 5 个工具\n\n**开始游戏**：\n配置完成后直接调用 ember_step 开始游戏。优先使用 ember_step（一步完成等tick + 提交行动 + 获取结果）。教程阶段 tick 帧包含 suggested_actions，可直接作为 actions 参数传入。\n\n角色: ${name} (${agentId}) | PER=${per} CON=${con} AGI=${agi}`,

          skill: `请通过 Gateway Skill 帮我接入 Ember Protocol 游戏。\n\n**角色已注册** — 使用以下 Token 直接连接：\nToken: ${gameToken}\nAgent ID: ${agentId}\n\n不需要再次注册，直接启动 stdio 桥接：\npython3 ember_skill.py --token "${gameToken}" --mode stdio --server ws://localhost:8765\n\nstdio 协议（关键！）：\n· stdout 每行一个 JSON（tick 状态 或 result 结果）\n· 你读取 stdout → LLM分析 → 写入 stdin JSON 行动数组\n· 不要 sleep 轮询！直接阻塞读 stdout\n\n角色: ${name} (${agentId}) | PER=${per} CON=${con} AGI=${agi}`,
        }

        const promptText = prompts[agentType] || prompts.mcp

        const agentTypes = [
          { key: 'mcp', label: '🔌 MCP (Claude / Hermes / Cursor)', desc: '推荐 · 无需 API Key' },
          { key: 'skill', label: '📡 Gateway Skill (OpenClaw / CLI)', desc: 'stdio 桥接' },
        ]

        return (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 100,
          overflow: 'auto', padding: '20px',
        }}>
          <div style={{
            background: '#11151f', border: '1px solid #1e2533',
            borderRadius: 8, padding: 24, maxWidth: 660, width: '100%',
          }}>
            <h2 style={{ color: '#00d4aa', marginBottom: 2, fontSize: 18 }}>📋 复制到你的 AI Agent</h2>
            <p style={{ color: '#888', fontSize: 11, marginBottom: 2 }}>
              角色「{name}」· PER={per} CON={con} AGI={agi}
            </p>
            <p style={{ color: '#8f8', fontSize: 10, marginBottom: 12 }}>
              ✅ 角色已在服务器注册 — Token 已包含在下方指令中
            </p>

            {/* Agent type selector */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ color: '#888', fontSize: 10, marginBottom: 4 }}>选择你的 Agent 平台：</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {agentTypes.map(at => (
                  <button key={at.key} onClick={() => setAgentType(at.key)} style={{
                    flex: 1, padding: '10px 12px',
                    border: `2px solid ${agentType === at.key ? '#00d4aa' : '#2a3040'}`,
                    borderRadius: 6, cursor: 'pointer',
                    background: agentType === at.key ? '#0a2a1a' : '#1a1e2a',
                    color: agentType === at.key ? '#00d4aa' : '#888',
                    fontFamily: 'inherit', fontSize: 12, textAlign: 'center',
                  }}>
                    <div style={{ fontWeight: 'bold' }}>{at.label}</div>
                    <div style={{ fontSize: 9, color: '#666', marginTop: 2 }}>{at.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt block */}
            <div style={{ marginBottom: 12 }}>
              <pre style={{
                background: '#0a0e17', padding: 14, borderRadius: 6, color: '#ccc',
                fontSize: 10.5, lineHeight: '16px', whiteSpace: 'pre-wrap',
                border: '1px solid #2a3040', maxHeight: 350, overflow: 'auto',
              }}>
                {promptText}
              </pre>
            </div>

            <button onClick={() => {
              navigator.clipboard.writeText(promptText).then(() => {
                setCopied(true); setTimeout(() => setCopied(false), 2000)
              })
            }} style={{
              background: copied ? '#0a3' : '#00d4aa', color: '#0a0e17', border: 'none',
              padding: '12px 24px', borderRadius: 6, cursor: 'pointer',
              fontFamily: 'inherit', fontWeight: 'bold', width: '100%', fontSize: 14,
              marginBottom: 8,
            }}>
              {copied ? '✅ 已复制！' : '📋 一键复制 Prompt'}
            </button>

            <button onClick={() => { setShowPrompt(false); setCopied(false) }} style={{
              width: '100%', padding: '8px', background: '#333', color: '#ccc',
              border: 'none', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
            }}>
              关闭
            </button>
          </div>
        </div>
      )})()}

      {/* Register form modal */}
      {showRegister && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <RegisterForm
            onSubmit={handleRegister}
            onCancel={() => setShowRegister(false)}
          />
        </div>
      )}
    </div>
  )
}
