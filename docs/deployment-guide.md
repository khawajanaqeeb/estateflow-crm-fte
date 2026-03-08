# EstateFlow Customer Success FTE — Deployment Guide

## Overview

This guide covers deploying the EstateFlow Digital FTE (Full-Time Equivalent) AI agent
to production. The system runs on Kubernetes and handles customer support 24/7 across
three channels: Web Form, Gmail, and WhatsApp.

**Architecture:**
```
Internet → Ingress (nginx + TLS) → FastAPI (3–20 pods)
                                         ↓
                                    Kafka topics
                                         ↓
                               Message Processor Worker (3–30 pods)
                                         ↓
                              OpenAI Agents SDK (gpt-4o)
                                         ↓
                              PostgreSQL 16 + pgvector
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24+ | Container builds |
| kubectl | 1.29+ | Kubernetes management |
| Helm | 3.14+ | Chart deployments (optional) |
| Python | 3.12+ | Local development |
| psql | 16+ | Database inspection |

### Required Credentials

Collect these before deploying:

- `OPENAI_API_KEY` — OpenAI platform API key with GPT-4o access
- `POSTGRES_PASSWORD` — Choose a strong password (min 24 chars)
- `GMAIL_CREDENTIALS` — Base64-encoded `credentials.json` from Google Cloud Console
- `GMAIL_TOKEN` — Base64-encoded `token.json` after OAuth consent
- `TWILIO_ACCOUNT_SID` — Twilio console → Account Info
- `TWILIO_AUTH_TOKEN` — Twilio console → Account Info
- `TWILIO_WHATSAPP_FROM` — Format: `whatsapp:+14155238886` (sandbox number)

---

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/khawajanaqeeb/estateflow-crm-fte.git
cd estateflow-crm-fte
cp .env.example .env        # edit with your credentials
```

### 2. Required `.env` variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# PostgreSQL (docker-compose uses these automatically)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=fte_db
POSTGRES_USER=fte_user
POSTGRES_PASSWORD=your_password

# Kafka (docker-compose sets kafka:29092 automatically)
KAFKA_BOOTSTRAP_SERVERS=kafka:29092

# Gmail (optional for local dev)
GMAIL_CREDENTIALS_JSON={"installed":{...}}
GMAIL_TOKEN_JSON={"token":"..."}
GMAIL_SUPPORT_EMAIL=support@estateflow.io

# Twilio / WhatsApp (optional for local dev)
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Feature flags
CHANNEL_GMAIL_ENABLED=true
CHANNEL_WHATSAPP_ENABLED=true
CHANNEL_WEB_FORM_ENABLED=true
MAX_RESPONSE_LENGTH=1500
```

### 3. Start the full stack

```bash
docker compose up
```

Services started:
- PostgreSQL (port 5432) — schema auto-applied from `production/database/schema.sql`
- Zookeeper + Kafka (port 9092)
- Kafka UI (port 8080) — browse topics at http://localhost:8080
- FastAPI (port 8000) — API at http://localhost:8000
- Worker — Kafka consumer loop

### 4. Verify health

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","channels":{"web_form":"active",...}}
```

### 5. Test a web form submission

```bash
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sarah Morrison",
    "email": "sarah@example.com",
    "subject": "Cannot sync Gmail contacts",
    "category": "technical",
    "message": "Getting authentication errors when trying to sync Gmail contacts to EstateFlow."
  }'
```

---

## Production Deployment (Kubernetes)

### 1. Build and push the Docker image

```bash
# Replace with your registry
docker build -t your-registry/estateflow-fte:v1.0.0 .
docker push your-registry/estateflow-fte:v1.0.0
```

Update the image tag in:
- `production/k8s/deployment-api.yaml`
- `production/k8s/deployment-worker.yaml`

### 2. Create the namespace

```bash
kubectl apply -f production/k8s/namespace.yaml
```

### 3. Create secrets

**Never commit secrets to git.** Create them via kubectl:

```bash
kubectl create secret generic fte-secrets \
  --namespace customer-success-fte \
  --from-literal=OPENAI_API_KEY="sk-your-key" \
  --from-literal=POSTGRES_PASSWORD="your-db-password" \
  --from-literal=TWILIO_ACCOUNT_SID="ACxxx" \
  --from-literal=TWILIO_AUTH_TOKEN="your-token" \
  --from-literal=TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"

# Gmail credentials (base64-encoded JSON files)
kubectl create secret generic fte-gmail-secrets \
  --namespace customer-success-fte \
  --from-file=credentials.json=./gmail-credentials.json \
  --from-file=token.json=./gmail-token.json
```

### 4. Apply ConfigMap

```bash
kubectl apply -f production/k8s/configmap.yaml
```

Edit `configmap.yaml` first to set your Kafka bootstrap servers and PostgreSQL host.

### 5. Deploy PostgreSQL

For production, use a managed PostgreSQL service (AWS RDS, Google Cloud SQL, or
Azure Database for PostgreSQL) with pgvector extension enabled.

If using self-hosted PostgreSQL on Kubernetes:
```bash
# Apply schema after DB is ready
kubectl run schema-init --rm -i --restart=Never \
  --namespace customer-success-fte \
  --image=postgres:16 \
  -- psql "postgresql://fte_user:password@postgres-host/fte_db" \
     -f /schema.sql
```

### 6. Deploy Kafka

For production, use Confluent Cloud or Amazon MSK. Update `KAFKA_BOOTSTRAP_SERVERS`
in the ConfigMap to point to your managed Kafka cluster.

### 7. Deploy the application

```bash
kubectl apply -f production/k8s/deployment-api.yaml
kubectl apply -f production/k8s/deployment-worker.yaml
kubectl apply -f production/k8s/service.yaml
kubectl apply -f production/k8s/hpa.yaml
kubectl apply -f production/k8s/ingress.yaml
```

### 8. Verify deployment

```bash
# Check all pods are Running
kubectl get pods -n customer-success-fte

# Check HPA status
kubectl get hpa -n customer-success-fte

# Check API logs
kubectl logs -n customer-success-fte -l app=fte-api --tail=50

# Check worker logs
kubectl logs -n customer-success-fte -l app=fte-worker --tail=50

# Hit the health endpoint
kubectl port-forward -n customer-success-fte svc/fte-api 8000:80
curl http://localhost:8000/health
```

---

## Webhook Configuration

### Gmail Push Notifications

1. Go to Google Cloud Console → Pub/Sub → Topics
2. Create topic: `estateflow-gmail-notifications`
3. Create subscription: push to `https://support-api.estateflow.io/webhooks/gmail`
4. In Gmail API, call `users.watch`:
   ```python
   service.users().watch(userId='me', body={
       'topicName': 'projects/YOUR_PROJECT/topics/estateflow-gmail-notifications',
       'labelIds': ['INBOX']
   }).execute()
   ```
5. Watch expires every 7 days — set up a Cloud Scheduler job to renew.

### Twilio WhatsApp

1. Go to Twilio Console → Messaging → Senders → WhatsApp Senders
2. Set Webhook URL: `https://support-api.estateflow.io/webhooks/whatsapp`
3. Set Status Callback URL: `https://support-api.estateflow.io/webhooks/whatsapp/status`
4. Method: HTTP POST

---

## Web Form Integration

Embed the support form in any webpage:

```html
<!-- Option 1: React component (requires React 18+) -->
<div id="support-form"></div>
<script src="https://your-cdn/SupportForm.js"></script>
<script>
  ReactDOM.render(
    React.createElement(SupportForm, {
      apiEndpoint: "https://support-api.estateflow.io"
    }),
    document.getElementById("support-form")
  );
</script>
```

The form:
- Validates inputs client-side (mirrors server validation)
- Shows success screen with ticket ID after submission
- Allows customers to look up ticket status
- Requires no external CSS frameworks

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health + channel status |
| POST | `/support/submit` | Web form ticket submission |
| GET | `/support/ticket/{id}` | Ticket status by UUID |
| POST | `/webhooks/gmail` | Gmail Pub/Sub push handler |
| POST | `/webhooks/whatsapp` | Twilio WhatsApp incoming |
| POST | `/webhooks/whatsapp/status` | Twilio delivery status callback |
| GET | `/customers/lookup` | Find customer by email or phone |
| GET | `/conversations/{id}` | Conversation history by UUID |
| GET | `/metrics/channels` | Channel performance metrics |

### POST `/support/submit` — Request Body

```json
{
  "name":     "string (2–200 chars, required)",
  "email":    "string (valid email, required)",
  "subject":  "string (5–300 chars, required)",
  "category": "general | technical | billing | bug_report | feedback",
  "priority": "low | medium | high (default: medium)",
  "message":  "string (10–5000 chars, required)"
}
```

### GET `/metrics/channels` — Response

```json
{
  "web_form": {
    "total_conversations": 1247,
    "escalations": 89,
    "escalation_rate": 0.071,
    "avg_response_time_ms": 1840
  },
  "gmail": { ... },
  "whatsapp": { ... }
}
```

---

## Scaling Guidelines

| Metric | Action |
|--------|--------|
| CPU > 70% | HPA adds pods (up to 20 API, 30 worker) |
| Memory > 80% | HPA adds pods |
| Kafka consumer lag > 1000 | Manually scale workers: `kubectl scale deploy fte-worker --replicas=10` |
| DB connections > 80% | Increase `POSTGRES_MAX_CONNECTIONS` or add read replicas |

---

## Monitoring

### Key metrics to watch

```bash
# Channel metrics via API
curl https://support-api.estateflow.io/metrics/channels

# Kafka consumer lag (via Kafka UI or CLI)
kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group fte-worker

# PostgreSQL active connections
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

### Alerting thresholds

| Alert | Threshold | Action |
|-------|-----------|--------|
| P95 latency | > 3 seconds | Scale API pods |
| Error rate | > 0.1% | Check logs, possible DB or Kafka issue |
| Kafka lag | > 5000 messages | Scale worker pods |
| Escalation rate | > 25% | Review agent knowledge base |

---

## Running Tests

```bash
# E2E tests (requires API running)
pytest production/tests/test_multichannel_e2e.py -v

# E2E tests against live server
API_BASE_URL=http://localhost:8000 pytest production/tests/test_multichannel_e2e.py -v

# Load test (requires locust)
locust -f production/tests/load_test.py \
  --host http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --headless
```

---

## Upgrading

```bash
# Build new image
docker build -t your-registry/estateflow-fte:v1.1.0 .
docker push your-registry/estateflow-fte:v1.1.0

# Rolling update (zero downtime)
kubectl set image deployment/fte-api \
  api=your-registry/estateflow-fte:v1.1.0 \
  -n customer-success-fte

kubectl set image deployment/fte-worker \
  worker=your-registry/estateflow-fte:v1.1.0 \
  -n customer-success-fte

# Monitor rollout
kubectl rollout status deployment/fte-api -n customer-success-fte
```

---

## Rollback

```bash
kubectl rollout undo deployment/fte-api -n customer-success-fte
kubectl rollout undo deployment/fte-worker -n customer-success-fte
```
