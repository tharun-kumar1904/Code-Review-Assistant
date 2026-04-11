import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

export const analyzePR = (data) => api.post('/analyze-pr', data)
export const getReviewResults = (params) => api.get('/review-results', { params })
export const getReviewDetail = (id) => api.get(`/review-results/${id}`)
export const getRepositoryInsights = (owner, repo) => api.get(`/repository-insights/${owner}/${repo}`)
export const getSecurityIssues = (params) => api.get('/security-issues', { params })

export default api
