interface StatusHeaderProps {
    isConnected: boolean
    latency: string
}

export function StatusHeader({ isConnected, latency }: StatusHeaderProps) {
    return (
        <header className="flex items-center justify-between px-4 py-2 border-b border-border-dark bg-void-light">
            {/* Logo & Title */}
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-gradient-to-br from-neon-green to-gold flex items-center justify-center">
                    <span className="font-mono font-bold text-void text-sm">PS</span>
                </div>
                <div>
                    <h1 className="font-mono font-bold text-sm tracking-wider">
                        POLYSWARM <span className="text-text-secondary">2.0</span>
                    </h1>
                    <p className="text-[10px] text-text-muted tracking-widest uppercase">
                        War Room Terminal
                    </p>
                </div>
            </div>

            {/* Status Indicators */}
            <div className="flex items-center gap-6">
                {/* Latency */}
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-text-muted uppercase tracking-wider">Latency</span>
                    <span className="font-mono text-sm text-neon-green">{latency}</span>
                </div>

                {/* Connection Status */}
                <div className="flex items-center gap-2">
                    {isConnected ? (
                        <>
                            <div className="w-2 h-2 rounded-full bg-neon-green pulse-glow" />
                            <span className="font-mono text-xs text-neon-green">ONLINE</span>
                        </>
                    ) : (
                        <>
                            <div className="w-2 h-2 rounded-full bg-danger blink" />
                            <span className="font-mono text-xs text-danger blink">OFFLINE</span>
                        </>
                    )}
                </div>
            </div>
        </header>
    )
}
