import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Reviews from './pages/Reviews'
import Security from './pages/Security'
import Insights from './pages/Insights'
import RLTraining from './pages/RLTraining'
import AgentPerformance from './pages/AgentPerformance'

function App() {
  return (
    <Router>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="/security" element={<Security />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/rl-training" element={<RLTraining />} />
            <Route path="/agent-performance" element={<AgentPerformance />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
