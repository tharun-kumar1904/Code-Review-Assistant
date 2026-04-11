---
title: AI Code Review Assistant 🤖
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
pinned: true
---

<div align="center">
  <h1>🤖 Reinforcement Learning Code Review Assistant</h1>
  <p><h3><strong>A Meta PyTorch Hackathon Submission (Team Nexus)</strong></h3></p>
  <p>An enterprise-grade, autonomous pull request reviewer that doesn't just prompt a frontier model, but uses <strong>Reinforcement Learning in a Gymnasium Environment</strong> to dynamically improve its code review accuracy against a pristine gold-standard dataset.</p>

  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white" />
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" />
</div>

<br>

---

## 💡 What is this? (The Layman's Explanation)

Most AI coding assistants simply shove a block of code into a prompt and cross their fingers that the LLM guesses the right bug. 

Our **AI Code Review Assistant** is fundamentally different. It acts like a Senior Staff Engineer. We built a custom **Reinforcement Learning (RL) Pipeline** (compliant with the OpenEnv specification) that simulates a code review scenario. The Assistant looks at a piece of code, makes a judgment ("Approve" or "Request Changes" with specific line references), and is then rigorously graded against a hidden "gold standard" test dataset. 

Over time, this RL environment penalizes the AI for false positives (nitpicking about formatting) and heavily rewards it for finding complex architectural flaws like Race Conditions and SQL injections. It’s an AI that actively **learns how to review code better**.

## 🚀 How to Use the Dashboard

Our project consists of a sleek React dashboard that aggregates analytics and triggers reviews:

1. **Submit Code:** On the frontend interface, paste a GitHub Pull Request URL or raw diffs.
2. **Analysis Execution:** The background Celery workers will spin up the AI Agent, contextualize the codebase, and generate a structured review.
3. **Dashboard Consumption:** The UI visually overlays the AI's findings onto your code snippet (highlighting exact lines), categorizes bugs (Security, Performance, Logic), and assigns a confidence severity score. 
4. **Insights Tab:** Track the telemetry. You can view the historical accuracy, response times, and the exact "Reward Scores" the agent achieved during its RL training simulations.


---

## 🛠️ System Architecture

This project is not a simple script. It is a full-stack, distributed web application built for scale.

- **Frontend:** React + Vite + Recharts (for analytics).
- **Backend Core:** Asynchronous FastAPI backend.
- **Task Queue:** Redis and Celery for asynchronous background code-review processing.
- **Database:** PostgreSQL (with `pgvector` specifically enabled for future semantic embedding search).
- **Observability:** Prometheus metrics bound to Grafana dashboards.
- **RL Engine:** Self-contained Gymnasium environment simulating `OpenEnv` review rounds.

---

## ⚡ How To Run the Project (1-Click Deploy)

We have containerized the entire distributed stack via Docker Compose.

### **Option 1: Windows Easy Start**
We provided a script that brings up the database, cache, queues, backend, frontend, and telemetry layers automatically.
Simply double click or run:
```cmd
start-local.bat
```

### **Option 2: Mac / Linux Easy Start**
```bash
chmod +x start-local.sh
./start-local.sh
```

### **Manual Docker Start**
If you prefer to run it manually:
```bash
cd infrastructure
docker-compose up -d --build
```

Once booted, the ecosystem lives here:
*   **Main Web Dashboard:** [http://localhost:3000](http://localhost:3000)
*   **FastAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Grafana Telemetry:** [http://localhost:3001](http://localhost:3001)

---

## 🗄️ Database Access (PostgreSQL)

If judges or developers need to inspect the inner telemetry tables or webhooks logs, the local PostgreSQL database is exposed to the host machine.

Use any Database GUI (like **DBeaver**, **DataGrip**, or **pgAdmin**) and connect with:

*   **Host:** `localhost`
*   **Port:** `5432`
*   **Database Name:** `codereview`
*   **Username:** `codereview`
*   **Password:** `postgres@data123`

---

## 🌐 The Two Deployment Modes

1. **Hugging Face Space (Static Validator Mode):** Hugging Face hosts the `openenv.yaml` compliant CLI validator version of this project. It is stripped down to strictly interface with the automated `inference.py` script to prove our RL model works under extreme constraint sandbox guidelines.
2. **Local Distributed Mode (Full Experience):** Running the `.bat` / `.sh` scripts invokes `docker-compose`, launching our gorgeous Web UI, our Celery Queues, and our Grafana telemetry dashboards, which demonstrate the true "production-readiness" of this tool.

---
<div align="center">
  <i>Built with ❤️ for the Meta PyTorch Hackathon</i>
</div>
