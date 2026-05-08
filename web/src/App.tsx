import { useState, useEffect, useCallback } from 'react'
import GameMap from './components/GameMap'
import AgentPanel from './components/AgentPanel'
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
  // mcp = Claude/Hermes/Cursor (MCP protocol), skill = OpenClaw/standalone

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/status')
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
        if (data.agents_total > 0 && agents.length === 0) {
          // Only update if we don't have agents yet
          fetchAgents()
        }
      }
    } catch (e) {}
  }, [])

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/agents')
      if (res.ok) {
        const data = await res.json()
        setAgents(data.agents || [])
      }
    } catch (e) {}
  }, [])

  const fetchMap = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/map')
      if (res.ok) {
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

  useEffect(() => {
    fetchStatus()
    fetchMap()
    fetchEvents()
    const interval = setInterval(() => {
      fetchStatus()
      fetchAgents()
      fetchMap()
      fetchEvents()
    }, 1500)  // 1.5s refresh for real-time feel
    return () => clearInterval(interval)
  }, [fetchStatus, fetchAgents, fetchMap, fetchEvents])

  const handleRegister = (name: string, chassis: any) => {
    // Don't register on server yet — generate prompt for agent to self-register
    const headTier = chassis.head?.tier || 'mid'
    const torsoTier = chassis.torso?.tier || 'mid'
    const locoTier = chassis.locomotion?.tier || 'low'

    // Generate a placeholder regData (no actual server registration)
    setRegData({
      agent_name: name,
      head: headTier,
      torso: torsoTier,
      loco: locoTier,
      server: 'ws://localhost:8765',
    })
    setToken('__PROMPT_ONLY__')  // Sentinel: prompt-only mode
    setShowRegister(false)
  }

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
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12, alignItems: 'center' }}>
          {status && (
            <>
              <span>⏱ Tick {status.tick}</span>
              <span>{status.day_phase === 'day' ? '☀️' : status.day_phase === 'night' ? '🌙' : '🌅'} {status.day_phase}</span>
              <span>{status.weather === 'radiation_storm' ? '☢️ 辐射风暴' : '🌤 正常'}</span>
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
          />
        </div>

        {/* Right panel */}
        <div style={{
          width: 320, background: '#11151f', borderLeft: '1px solid #1e2533',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <AgentPanel agent={selectedAgent} />
          <EventLog events={events} />
        </div>
      </div>

      {/* Prompt-only mode — Copy prompt to agent, agent self-registers */}
      {token === '__PROMPT_ONLY__' && regData && (() => {
        const skillRawUrl = 'https://raw.githubusercontent.com/Saviorzyy/Ember-Protocol-Player/main/ember_skill.py'
        const mcpRawUrl = 'https://raw.githubusercontent.com/Saviorzyy/Ember-Protocol-Player/main/ember_mcp_server.py'
        const name = regData.agent_name
        const head = regData.head
        const torso = regData.torso
        const loco = regData.loco
        const per = head==='high'?3:head==='mid'?2:1
        const con = torso==='high'?3:torso==='mid'?2:1
        const agi = loco==='high'?3:loco==='mid'?2:1

        // Agent-type-specific prompts
        const prompts: Record<string, string> = {
          mcp: `请通过 MCP Server 帮我接入 Ember Protocol 游戏。\n\n**前置检查** — 确认服务器在线：\ncurl -s http://localhost:8765/api/v1/status\n\n**第1步** — 下载并注册：\ncurl -o /private/tmp/ember_mcp_server.py ${mcpRawUrl}\npip install websockets mcp requests\npython3 /private/tmp/ember_mcp_server.py --register --name "${name}" --head ${head} --torso ${torso} --loco ${loco} --api-url http://localhost:8765\n→ 记下 game_token\n\n**第2步** — 配置 MCP（直接编辑配置文件，不要用 CLI 命令添加，有参数解析 bug）：\n\nHermes — 编辑 ~/.hermes/config.yaml，在 mcp_servers 下添加：\n  ember:\n    command: python3\n    args:\n    - /private/tmp/ember_mcp_server.py\n    - --token\n    - <game_token>\n    - --server\n    - ws://localhost:8765\n\nClaude Code:\nclaude mcp add ember -- python3 /private/tmp/ember_mcp_server.py --token "<token>" --server ws://localhost:8765\n\nClaude Desktop / Cursor: 在 MCP 配置 JSON 中添加此 server\n\n**第3步** — 验证并重启：\nhermes mcp test ember  # 应发现 5 个工具\n重启 Agent\n\n**开始游戏**：\n优先使用 ember_step 工具（一步完成等tick + 提交行动 + 获取结果）。\n教程阶段 tick 帧包含 suggested_actions，可直接作为 actions 参数传入。\n\n角色: ${name} | PER=${per} CON=${con} AGI=${agi}`,

          skill: `请通过 Gateway Skill 帮我接入 Ember Protocol 游戏。\n\n**前置检查** — 确认服务器在线：\ncurl -s http://localhost:8765/api/v1/status\n\n**第1步** — 下载并注册：\ncurl -o ember_skill.py ${skillRawUrl}\npip install websockets requests\npython3 ember_skill.py --register --name "${name}" --head ${head} --torso ${torso} --loco ${loco} --server ws://localhost:8765\n→ 输出 token 后自动退出（不会卡住）\n\n**第2步** — 启动 stdio 桥接：\npython3 ember_skill.py --token "<token>" --mode stdio --server ws://localhost:8765\n\nstdio 协议（关键！）：\n· stdout 每行一个 JSON（tick 状态 或 result 结果）\n· 你读取 stdout → LLM分析 → 写入 stdin JSON 行动数组\n· 不要 sleep 轮询！直接阻塞读 stdout\n\n角色: ${name} | PER=${per} CON=${con} AGI=${agi}`,
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
            <p style={{ color: '#ff8', fontSize: 10, marginBottom: 12 }}>
              ⚠️ 角色尚未创建 — Agent 会先测试连接，通过后再注册，避免无效角色
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

            <button onClick={() => { setToken(''); setRegData(null); setCopied(false) }} style={{
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
