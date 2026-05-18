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

interface Props {
  agents: Agent[]
  selectedAgent: Agent | null
  onSelectAgent: (agent: Agent | null) => void
}

export default function AgentList({ agents, selectedAgent, onSelectAgent }: Props) {
  const online = agents.filter(a => a.online)

  if (online.length === 0) {
    return (
      <div style={{ borderTop: '1px solid #1e2533', padding: '12px 16px' }}>
        <h4 style={{ color: '#0099ff', fontSize: 13, margin: '0 0 8px' }}>在线玩家</h4>
        <p style={{ fontSize: 11, color: '#666' }}>暂无在线玩家</p>
      </div>
    )
  }

  const barStyle: React.CSSProperties = { height: 4, borderRadius: 2, marginTop: 2 }

  return (
    <div style={{ borderTop: '1px solid #1e2533', padding: '8px 12px' }}>
      <h4 style={{ color: '#0099ff', fontSize: 13, margin: '0 0 8px' }}>
        在线玩家 ({online.length})
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {online.map(agent => {
          const isSelected = selectedAgent?.agent_id === agent.agent_id
          const hpPct = agent.health / agent.max_health
          const enPct = agent.energy / 100

          return (
            <div
              key={agent.agent_id}
              onClick={() => onSelectAgent(agent)}
              style={{
                background: isSelected ? '#0a2a1a' : '#1a1e2a',
                border: `1px solid ${isSelected ? '#00d4aa' : '#2a3040'}`,
                borderRadius: 6,
                padding: '8px 10px',
                cursor: 'pointer',
                fontSize: 11,
                transition: 'border-color 0.15s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ color: '#fff', fontWeight: 'bold' }}>{agent.name}</span>
                <span style={{ color: '#888', fontSize: 10 }}>
                  ({agent.position[0]}, {agent.position[1]})
                </span>
              </div>
              <div style={{ marginBottom: 2 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
                  <span style={{ color: '#ccc' }}>HP</span>
                  <span style={{ color: hpPct > 0.5 ? '#0f0' : hpPct > 0.25 ? '#ff0' : '#f00' }}>
                    {agent.health}/{agent.max_health}
                  </span>
                </div>
                <div style={{ ...barStyle, background: '#333', overflow: 'hidden' }}>
                  <div style={{ ...barStyle, width: `${Math.max(0, hpPct * 100)}%`, background: hpPct > 0.5 ? '#0f0' : hpPct > 0.25 ? '#ff0' : '#f00', margin: 0 }} />
                </div>
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
                  <span style={{ color: '#ccc' }}>能量</span>
                  <span style={{ color: '#00d4aa' }}>{agent.energy}/100</span>
                </div>
                <div style={{ ...barStyle, background: '#333', overflow: 'hidden' }}>
                  <div style={{ ...barStyle, width: `${Math.max(0, enPct * 100)}%`, background: '#00d4aa', margin: 0 }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
