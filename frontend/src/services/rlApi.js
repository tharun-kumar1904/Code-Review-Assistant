import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const rlApi = axios.create({
  baseURL: `${API_BASE}/rl`,
  headers: { 'Content-Type': 'application/json' },
})

// Training
export const startTraining = (config) => rlApi.post('/train', config)
export const getTrainingStatus = () => rlApi.get('/train/status')

// Evaluation
export const evaluateAgent = () => rlApi.post('/evaluate')

// Review
export const reviewWithAgent = (data) => rlApi.post('/review', data)

// Metrics
export const getMetrics = () => rlApi.get('/metrics')

// Agent Info
export const getAgentInfo = () => rlApi.get('/agent/info')

// Human Feedback (RLHF)
export const submitFeedback = (taskId, feedback) =>
  rlApi.post('/feedback', { task_id: taskId, feedback })

// Baseline Comparison
export const getBaselineComparison = () => rlApi.get('/baseline')

export default rlApi
