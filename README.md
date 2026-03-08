# EstateFlow Customer Success FTE

**A production-grade Digital FTE (Full-Time Equivalent) AI agent** that handles customer
support 24/7 across Web Form, Gmail, and WhatsApp — built for The CRM Digital FTE Factory
Hackathon 5.

## What it does

- Answers customer questions using product documentation (via pgvector semantic search)
- Creates and tracks support tickets with full conversation history
- Routes escalations to billing, security, legal, or sales teams automatically
- Maintains cross-channel customer identity (same customer via email and WhatsApp = one record)
- Scales from 3 to 30 pods automatically based on load

## Architecture

```
Web Form → POST /support/submit ─────────┐
Gmail   → POST /webhooks/gmail  ─────────┤─→ Kafka → Worker → OpenAI gpt-4o
WhatsApp→ POST /webhooks/whatsapp ────────┘                        ↓
                                                            PostgreSQL 16
                                                            + pgvector
```

| Layer | Technology |
|-------|-----------|
| Agent | OpenAI Agents SDK (`gpt-4o`) |
| API | FastAPI + uvicorn |
| Database / CRM | PostgreSQL 16 + pgvector |
| Event streaming | Apache Kafka (aiokafka) |
| Email | Gmail API + Google Pub/Sub |
| WhatsApp | Twilio |
| Orchestration | Kubernetes + HPA |

## Quick Start

```bash
# Clone
git clone https://github.com/khawajanaqeeb/estateflow-crm-fte.git
cd estateflow-crm-fte

# Configure
cp .env.example .env     # add OPENAI_API_KEY and other credentials

# Run everything
docker compose up

# Health check
curl http://localhost:8000/health

# Submit a test ticket
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{"name":"Sarah Morrison","email":"sarah@test.com","subject":"Gmail sync not working","category":"technical","message":"Getting authentication errors when syncing Gmail contacts."}'
```

## Project Structure

```
production/
├── agent/
│   ├── customer_success_agent.py   # OpenAI Agent definition
│   └── tools.py                    # 9 @function_tool implementations
├── api/
│   └── main.py                     # FastAPI app (9 endpoints)
├── channels/
│   ├── web_form_handler.py         # Web form router + Pydantic validation
│   ├── gmail_handler.py            # Gmail API + Pub/Sub handler
│   └── whatsapp_handler.py         # Twilio WhatsApp handler
├── database/
│   ├── schema.sql                  # PostgreSQL schema (7 tables + pgvector)
│   └── queries.py                  # All asyncpg query functions
├── workers/
│   └── message_processor.py        # Kafka consumer → agent pipeline
├── web-form/
│   ├── SupportForm.jsx             # Embeddable React support form
│   └── TicketStatus.jsx            # Ticket lookup component
├── k8s/                            # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment-api.yaml         # 3-20 pod HPA
│   ├── deployment-worker.yaml      # 3-30 pod HPA
│   ├── service.yaml
│   ├── ingress.yaml                # nginx + TLS
│   └── hpa.yaml
└── tests/
    ├── test_multichannel_e2e.py    # 19 pytest async E2E tests
    └── load_test.py                # Locust load test (P95 < 3s target)

docs/
├── deployment-guide.md             # Full deployment documentation
└── runbook.md                      # Incident response playbooks
```

## Running Tests

```bash
# E2E tests (ASGI mode - no server needed)
pytest production/tests/test_multichannel_e2e.py -v

# Load test
locust -f production/tests/load_test.py --host http://localhost:8000
```

## Performance Targets

| Metric | Target |
|--------|--------|
| P95 latency | < 3 seconds |
| Uptime | > 99.9% |
| Escalation rate | < 25% |
| Web form submissions | 100+ / 24 hours |

## Documentation

- [Deployment Guide](docs/deployment-guide.md) - setup, Kubernetes, webhooks, API reference
- [Runbook](docs/runbook.md) - incident response playbooks (8 scenarios)
- [Hackathon Requirements](docs/hackathon5-requirement.md) - original spec

## Agent Maturity Model Progression

**Phase 1 - Incubation** (complete): Prototype agent with in-memory tools, discovery log,
multi-channel pattern identification.

**Phase 2 - Specialization** (complete): Production system with real DB, Kafka event
streaming, multi-channel webhooks, Kubernetes deployment, pgvector knowledge search.

**Phase 3 - 24/7 Readiness** (complete): E2E test suite (19 tests), Locust load tests,
deployment documentation, incident runbook.
