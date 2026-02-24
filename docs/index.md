# Retail Agent Swarm — Wiki

Welcome to the documentation wiki for the Retail Agent Swarm project.

## Quick Links

- [Specification](SPEC.md) — Requirements, data models, API contracts, acceptance criteria
- [Architecture](ARCHITECTURE.md) — System components, parallel execution, thread pool design
- [Design](DESIGN.md) — Design decisions, agent patterns, guardrail rationale, data flow

## What Is This?

A multi-agent AI system that simulates a full retail pharmacy order pipeline. When a customer places an order, **9 specialized agents** coordinate in parallel to check inventory, logistics, distribution, suppliers, prescriptions, and clinic data — then deliver a personalized, safety-checked response.

## Getting Started

```bash
git clone <repo-url>
cd retail-agent-swarm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
uvicorn app:app --port 8000
# In another terminal:
python smoke_test.py
```

## Project Status

| Component | Status |
|-----------|--------|
| Agent Swarm (7 domain agents) | ✅ Complete |
| Orchestrator (parallel execution) | ✅ Complete |
| Customer Conversation Agent (guardrails) | ✅ Complete |
| FastAPI REST API | ✅ Complete |
| Simulated Data Layer | ✅ Complete |
| Smoke Test | ✅ Complete |
| Documentation (Spec/Arch/Design) | ✅ Complete |
| Unit Tests | 🔲 Planned |
| Guardrail Test Suite | 🔲 Planned |
| Production Persistence | 🔲 Planned |
