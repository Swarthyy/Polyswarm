import { useEffect, useState, useCallback } from 'react'

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

interface ConnectionState {
    isConnected: boolean
    latency: string
    lastHeartbeat: HeartbeatData | null
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
