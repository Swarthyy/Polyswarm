interface ArbLogEntry {
    id: string
    time: string
    market: string
    signal: 'BUY' | 'SELL' | 'HOLD'
    binancePrice: string
    polyPrice: string
    edge: string
    status: 'PENDING' | 'EXECUTED' | 'MISSED' | 'BLOCKED'
}

// Mock data for the placeholder table
const mockLogs: ArbLogEntry[] = [
    {
        id: '001',
        time: '17:58:12',
        market: 'BTC-HALVING',
        signal: 'BUY',
        binancePrice: '0.72',
        polyPrice: '0.68',
        edge: '+5.88%',
        status: 'PENDING'
    },
    {
        id: '002',
        time: '17:58:09',
        market: 'ETH-10K',
        signal: 'HOLD',
        binancePrice: '0.45',
        polyPrice: '0.44',
        edge: '+2.27%',
        status: 'BLOCKED'
    },
    {
        id: '003',
        time: '17:58:05',
        market: 'SOL-ATH',
        signal: 'BUY',
        binancePrice: '0.61',
        polyPrice: '0.55',
        edge: '+10.9%',
        status: 'EXECUTED'
    },
    {
        id: '004',
        time: '17:57:58',
        market: 'XRP-WIN',
        signal: 'SELL',
        binancePrice: '0.38',
        polyPrice: '0.42',
        edge: '-9.52%',
        status: 'MISSED'
    },
]

const signalColors = {
    BUY: 'text-neon-green',
    SELL: 'text-danger',
    HOLD: 'text-text-secondary'
}

const statusColors = {
    PENDING: 'text-warning',
    EXECUTED: 'text-neon-green',
    MISSED: 'text-danger',
    BLOCKED: 'text-text-muted'
}

export function ArbLogTable() {
    return (
        <div className="h-full flex flex-col">
            {/* Table Header */}
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>Arbitrage Signals</span>
                <span className="text-neon-green">● SCANNING</span>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-left text-text-secondary border-b border-border-dark">
                            <th className="font-mono font-normal py-2 pr-2">TIME</th>
                            <th className="font-mono font-normal py-2 pr-2">MARKET</th>
                            <th className="font-mono font-normal py-2 pr-2">SIG</th>
                            <th className="font-mono font-normal py-2 pr-2">EDGE</th>
                            <th className="font-mono font-normal py-2">STATUS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {mockLogs.map((log) => (
                            <tr
                                key={log.id}
                                className="border-b border-border-dark/50 hover:bg-void-light transition-colors"
                            >
                                <td className="font-mono py-2 pr-2 text-text-secondary">
                                    {log.time}
                                </td>
                                <td className="font-mono py-2 pr-2 text-text-primary">
                                    {log.market}
                                </td>
                                <td className={`font-mono py-2 pr-2 font-semibold ${signalColors[log.signal]}`}>
                                    {log.signal}
                                </td>
                                <td className={`font-mono py-2 pr-2 ${log.edge.startsWith('+') ? 'text-neon-green' : 'text-danger'
                                    }`}>
                                    {log.edge}
                                </td>
                                <td className={`font-mono py-2 ${statusColors[log.status]}`}>
                                    {log.status}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Footer Stats */}
            <div className="mt-3 pt-3 border-t border-border-dark flex justify-between text-[10px]">
                <div className="text-text-secondary">
                    <span className="text-neon-green font-mono">24</span> markets scanned
                </div>
                <div className="text-text-secondary">
                    <span className="text-gold font-mono">3</span> opportunities
                </div>
            </div>
        </div>
    )
}
