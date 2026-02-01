import { useEffect, useState, useCallback, useRef } from 'react'

interface HeartbeatData {
    type: string
    latency: string
    active_cores: string[]
    timestamp: string
    status: {
        flash: {
            state: string
            markets_scanning: number
            opportunities: number
        }
        swarm: {
            state: string
            agents_ready: number
            consensus: string | null
        }
    }
}

export interface GapMonitorData {
    type: 'gap_monitor'
    binance: number
    poly_implied: number
    gap_percent: number
    latency_delta_ms: number
    timestamp: number
    binance_ts: number
    poly_ts: number
}

interface ConnectionState {
    isConnected: boolean
    latency: string
    lastHeartbeat: HeartbeatData | null
}

// Separate hook for gap monitor data to optimize re-renders
export function useGapMonitor(url: string = 'ws://localhost:8000/ws') {
    const [gapData, setGapData] = useState<GapMonitorData | null>(null)
    const [priceHistory, setPriceHistory] = useState<GapMonitorData[]>([])
    const socketRef = useRef<WebSocket | null>(null)
    const [isConnected, setIsConnected] = useState(false)

    const connect = useCallback(() => {
        const ws = new WebSocket(url)

        ws.onopen = () => {
            console.log('[GAP] Connected to Reality Gap stream')
            setIsConnected(true)
        }

        ws.onclose = () => {
            console.log('[GAP] Disconnected from stream')
            setIsConnected(false)
            // Reconnect after 3 seconds
            setTimeout(connect, 3000)
        }

        ws.onerror = (error) => {
            console.error('[GAP] Error:', error)
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.type === 'gap_monitor') {
                    const gapUpdate = data as GapMonitorData
                    setGapData(gapUpdate)

                    // Add to price history (keep last 60 points for chart)
                    setPriceHistory(prev => {
                        const updated = [...prev, gapUpdate]
                        return updated.slice(-60)
                    })
                }
            } catch (e) {
                // Ignore parse errors for non-JSON messages
            }
        }

        socketRef.current = ws
    }, [url])

    useEffect(() => {
        connect()

        return () => {
            socketRef.current?.close()
        }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    return { gapData, priceHistory, isConnected }
}

export function useWebSocket(url: string = 'ws://localhost:8000/ws') {
    const [connectionState, setConnectionState] = useState<ConnectionState>({
        isConnected: false,
        latency: '--',
        lastHeartbeat: null
    })
    const [socket, setSocket] = useState<WebSocket | null>(null)

    const connect = useCallback(() => {
        const ws = new WebSocket(url)

        ws.onopen = () => {
            console.log('[WS] Connected to War Room')
            setConnectionState(prev => ({ ...prev, isConnected: true }))
        }

        ws.onclose = () => {
            console.log('[WS] Disconnected from War Room')
            setConnectionState(prev => ({
                ...prev,
                isConnected: false,
                latency: '--'
            }))
            // Reconnect after 3 seconds
            setTimeout(connect, 3000)
        }

        ws.onerror = (error) => {
            console.error('[WS] Error:', error)
        }

        ws.onmessage = (event) => {
            try {
                const data: HeartbeatData = JSON.parse(event.data)
                if (data.type === 'heartbeat') {
                    setConnectionState(prev => ({
                        ...prev,
                        latency: data.latency,
                        lastHeartbeat: data
                    }))
                }
            } catch (e) {
                console.error('[WS] Parse error:', e)
            }
        }

        setSocket(ws)
    }, [url])

    useEffect(() => {
        connect()

        return () => {
            socket?.close()
        }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    return connectionState
}
