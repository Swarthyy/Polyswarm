import './index.css'
import { StatusHeader } from './components/shared/StatusHeader'
import { SplitLayout } from './components/layout/SplitLayout'
import { ArbLogTable } from './components/flash/ArbLogTable'
import { SwarmRing } from './components/swarm/SwarmRing'
import { useWebSocket } from './hooks/useWebSocket'

function App() {
  const { isConnected, latency, lastHeartbeat } = useWebSocket()

  // Extract core states from heartbeat
  const flashState = lastHeartbeat?.status?.flash?.state ?? 'OFFLINE'
  const swarmState = lastHeartbeat?.status?.swarm?.state ?? 'OFFLINE'

  return (
    <div className="h-screen flex flex-col bg-void">
      {/* Top Header */}
      <StatusHeader
        isConnected={isConnected}
        latency={latency}
      />

      {/* Main Content - Split Layout */}
      <main className="flex-1 overflow-hidden">
        <SplitLayout
          leftPanel={<ArbLogTable />}
          rightPanel={<SwarmRing />}
          flashState={flashState}
          swarmState={swarmState}
        />
      </main>

      {/* Footer Status Bar */}
      <footer className="px-4 py-1.5 border-t border-border-dark bg-void-light flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-4 text-text-muted">
          <span>MODE: <span className="text-neon-green font-mono">SHADOW</span></span>
          <span>|</span>
          <span>RISK: <span className="text-gold font-mono">KELLY 0.25</span></span>
          <span>|</span>
          <span>GAS: <span className="text-text-secondary font-mono">~$0.02</span></span>
        </div>
        <div className="text-text-muted">
          {lastHeartbeat?.timestamp
            ? new Date(lastHeartbeat.timestamp).toLocaleTimeString()
            : '--:--:--'
          }
        </div>
      </footer>
    </div>
  )
}

export default App
