# EstateFlow Customer Success FTE — Incident Runbook

## Severity Levels

| Level | Response Time | Examples |
|-------|--------------|---------|
| SEV-1 | < 15 min | API completely down, all channels failing |
| SEV-2 | < 1 hour | One channel down, high error rate, DB unavailable |
| SEV-3 | < 4 hours | Elevated latency, single webhook failing |
| SEV-4 | Next business day | Cosmetic issues, metrics anomalies |

---

## Quick Diagnostics

Run this first for any incident:

```bash
# 1. Health check
curl https://support-api.estateflow.io/health

# 2. Pod status
kubectl get pods -n customer-success-fte

# 3. Recent errors
kubectl logs -n customer-success-fte -l app=fte-api --tail=100 | grep -i "error\|exception"
kubectl logs -n customer-success-fte -l app=fte-worker --tail=100 | grep -i "error\|exception"

# 4. HPA status
kubectl get hpa -n customer-success-fte

# 5. Channel metrics
curl https://support-api.estateflow.io/metrics/channels
```

---

## Incident Playbooks

---

### INC-001: API Completely Unresponsive (SEV-1)

**Symptoms:** `/health` returns 5xx or times out. All channels down.

**Steps:**

1. **Check pods:**
   ```bash
   kubectl get pods -n customer-success-fte -l app=fte-api
   ```
   - If `0/N Running`: proceed to step 2
   - If pods are `Running` but health fails: check step 4

2. **Check pod events:**
   ```bash
   kubectl describe pods -n customer-success-fte -l app=fte-api | grep -A10 Events
   ```

3. **Check common causes:**
   ```bash
   # OOMKilled?
   kubectl get events -n customer-success-fte --sort-by='.lastTimestamp' | tail -20

   # ImagePullBackOff?
   kubectl get pods -n customer-success-fte -o wide
   ```

4. **Check DB connectivity:**
   ```bash
   kubectl exec -n customer-success-fte -it $(kubectl get pod -n customer-success-fte -l app=fte-api -o name | head -1) \
     -- python -c "import asyncpg, asyncio; asyncio.run(asyncpg.connect(host='postgres-host'))"
   ```

5. **Check Kafka connectivity:**
   ```bash
   kubectl exec -n customer-success-fte -it $(kubectl get pod -n customer-success-fte -l app=fte-api -o name | head -1) \
     -- python -c "from aiokafka import AIOKafkaProducer; print('Kafka OK')"
   ```

6. **Emergency restart:**
   ```bash
   kubectl rollout restart deployment/fte-api -n customer-success-fte
   kubectl rollout status deployment/fte-api -n customer-success-fte
   ```

7. **If still failing — rollback:**
   ```bash
   kubectl rollout undo deployment/fte-api -n customer-success-fte
   ```

**Resolution time target:** < 15 minutes

---

### INC-002: High Latency (P95 > 3 seconds) (SEV-2)

**Symptoms:** Slow responses on `/support/submit`, ticket status slow.

**Steps:**

1. **Check current RPS vs pod count:**
   ```bash
   kubectl get hpa -n customer-success-fte
   # Is REPLICAS at max (20)?
   ```

2. **Manually scale if HPA is slow to respond:**
   ```bash
   kubectl scale deployment fte-api --replicas=15 -n customer-success-fte
   ```

3. **Check DB slow queries:**
   ```bash
   psql $DATABASE_URL -c "
     SELECT query, mean_exec_time, calls
     FROM pg_stat_statements
     ORDER BY mean_exec_time DESC
     LIMIT 10;
   "
   ```

4. **Check OpenAI API latency:**
   ```bash
   # Look for timeout patterns in logs
   kubectl logs -n customer-success-fte -l app=fte-worker --tail=200 | grep "openai\|timeout\|429"
   ```
   - If OpenAI rate limited (429): worker already has retry logic; latency will self-resolve
   - If OpenAI API is degraded: check https://status.openai.com

5. **Check Kafka consumer lag:**
   ```bash
   # Via Kafka UI at http://kafka-ui:8080
   # Or CLI:
   kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
     --describe --group fte-worker
   ```
   - If lag > 5000: scale workers `kubectl scale deployment fte-worker --replicas=15`

6. **Check pgvector index:**
   ```bash
   psql $DATABASE_URL -c "
     SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
     FROM pg_stat_user_indexes
     WHERE indexname = 'idx_knowledge_embedding';
   "
   ```
   - Very low `idx_scan` with high query count indicates missing index usage; REINDEX.

---

### INC-003: Web Form Submissions Failing (SEV-2)

**Symptoms:** `/support/submit` returns 500. Customers cannot submit tickets.

**Steps:**

1. **Test manually:**
   ```bash
   curl -X POST https://support-api.estateflow.io/support/submit \
     -H "Content-Type: application/json" \
     -d '{"name":"Test","email":"test@example.com","subject":"Test subject","category":"general","message":"Test message body here."}'
   ```

2. **Check API logs for the error:**
   ```bash
   kubectl logs -n customer-success-fte -l app=fte-api --tail=50 | grep "POST /support/submit" -A5
   ```

3. **Check Kafka producer:**
   - If "Kafka topic not found": topic auto-creation should handle this; check `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true`
   - If "Connection refused": check Kafka pod health

4. **Bypass Kafka (emergency):**
   If Kafka is down, the web form can process tickets synchronously. Redeploy with
   `KAFKA_BOOTSTRAP_SERVERS` pointing to a backup cluster or enable sync mode:
   ```bash
   kubectl set env deployment/fte-api KAFKA_BYPASS_MODE=true -n customer-success-fte
   ```

5. **Check DB write access:**
   ```bash
   psql $DATABASE_URL -c "INSERT INTO tickets (id, status) VALUES (gen_random_uuid(), 'open') RETURNING id;"
   ```

---

### INC-004: Gmail Webhook Not Processing (SEV-3)

**Symptoms:** Customer emails not generating tickets. Gmail channel shows 0 in metrics.

**Steps:**

1. **Verify webhook is reachable:**
   ```bash
   curl -X POST https://support-api.estateflow.io/webhooks/gmail \
     -H "Content-Type: application/json" \
     -d '{"message":{"data":"eyJoaXN0b3J5SWQiOiIxMjM0NSJ9","messageId":"test"},"subscription":"test"}'
   # Should return 200
   ```

2. **Check Gmail watch expiry:**
   Gmail push notifications expire every 7 days. Renew:
   ```bash
   kubectl exec -n customer-success-fte \
     $(kubectl get pod -n customer-success-fte -l app=fte-api -o name | head -1) \
     -- python -c "
   from production.channels.gmail_handler import GmailHandler
   import asyncio
   asyncio.run(GmailHandler().setup_push_notifications())
   print('Watch renewed')
   "
   ```

3. **Check Gmail credentials:**
   ```bash
   kubectl get secret fte-gmail-secrets -n customer-success-fte -o yaml
   # Ensure credentials.json and token.json are present and non-empty
   ```

4. **Check Pub/Sub subscription:**
   - Google Cloud Console → Pub/Sub → Subscriptions
   - Verify `estateflow-gmail-notifications` subscription push URL matches
   - Check subscription backlog (should be 0 if processing normally)

5. **Force manual history pull:**
   ```bash
   # Get latest historyId from Gmail API and trigger manually
   curl -X POST https://support-api.estateflow.io/webhooks/gmail \
     -H "Content-Type: application/json" \
     -d '{"message":{"data":"<base64-encoded-historyId>","messageId":"manual"}}'
   ```

---

### INC-005: WhatsApp Webhook Failing (SEV-3)

**Symptoms:** WhatsApp messages not generating tickets. Returns 403 or 500.

**Steps:**

1. **Check signature validation:**
   ```bash
   kubectl logs -n customer-success-fte -l app=fte-api --tail=50 | grep "whatsapp\|twilio\|403"
   ```
   - 403 on every request: `TWILIO_AUTH_TOKEN` may be wrong
   - Update secret: `kubectl create secret generic fte-secrets --from-literal=TWILIO_AUTH_TOKEN=new-token -n customer-success-fte --dry-run=client -o yaml | kubectl apply -f -`

2. **Test without signature (dev only):**
   ```bash
   # Temporarily clear TWILIO_AUTH_TOKEN to skip validation
   kubectl set env deployment/fte-api TWILIO_AUTH_TOKEN="" -n customer-success-fte
   ```

3. **Check Twilio webhook URL:**
   - Twilio Console → Messaging → Senders → WhatsApp
   - Webhook URL must be `https://support-api.estateflow.io/webhooks/whatsapp`
   - Must be HTTPS with valid TLS cert

4. **Verify TLS certificate:**
   ```bash
   kubectl get certificate -n customer-success-fte
   kubectl describe certificate fte-tls -n customer-success-fte
   ```
   - If cert is expired: cert-manager should auto-renew; check `kubectl get certificaterequest -n customer-success-fte`

5. **Test Twilio connectivity from worker:**
   ```bash
   kubectl exec -n customer-success-fte \
     $(kubectl get pod -n customer-success-fte -l app=fte-worker -o name | head -1) \
     -- python -c "
   from twilio.rest import Client
   import os
   c = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
   print('Account:', c.api.accounts(os.environ['TWILIO_ACCOUNT_SID']).fetch().friendly_name)
   "
   ```

---

### INC-006: Database Connection Pool Exhausted (SEV-2)

**Symptoms:** 500 errors with "too many connections" or "connection pool exhausted".

**Steps:**

1. **Check active connections:**
   ```bash
   psql $DATABASE_URL -c "
     SELECT count(*), state
     FROM pg_stat_activity
     WHERE datname = 'fte_db'
     GROUP BY state;
   "
   ```

2. **Identify long-running queries:**
   ```bash
   psql $DATABASE_URL -c "
     SELECT pid, now() - query_start AS duration, query
     FROM pg_stat_activity
     WHERE datname = 'fte_db' AND state = 'active' AND query_start < now() - interval '30 seconds'
     ORDER BY duration DESC;
   "
   ```

3. **Kill long-running connections (only if blocking):**
   ```bash
   psql $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND query_start < now() - interval '5 minutes';"
   ```

4. **Temporarily scale down pods to reduce connections:**
   ```bash
   kubectl scale deployment fte-api --replicas=2 -n customer-success-fte
   kubectl scale deployment fte-worker --replicas=2 -n customer-success-fte
   ```

5. **Long-term fix:** Increase `max_connections` in PostgreSQL or deploy PgBouncer
   as a connection pooler in front of the database.

---

### INC-007: Kafka Consumer Lag Growing (SEV-3)

**Symptoms:** Messages queued but not processed. Agent responses delayed > 60 seconds.

**Steps:**

1. **Check current lag:**
   ```bash
   kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
     --describe --group fte-worker
   ```

2. **Check worker pod status:**
   ```bash
   kubectl get pods -n customer-success-fte -l app=fte-worker
   kubectl logs -n customer-success-fte -l app=fte-worker --tail=50
   ```

3. **Scale workers:**
   ```bash
   kubectl scale deployment fte-worker --replicas=20 -n customer-success-fte
   ```
   Note: workers scale up to 30 via HPA. Partition count limits parallel consumers.

4. **Check for poison messages (stuck in DLQ):**
   ```bash
   # Count DLQ messages
   kafka-console-consumer --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
     --topic fte.dlq --from-beginning --max-messages 10
   ```

5. **If OpenAI rate limits are causing slowdown:**
   - Reduce worker replicas to decrease concurrent API calls
   - Rate limit: `kubectl set env deployment/fte-worker OPENAI_REQUESTS_PER_MIN=60 -n customer-success-fte`

---

### INC-008: Escalation Rate > 25% (SEV-4)

**Symptoms:** `/metrics/channels` shows `escalation_rate` above 0.25.

**This is a quality issue, not a system failure.**

**Steps:**

1. **Identify top escalation reasons:**
   ```bash
   psql $DATABASE_URL -c "
     SELECT metadata->>'escalation_reason' AS reason, count(*)
     FROM tickets
     WHERE status = 'escalated'
       AND created_at > now() - interval '24 hours'
     GROUP BY reason
     ORDER BY count DESC
     LIMIT 10;
   "
   ```

2. **Identify knowledge gaps:** Common reasons that should be in knowledge base.
   Add articles to the `knowledge_base` table for frequently escalated topics:
   ```sql
   INSERT INTO knowledge_base (title, content, category, embedding)
   VALUES ('How to sync Gmail contacts', '...', 'technical', NULL);
   -- Embedding will be generated by the agent on next search
   ```

3. **Review agent system prompt** in `production/agent/customer_success_agent.py`
   for calibration adjustments.

4. **Check escalation routing** in `production/agent/tools.py` `_route_escalation()`
   to ensure correct team assignment.

---

## Escalation Contacts

| Issue | Contact | Channel |
|-------|---------|---------|
| OpenAI API outage | OpenAI support | https://status.openai.com |
| Twilio outage | Twilio support | https://status.twilio.com |
| GCP / Pub/Sub outage | GCP support | https://status.cloud.google.com |
| Database corruption | DBA team | PagerDuty: #dba-oncall |
| Security incident | Security team | PagerDuty: #security-oncall |

---

## Post-Incident Review Template

After every SEV-1 or SEV-2 incident, complete within 48 hours:

```markdown
## Incident Report — [DATE] — [INC-XXX]

**Duration:** HH:MM
**Impact:** [channels affected, estimated customer impact]
**Root Cause:** [single sentence]

### Timeline
- HH:MM — Alert fired / issue detected
- HH:MM — Diagnosis started
- HH:MM — Root cause identified
- HH:MM — Fix deployed
- HH:MM — Resolved confirmed

### Root Cause Analysis
[Detail the technical root cause]

### Contributing Factors
[What made detection or resolution slower]

### Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| [Fix] | [Name] | [Date] |
| [Monitor] | [Name] | [Date] |
| [Document] | [Name] | [Date] |
```

---

## Regular Maintenance Tasks

| Frequency | Task | Command |
|-----------|------|---------|
| Weekly | Renew Gmail watch | See INC-004 step 2 |
| Weekly | Check Kafka consumer lag | `kafka-consumer-groups --describe` |
| Monthly | Rotate API keys | Update kubectl secrets |
| Monthly | Review escalation rate | `/metrics/channels` |
| Monthly | Vacuum PostgreSQL | `psql -c "VACUUM ANALYZE;"` |
| Quarterly | Load test | `locust -f production/tests/load_test.py` |
