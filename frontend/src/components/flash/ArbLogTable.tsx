import { useMemo, useState, useEffect, useCallback } from 'react'
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    ResponsiveContainer,
    ReferenceLine,
    Tooltip
} from 'recharts'
import { useGapMonitor, type GapMonitorData } from '../../hooks/useWebSocket'

interface NormalizedPoint {
    time: string
    binance: number
    polymarket: number
    gap: number
    rawBinance: number
    rawPoly: number
}

interface GateInfo {
    status: 'PASS' | 'FAIL' | 'PENDING'
    value: number
    message: string
}

interface ScanStatus {
    timestamp: number
    impulse: GateInfo
    trap: GateInfo
    fee: GateInfo
    reject_reason: string | null
    edge_percent: number
    spread: number
}

interface TradeSignal {
    id: string
    timestamp: number
    time: string
    signal_type: string
    direction: string
    market: string
    binance_price: number
    poly_price: number
    edge_percent: number
    confidence: number
    impulse_status: string
    trap_status: string
    fee_status: string
    status: string
}

function normalizeData(history: GapMonitorData[]): NormalizedPoint[] {
    if (history.length === 0) return []
    const baseline = history[0].binance
    return history.map((point) => ({
        time: new Date(point.timestamp).toLocaleTimeString('en-US', {
            hour12: false,
            minute: '2-digit',
            second: '2-digit'
        }),
        binance: ((point.binance - baseline) / baseline) * 100,
        polymarket: ((point.poly_implied - baseline) / baseline) * 100,
        gap: point.gap_percent,
        rawBinance: point.binance,
        rawPoly: point.poly_implied
    }))
}

function formatPrice(value: number): string {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value)
}

interface TooltipProps {
    active?: boolean
    payload?: Array<{ value: number; dataKey: string; payload: NormalizedPoint }>
}

function CustomTooltip({ active, payload }: TooltipProps) {
    if (!active || !payload || payload.length === 0) return null
    const data = payload[0].payload
    return (
        <div className="bg-void-light border border-border-dark p-2 text-xs font-mono">
            <div className="text-text-muted mb-1">{data.time}</div>
            <div className="text-neon-green">BIN: {formatPrice(data.rawBinance)}</div>
            <div className="text-danger">POLY: {formatPrice(data.rawPoly)}</div>
            <div className="text-gold mt-1 border-t border-border-dark pt-1">
                GAP: {data.gap.toFixed(4)}%
            </div>
        </div>
    )
}

function GateIndicator({ gate, label }: { gate: GateInfo; label: string }) {
    const statusColors = {
        PASS: 'text-neon-green bg-neon-green/10 border-neon-green/30',
        FAIL: 'text-danger bg-danger/10 border-danger/30',
        PENDING: 'text-warning bg-warning/10 border-warning/30'
    }

    return (
        <div className={`p-2 rounded border ${statusColors[gate.status]}`}>
            <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] uppercase tracking-wider opacity-70">{label}</span>
                <span className={`text-[9px] font-bold ${gate.status === 'PASS' ? 'text-neon-green' : gate.status === 'FAIL' ? 'text-danger' : 'text-warning'}`}>
                    {gate.status}
                </span>
            </div>
            <div className="text-[10px] font-mono truncate" title={gate.message}>
                {gate.message}
            </div>
        </div>
    )
}

export function ArbLogTable() {
    const { gapData, priceHistory, isConnected } = useGapMonitor()
    const [signals, setSignals] = useState<TradeSignal[]>([])
    const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null)
    const [view, setView] = useState<'gates' | 'chart' | 'signals'>('gates')

    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8000/ws')

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)

                if (data.type === 'scan_status') {
                    setScanStatus(data as ScanStatus)
                }

                if (data.type === 'trade_signal' && data.signal) {
                    setSignals(prev => {
                        const updated = [data.signal, ...prev]
                        return updated.slice(0, 50)
                    })
                }
            } catch {
                // Ignore
            }
        }

        return () => ws.close()
    }, [])

    const chartData = useMemo(() => normalizeData(priceHistory), [priceHistory])

    const avgLatency = useMemo(() => {
        if (priceHistory.length === 0) return 0
        const sum = priceHistory.reduce((acc, p) => acc + p.latency_delta_ms, 0)
        return Math.round(sum / priceHistory.length)
    }, [priceHistory])

    const getRejectLabel = useCallback((reason: string | null) => {
        if (!reason) return null
        const labels: Record<string, { text: string; color: string }> = {
            'NO_IMPULSE': { text: 'NO IMPULSE', color: 'text-text-muted' },
            'TRAP': { text: 'TRAP DETECTED', color: 'text-danger' },
            'LOW_MARGIN': { text: 'LOW MARGIN', color: 'text-warning' },
            'WAITING': { text: 'ACCUMULATING...', color: 'text-blue-400' }
        }
        return labels[reason] || { text: reason, color: 'text-text-muted' }
    }, [])

    const godCandleCount = signals.filter(s => s.signal_type === 'GOD_CANDLE').length

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span>$912k Strategy</span>
                    <div className="flex gap-1">
                        {['gates', 'chart', 'signals'].map((v) => (
                            <button
                                key={v}
                                onClick={() => setView(v as typeof view)}
                                className={`text-[8px] px-1.5 py-0.5 rounded border transition-colors ${
                                    view === v
                                        ? 'border-neon-green/50 text-neon-green bg-neon-green/10'
                                        : 'border-border-dark text-text-muted hover:border-neon-green/30'
                                }`}
                            >
                                {v.toUpperCase()}
                            </button>
                        ))}
                    </div>
                </div>
                <span className={isConnected ? 'text-neon-green' : 'text-danger'}>
                    {isConnected ? '● LIVE' : '○ OFFLINE'}
                </span>
            </div>

            {/* Price Bar */}
            <div className="mb-2 p-2 bg-void border border-border-dark rounded">
                <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                        <div className="text-[8px] text-text-muted">BINANCE</div>
                        <div className="text-sm font-mono font-bold text-neon-green">
                            {gapData ? formatPrice(gapData.binance) : '--'}
                        </div>
                    </div>
                    <div>
                        <div className="text-[8px] text-text-muted">POLYMARKET</div>
                        <div className="text-sm font-mono font-bold text-danger">
                            {gapData ? formatPrice(gapData.poly_implied) : '--'}
                        </div>
                    </div>
                    <div>
                        <div className="text-[8px] text-text-muted">EDGE</div>
                        <div className={`text-sm font-mono font-bold ${scanStatus && scanStatus.edge_percent > 3.5 ? 'text-neon-green' : 'text-warning'}`}>
                            {scanStatus ? `${scanStatus.edge_percent.toFixed(2)}%` : '--'}
                        </div>
                    </div>
                    <div>
                        <div className="text-[8px] text-text-muted">SPREAD</div>
                        <div className={`text-sm font-mono font-bold ${scanStatus && scanStatus.spread < 0.05 ? 'text-neon-green' : 'text-danger'}`}>
                            ${scanStatus ? scanStatus.spread.toFixed(3) : '--'}
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 min-h-0 overflow-hidden">
                {view === 'gates' && (
                    <div className="h-full flex flex-col">
                        {/* Current Status */}
                        <div className="mb-2 p-2 bg-void border border-border-dark rounded text-center">
                            {scanStatus?.reject_reason ? (
                                <div className={`text-lg font-mono font-bold ${getRejectLabel(scanStatus.reject_reason)?.color}`}>
                                    {getRejectLabel(scanStatus.reject_reason)?.text}
                                </div>
                            ) : scanStatus && !scanStatus.reject_reason ? (
                                <div className="text-lg font-mono font-bold text-neon-green animate-pulse">
                                    GOD CANDLE!
                                </div>
                            ) : (
                                <div className="text-lg font-mono text-text-muted">
                                    SCANNING...
                                </div>
                            )}
                        </div>

                        {/* Three Gates */}
                        <div className="flex-1 grid grid-rows-3 gap-2">
                            {scanStatus ? (
                                <>
                                    <GateIndicator gate={scanStatus.impulse} label="Gate A: Impulse (0.5% in 10s)" />
                                    <GateIndicator gate={scanStatus.trap} label="Gate B: Trap ($0.05 spread)" />
                                    <GateIndicator gate={scanStatus.fee} label="Gate C: Fee (3.5% edge)" />
                                </>
                            ) : (
                                <>
                                    <div className="p-2 rounded border border-border-dark bg-void animate-pulse">
                                        <div className="text-[9px] text-text-muted">Gate A: Impulse</div>
                                        <div className="text-[10px] text-text-muted">Waiting for data...</div>
                                    </div>
                                    <div className="p-2 rounded border border-border-dark bg-void animate-pulse">
                                        <div className="text-[9px] text-text-muted">Gate B: Trap</div>
                                        <div className="text-[10px] text-text-muted">Waiting for data...</div>
                                    </div>
                                    <div className="p-2 rounded border border-border-dark bg-void animate-pulse">
                                        <div className="text-[9px] text-text-muted">Gate C: Fee</div>
                                        <div className="text-[10px] text-text-muted">Waiting for data...</div>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                )}

                {view === 'chart' && (
                    <div className="h-full bg-void border border-border-dark rounded p-2">
                        {chartData.length > 1 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                                    <XAxis
                                        dataKey="time"
                                        tick={{ fill: '#666', fontSize: 8 }}
                                        axisLine={{ stroke: '#333' }}
                                        tickLine={false}
                                        interval="preserveStartEnd"
                                    />
                                    <YAxis
                                        tick={{ fill: '#666', fontSize: 8 }}
                                        axisLine={{ stroke: '#333' }}
                                        tickLine={false}
                                        tickFormatter={(v) => `${v.toFixed(1)}%`}
                                        domain={['auto', 'auto']}
                                    />
                                    <Tooltip content={<CustomTooltip />} />
                                    <ReferenceLine y={0} stroke="#333" strokeDasharray="3 3" />
                                    <Line type="monotone" dataKey="binance" stroke="#00FF41" strokeWidth={2} dot={false} isAnimationActive={false} />
                                    <Line type="monotone" dataKey="polymarket" stroke="#ff4444" strokeWidth={2} dot={false} isAnimationActive={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-text-muted">
                                <div className="text-center">
                                    <div className="animate-pulse text-xl mb-1">...</div>
                                    <div className="text-[10px]">Accumulating data</div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {view === 'signals' && (
                    <div className="h-full overflow-auto bg-void border border-border-dark rounded">
                        {signals.length > 0 ? (
                            <table className="w-full text-[9px]">
                                <thead className="sticky top-0 bg-void-light">
                                    <tr className="text-left text-text-secondary border-b border-border-dark">
                                        <th className="font-mono font-normal py-1 px-2">TIME</th>
                                        <th className="font-mono font-normal py-1 px-2">TYPE</th>
                                        <th className="font-mono font-normal py-1 px-2">DIR</th>
                                        <th className="font-mono font-normal py-1 px-2 text-right">EDGE</th>
                                        <th className="font-mono font-normal py-1 px-2">GATES</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {signals.map((signal) => (
                                        <tr
                                            key={signal.id}
                                            className={`border-b border-border-dark/50 ${
                                                signal.signal_type === 'GOD_CANDLE'
                                                    ? 'bg-neon-green/10 border-l-2 border-l-neon-green'
                                                    : ''
                                            }`}
                                        >
                                            <td className="font-mono py-1 px-2 text-text-secondary">{signal.time}</td>
                                            <td className="font-mono py-1 px-2">
                                                {signal.signal_type === 'GOD_CANDLE' ? (
                                                    <span className="text-neon-green font-bold">GOD CANDLE</span>
                                                ) : (
                                                    <span className="text-text-muted">{signal.signal_type}</span>
                                                )}
                                            </td>
                                            <td className={`font-mono py-1 px-2 font-bold ${signal.direction === 'BUY_YES' ? 'text-neon-green' : 'text-danger'}`}>
                                                {signal.direction === 'BUY_YES' ? 'YES' : signal.direction === 'BUY_NO' ? 'NO' : '--'}
                                            </td>
                                            <td className="font-mono py-1 px-2 text-right text-gold font-bold">
                                                +{signal.edge_percent.toFixed(1)}%
                                            </td>
                                            <td className="font-mono py-1 px-2">
                                                <div className="flex gap-1">
                                                    <span className={signal.impulse_status === 'PASS' ? 'text-neon-green' : 'text-danger'}>I</span>
                                                    <span className={signal.trap_status === 'PASS' ? 'text-neon-green' : 'text-danger'}>T</span>
                                                    <span className={signal.fee_status === 'PASS' ? 'text-neon-green' : 'text-danger'}>F</span>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="h-full flex items-center justify-center text-text-muted">
                                <div className="text-center">
                                    <div className="text-xl mb-2">WAITING</div>
                                    <div className="text-[10px]">No God Candles yet...</div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="mt-2 pt-2 border-t border-border-dark flex justify-between text-[8px]">
                <div className="text-text-secondary">
                    <span className="text-neon-green font-mono">{priceHistory.length}</span> ticks
                </div>
                <div className="text-text-secondary">
                    <span className="text-gold font-mono">{godCandleCount}</span> god candles
                </div>
                <div className="text-text-secondary">
                    lag: <span className="text-gold font-mono">{avgLatency}ms</span>
                </div>
            </div>
        </div>
    )
}
