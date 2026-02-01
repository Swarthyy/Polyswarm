interface Agent {
    id: string
    name: string
    role: 'BELIEVER' | 'SKEPTIC' | 'ANALYST'
    status: 'IDLE' | 'THINKING' | 'SPEAKING'
    avatar: string
}

const agents: Agent[] = [
    { id: '1', name: 'The Believer', role: 'BELIEVER', status: 'IDLE', avatar: '🟢' },
    { id: '2', name: 'The Skeptic', role: 'SKEPTIC', status: 'IDLE', avatar: '🔴' },
    { id: '3', name: 'The Analyst', role: 'ANALYST', status: 'IDLE', avatar: '🔵' },
]

const roleColors = {
    BELIEVER: 'from-neon-green/20 to-neon-green/5 border-neon-green/30',
    SKEPTIC: 'from-danger/20 to-danger/5 border-danger/30',
    ANALYST: 'from-blue-500/20 to-blue-500/5 border-blue-500/30'
}

export function SwarmRing() {
    return (
        <div className="h-full flex flex-col items-center justify-center">
            {/* Central Ring Visualization */}
            <div className="relative w-80 h-80">
                {/* Outer Ring */}
                <div className="absolute inset-0 rounded-full border-2 border-gold/20" />
                <div className="absolute inset-4 rounded-full border border-gold/10" />
                <div className="absolute inset-8 rounded-full border border-dashed border-gold/5" />

                {/* Center Node */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-gold/20 to-transparent border border-gold/30 flex flex-col items-center justify-center">
                        <span className="text-gold font-mono text-[10px] tracking-widest">CONSENSUS</span>
                        <span className="text-gold font-mono text-lg font-bold">--</span>
                        <span className="text-text-muted text-[8px]">AWAITING INPUT</span>
                    </div>
                </div>

                {/* Agent Nodes positioned around the ring */}
                {agents.map((agent, index) => {
                    const angle = (index * 120 - 90) * (Math.PI / 180)
                    const radius = 120
                    const x = Math.cos(angle) * radius
                    const y = Math.sin(angle) * radius

                    return (
                        <div
                            key={agent.id}
                            className="absolute w-16 h-16 -translate-x-1/2 -translate-y-1/2"
                            style={{
                                left: `calc(50% + ${x}px)`,
                                top: `calc(50% + ${y}px)`
                            }}
                        >
                            <div className={`
                w-full h-full rounded-full 
                bg-gradient-to-br ${roleColors[agent.role]}
                border flex flex-col items-center justify-center
                transition-all duration-300
                ${agent.status === 'THINKING' ? 'animate-pulse' : ''}
              `}>
                                <span className="text-xl">{agent.avatar}</span>
                                <span className="text-[8px] text-text-secondary font-mono mt-0.5">
                                    {agent.status}
                                </span>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Agent Legend */}
            <div className="mt-8 flex gap-6">
                {agents.map(agent => (
                    <div key={agent.id} className="flex items-center gap-2">
                        <span className="text-sm">{agent.avatar}</span>
                        <div>
                            <p className="font-mono text-xs text-text-primary">{agent.name}</p>
                            <p className="text-[10px] text-text-muted">{agent.role}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Status Message */}
            <div className="mt-8 text-center">
                <p className="font-mono text-xs text-text-secondary">
                    Swarm is on <span className="text-gold">STANDBY</span>
                </p>
                <p className="text-[10px] text-text-muted mt-1">
                    Waiting for market trigger or manual query...
                </p>
            </div>
        </div>
    )
}
