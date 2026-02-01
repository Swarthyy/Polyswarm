import { useMemo } from 'react'
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

function normalizeData(history: GapMonitorData[]): NormalizedPoint[] {
    if (history.length === 0) return []

    // Get baseline (first price) for normalization
    const baseline = history[0].binance

    return history.map((point, index) => ({
        time: new Date(point.timestamp).toLocaleTimeString('en-US', {
            hour12: false,
            minute: '2-digit',
            second: '2-digit'
        }),
        // Normalize to percentage deviation from baseline
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
    payload?: Array<{
        value: number
        dataKey: string
        payload: NormalizedPoint
    }>
}

function CustomTooltip({ active, payload }: TooltipProps) {
    if (!active || !payload || payload.length === 0) return null

    const data = payload[0].payload

    return (
        <div className="bg-void-light border border-border-dark p-2 text-xs font-mono">
            <div className="text-text-muted mb-1">{data.time}</div>
            <div className="text-neon-green">
                BIN: {formatPrice(data.rawBinance)}
            </div>
            <div className="text-danger">
                POLY: {formatPrice(data.rawPoly)}
            </div>
            <div className="text-gold mt-1 border-t border-border-dark pt-1">
                GAP: {data.gap.toFixed(4)}%
            </div>
        </div>
    )
}

export function ArbLogTable() {
    const { gapData, priceHistory, isConnected } = useGapMonitor()

    const chartData = useMemo(() => normalizeData(priceHistory), [priceHistory])

    // Calculate average latency delta
    const avgLatency = useMemo(() => {
        if (priceHistory.length === 0) return 0
        const sum = priceHistory.reduce((acc, p) => acc + p.latency_delta_ms, 0)
        return Math.round(sum / priceHistory.length)
    }, [priceHistory])

    // Get current gap direction
    const gapDirection = gapData
        ? gapData.gap_percent > 0 ? 'BINANCE LEADS' : 'POLY LEADS'
        : '--'

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="text-[10px] text-text-muted uppercase tracking-wider mb-3 flex items-center justify-between">
                <span>Reality Gap Monitor</span>
                <span className={isConnected ? 'text-neon-green' : 'text-danger'}>
                    {isConnected ? '● STREAMING' : '○ DISCONNECTED'}
                </span>
            </div>

            {/* Latency Delta Display */}
            <div className="mb-4 p-3 bg-void border border-border-dark rounded">
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">
                    Latency Delta
                </div>
                <div className="flex items-baseline justify-between">
                    <span className="text-3xl font-mono font-bold text-gold">
                        {gapData ? Math.round(gapData.latency_delta_ms) : '--'}
                        <span className="text-sm text-text-secondary ml-1">ms</span>
                    </span>
                    <span className={`text-xs font-mono ${gapData && gapData.gap_percent > 0 ? 'text-neon-green' : 'text-danger'}`}>
                        {gapDirection}
                    </span>
                </div>
            </div>

            {/* Price Display */}
            <div className="grid grid-cols-2 gap-2 mb-4">
                <div className="p-2 bg-void border border-neon-green/30 rounded">
                    <div className="text-[9px] text-neon-green uppercase tracking-wider mb-1">
                        Binance BTC
                    </div>
                    <div className="text-lg font-mono font-semibold text-neon-green">
                        {gapData ? formatPrice(gapData.binance) : '--'}
                    </div>
                </div>
                <div className="p-2 bg-void border border-danger/30 rounded">
                    <div className="text-[9px] text-danger uppercase tracking-wider mb-1">
                        Polymarket Implied
                    </div>
                    <div className="text-lg font-mono font-semibold text-danger">
                        {gapData ? formatPrice(gapData.poly_implied) : '--'}
                    </div>
                </div>
            </div>

            {/* Gap Percentage */}
            <div className="mb-4 p-2 bg-void border border-gold/30 rounded text-center">
                <div className="text-[9px] text-gold uppercase tracking-wider mb-1">
                    Spread Gap
                </div>
                <div className={`text-2xl font-mono font-bold ${gapData && gapData.gap_percent > 0 ? 'text-neon-green' : 'text-danger'}`}>
                    {gapData ? (gapData.gap_percent > 0 ? '+' : '') + gapData.gap_percent.toFixed(4) : '--'}%
                </div>
            </div>

            {/* Live Heartbeat Chart */}
            <div className="flex-1 min-h-[200px]">
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">
                    Live Heartbeat (Normalized)
                </div>
                <div className="h-[calc(100%-20px)] bg-void border border-border-dark rounded p-2">
                    {chartData.length > 1 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                                data={chartData}
                                margin={{ top: 5, right: 5, bottom: 5, left: -20 }}
                            >
                                <XAxis
                                    dataKey="time"
                                    tick={{ fill: '#666', fontSize: 9 }}
                                    axisLine={{ stroke: '#333' }}
                                    tickLine={false}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    tick={{ fill: '#666', fontSize: 9 }}
                                    axisLine={{ stroke: '#333' }}
                                    tickLine={false}
                                    tickFormatter={(v) => `${v.toFixed(2)}%`}
                                    domain={['auto', 'auto']}
                                />
                                <Tooltip content={<CustomTooltip />} />
                                <ReferenceLine y={0} stroke="#333" strokeDasharray="3 3" />

                                {/* Binance Line - Green, moves first */}
                                <Line
                                    type="monotone"
                                    dataKey="binance"
                                    stroke="#00FF41"
                                    strokeWidth={2}
                                    dot={false}
                                    isAnimationActive={false}
                                    name="Binance"
                                />

                                {/* Polymarket Line - Red, lags behind */}
                                <Line
                                    type="monotone"
                                    dataKey="polymarket"
                                    stroke="#ff4444"
                                    strokeWidth={2}
                                    dot={false}
                                    isAnimationActive={false}
                                    name="Polymarket"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-full flex items-center justify-center text-text-muted text-sm">
                            <div className="text-center">
                                <div className="animate-pulse text-2xl mb-2">...</div>
                                <div>Waiting for data stream</div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Legend */}
            <div className="mt-3 flex justify-center gap-6 text-[10px]">
                <div className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-neon-green"></span>
                    <span className="text-neon-green">BINANCE (REAL-TIME)</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-danger"></span>
                    <span className="text-danger">POLYMARKET (LAGGED)</span>
                </div>
            </div>

            {/* Footer Stats */}
            <div className="mt-3 pt-3 border-t border-border-dark flex justify-between text-[10px]">
                <div className="text-text-secondary">
                    <span className="text-neon-green font-mono">{priceHistory.length}</span> samples
                </div>
                <div className="text-text-secondary">
                    avg lag: <span className="text-gold font-mono">{avgLatency}ms</span>
                </div>
            </div>
        </div>
    )
}
