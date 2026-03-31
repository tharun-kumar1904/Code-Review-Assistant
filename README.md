# 🤖 AI Code Review Assistant

**Intelligent GitHub Pull Request Reviewer powered by Large Language Models**

An AI-powered system that automatically analyzes GitHub pull requests and provides intelligent feedback including bug detection, security vulnerability scanning, performance suggestions, and code quality improvements — going beyond simple linting by understanding context with LLMs.

---

## 🏗️ System Architecture

```
┌─────────────┐         ┌──────────────────────────────────────────────────┐
│   GitHub     │         │                  Backend Service                 │
│  Repository  │────────▶│  ┌─────────────┐    ┌──────────────────────┐    │
│              │ Webhook │  │   FastAPI    │    │   Analysis Pipeline  │    │
│  PR opened/  │         │  │   Server     │    │                      │    │
│  updated     │         │  │  ┌────────┐  │    │  Static Analyzer     │    │
└─────────────┘         │  │  │Webhook │  │    │  Security Scanner    │    │
                        │  │  │Handler │──┼───▶│  RAG Context Engine  │    │
                        │  │  └────────┘  │    │  LLM Code Reviewer   │    │
                        │  │  ┌────────┐  │    │  Quality Scorer      │    │
                        │  │  │REST API│  │    └──────────┬───────────┘    │
                        │  │  └────────┘  │               │                │
                        │  └──────┬───────┘               │                │
                        └─────────┼───────────────────────┼────────────────┘
                                  │                       │
                    ┌─────────────┼───────────────────────┼──────────┐
                    │             ▼                       ▼          │
                    │  ┌──────────────┐    ┌──────────────────────┐  │
                    │  │    Redis     │    │   PostgreSQL         │  │
                    │  │  • Queue     │    │   + pgvector         │  │
                    │  │  • Cache     │    │   • Reviews          │  │
                    │  └──────┬───────┘    │   • Security Issues  │  │
                    │         │            │   • Code Metrics     │  │
                    │         ▼            │   • Embeddings (RAG) │  │
                    │  ┌──────────────┐    └──────────────────────┘  │
                    │  │   Celery     │                              │
                    │  │   Workers    │         Data Layer           │
                    │  └──────────────┘                              │
                    └───────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼──────────────────────┐
                    │             ▼                      │
                    │  ┌──────────────┐  ┌────────────┐  │
                    │  │   React      │  │  Grafana   │  │
                    │  │  Dashboard   │  │  Metrics   │  │
                    │  └──────────────┘  └────────────┘  │
                    │           Frontend & Monitoring     │
                    └────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔗 **GitHub Integration** | Webhook auto-trigger on PR open/update, inline review comments |
| 🤖 **LLM Code Analysis** | Multi-provider support (GPT-4o, Claude, Gemini) with structured JSON output |
| 🔒 **Security Scanning** | SQL injection, XSS, hardcoded secrets, insecure functions (CWE/OWASP mapped) |
| 📊 **Static Analysis** | Cyclomatic complexity, maintainability index, duplication detection, LOC metrics |
| 🧠 **RAG Context Engine** | Repository code embedded in pgvector, relevant context retrieved for each review |
| ⚡ **Async Processing** | Celery workers with Redis queue for non-blocking analysis |
| 📈 **Observability** | Prometheus metrics + Grafana dashboards (latency, error rate, queue depth) |
| 💾 **Redis Caching** | GitHub API responses, repo metadata, and analysis results cached with TTL |
| 🎨 **Premium Dashboard** | Dark-themed React UI with charts, severity badges, and expandable review cards |
| 🐳 **Docker Deployment** | 7-service docker-compose (backend, frontend, DB, Redis, workers, Prometheus, Grafana) |
| 🔄 **CI/CD Pipeline** | GitHub Actions: lint, test, build, push Docker images |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy (async), Pydantic |
| **Workers** | Celery, Redis |
| **Database** | PostgreSQL 16 + pgvector |
| **AI/ML** | OpenAI GPT-4o / Claude / Gemini, RAG with embeddings |
| **Frontend** | React 18, Vite, Recharts, Lucide Icons |
| **Infrastructure** | Docker, Nginx, Prometheus, Grafana |
| **CI/CD** | GitHub Actions |

---

## 📁 Project Structure

```
ai-code-review-assistant/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Pydantic settings
│   ├── database.py                # Async SQLAlchemy + pgvector
│   ├── models.py                  # ORM models (7 tables)
│   ├── schemas.py                 # Request/response schemas
│   ├── routers/
│   │   ├── analysis.py            # POST /analyze-pr, GET /review-results
│   │   ├── insights.py            # GET /repository-insights, /security-issues
│   │   └── webhooks.py            # POST /webhook/github
│   ├── services/
│   │   ├── analysis_engine.py     # 8-step analysis pipeline orchestrator
│   │   ├── github_service.py      # GitHub API client (cached)
│   │   ├── llm_service.py         # Multi-provider LLM integration
│   │   ├── static_analyzer.py     # Complexity, duplication, metrics
│   │   ├── security_scanner.py    # Pattern-based vulnerability detection
│   │   ├── rag_service.py         # Embedding + vector search
│   │   └── cache_service.py       # Redis caching layer
│   ├── Dockerfile
│   └── requirements.txt
├── workers/
│   ├── celery_app.py              # Celery configuration
│   ├── tasks.py                   # Async analysis task
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Root + routing
│   │   ├── index.css              # Dark theme design system
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx      # Stats, charts, recent reviews
│   │   │   ├── Reviews.jsx        # PR analysis list + details
│   │   │   ├── Security.jsx       # Vulnerability table + charts
│   │   │   └── Insights.jsx       # Complexity, radar, LOC charts
│   │   ├── components/
│   │   │   ├── Sidebar.jsx        # Navigation sidebar
│   │   │   ├── StatCard.jsx       # Metric card component
│   │   │   └── ReviewCard.jsx     # Expandable review card
│   │   └── services/api.js        # Axios API client
│   ├── Dockerfile
│   └── package.json
├── infrastructure/
│   ├── docker-compose.yml         # 7-service stack
│   ├── nginx.conf                 # SPA + API proxy
│   ├── prometheus.yml             # Metrics scrape config
│   └── grafana/dashboard.json     # Pre-built monitoring dashboard
├── .github/workflows/ci.yml       # CI/CD pipeline
├── .env.example                   # Environment template
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- GitHub Personal Access Token
- LLM API key (OpenAI / Anthropic / Google)

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/ai-code-review-assistant.git
cd ai-code-review-assistant
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker
```bash
cd infrastructure
docker-compose up -d
```

### 3. Access
| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **Prometheus** | http://localhost:9090 |
| **Grafana** | http://localhost:3001 (admin / codereview) |

### 4. Analyze a PR
```bash
curl -X POST http://localhost:8000/api/analyze-pr \
  -H "Content-Type: application/json" \
  -d '{"repo_owner": "octocat", "repo_name": "hello-world", "pr_number": 1}'
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze-pr` | Trigger PR analysis (async via Celery) |
| `GET` | `/api/review-results` | List reviews (paginated, filterable) |
| `GET` | `/api/review-results/{id}` | Detailed review with all comments |
| `GET` | `/api/repository-insights/{owner}/{repo}` | Aggregated quality metrics |
| `GET` | `/api/security-issues` | Security vulnerabilities list |
| `POST` | `/api/webhook/github` | GitHub webhook handler |
| `GET` | `/health` | Health check |

---

## 🧠 AI Analysis Pipeline

The analysis engine runs an **8-step pipeline** for each PR:

1. **Fetch** — Pull PR diff and changed files from GitHub API
2. **Static Analysis** — Compute complexity (radon), maintainability, duplication, LOC
3. **Security Scan** — Pattern-based detection (SQL injection, XSS, secrets, etc.)
4. **RAG Retrieval** — Embed query → cosine search pgvector → retrieve relevant repo context
5. **LLM Analysis** — Send diff + context to LLM with structured prompt → get JSON issues
6. **Aggregation** — Merge all issues, deduplicate, sort by severity
7. **Scoring** — Compute quality score (0-100) based on severity-weighted deductions
8. **Reporting** — Store in PostgreSQL, post inline comments on GitHub PR

---

## 🔒 Security Detection

The scanner detects **8 vulnerability categories** with CWE/OWASP mapping:

| Category | CWE | Example |
|----------|-----|---------|
| SQL Injection | CWE-89 | `f"SELECT * FROM users WHERE id={user_id}"` |
| XSS | CWE-79 | `dangerouslySetInnerHTML={{__html: userInput}}` |
| Hardcoded Secrets | CWE-798 | `API_KEY = "sk-abc123..."` |
| Insecure Functions | CWE-78 | `eval(user_input)` |
| Path Traversal | CWE-22 | `open(base_dir + user_filename)` |
| Insecure HTTP | CWE-319 | `requests.get("http://api.example.com")` |
| Weak Crypto | CWE-327 | `hashlib.md5(password)` |
| Missing Error Handling | CWE-390 | `except: pass` |

---

## 📊 Observability

| Metric | Source |
|--------|--------|
| API request rate & latency | Prometheus FastAPI Instrumentator |
| Error rate (5xx) | Prometheus |
| Worker throughput & queue depth | Celery + Redis |
| LLM response time | Custom histogram |
| System health | Grafana dashboards |

---

## 🎤 Interview Discussion Guide (25-30 min)

### System Design (5 min)
- Event-driven architecture: GitHub webhook → Redis queue → Celery worker → DB → GitHub comments
- Decoupled services: API server handles requests, workers handle heavy analysis
- Scaling strategy: horizontal worker scaling, Redis pub/sub, DB read replicas

### AI Pipeline (8 min)
- RAG architecture: embed repo code → pgvector store → cosine similarity retrieval
- Multi-provider LLM integration with structured prompt engineering
- Output parsing: force JSON schema from LLM, fallback regex extraction
- Prompt design: system prompt for expertise, user prompt with diff + context

### Backend Design (5 min)
- Async SQLAlchemy with connection pooling and health checks
- Celery task retry logic with exponential backoff
- Redis caching layer with TTL-based invalidation
- Webhook signature validation (HMAC-SHA256)

### Security Analysis (4 min)
- Pattern-based detection with regex for 8 vulnerability categories
- CWE/OWASP classification for industry-standard mapping
- Combined human-readable explanation + automated remediation

### Scalability (4 min)
- Queue-based decoupling allows independent scaling of API and workers
- Redis caching reduces GitHub API rate limit pressure
- pgvector enables efficient similarity search without external vector DB
- Docker Compose → Kubernetes migration path

### DevOps (4 min)
- CI/CD: GitHub Actions with Postgres+Redis service containers
- Multi-stage Docker builds for minimal image sizes
- Prometheus + Grafana for production monitoring
- Infrastructure as Code with docker-compose

---

## 📝 License

MIT License — built for educational and portfolio purposes.
