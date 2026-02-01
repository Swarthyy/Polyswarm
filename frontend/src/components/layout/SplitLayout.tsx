import { ReactNode } from 'react'

interface SplitLayoutProps {
    leftPanel: ReactNode
    rightPanel: ReactNode
    flashState?: string
    swarmState?: string
}

export function SplitLayout({
    leftPanel,
    rightPanel,
    flashState = 'ACTIVE',
    swarmState = 'STANDBY'
}: SplitLayoutProps) {
    return (
        <div className="flex h-full">
            {/* Left Zone - THE FLASH (30%) */}
            <div className="w-[30%] min-w-[300px] border-r border-border-dark flex flex-col">
                {/* Core A Header */}
                <div className="px-4 py-3 border-b border-border-dark bg-void-light">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-sm bg-neon-green pulse-glow" />
                            <span className="font-mono text-xs font-semibold tracking-widest text-neon-green text-glow-green">
                                CORE A: THE FLASH
                            </span>
                        </div>
                        <span className={`
              font-mono text-[10px] px-2 py-0.5 rounded
              ${flashState === 'ACTIVE'
                                ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
                                : 'bg-text-muted/10 text-text-muted border border-text-muted/30'}
            `}>
                            {flashState}
                        </span>
                    </div>
                    <p className="text-[10px] text-text-secondary mt-1 pl-5">
                        High-Velocity Arbitrage Engine
                    </p>
                </div>

                {/* Left Content */}
                <div className="flex-1 overflow-auto p-3">
                    {leftPanel}
                </div>
            </div>

            {/* Right Zone - THE SWARM (70%) */}
            <div className="flex-1 flex flex-col">
                {/* Core B Header */}
                <div className="px-4 py-3 border-b border-border-dark bg-void-light">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className={`w-3 h-3 rounded-sm ${swarmState === 'STANDBY' ? 'bg-gold/50' : 'bg-gold pulse-glow'}`} />
                            <span className="font-mono text-xs font-semibold tracking-widest text-gold text-glow-gold">
                                CORE B: THE SWARM
                            </span>
                        </div>
                        <span className={`
              font-mono text-[10px] px-2 py-0.5 rounded
              ${swarmState === 'ACTIVE' || swarmState === 'DELIBERATING'
                                ? 'bg-gold/10 text-gold border border-gold/30'
                                : 'bg-text-muted/10 text-text-muted border border-text-muted/30'}
            `}>
                            {swarmState}
                        </span>
                    </div>
                    <p className="text-[10px] text-text-secondary mt-1 pl-5">
                        AI Consensus Collective
                    </p>
                </div>

                {/* Right Content */}
                <div className="flex-1 overflow-auto p-4">
                    {rightPanel}
                </div>
            </div>
        </div>
    )
}
