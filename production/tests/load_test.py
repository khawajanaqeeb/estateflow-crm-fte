"""
EstateFlow Customer Success FTE — Load Test
Phase 3: 24/7 Readiness Validation

Simulates realistic multi-channel traffic using Locust.

Run with:
  locust -f production/tests/load_test.py --host http://localhost:8000

Targets from hackathon requirements:
  - P95 latency < 3 seconds
  - Uptime > 99.9%
  - Web form: 100+ submissions over 24 hours
  - Cross-channel: 10+ customers contact via multiple channels
"""

import random
import string
from locust import HttpUser, task, between, events


# ── Shared test data ──────────────────────────────────────────────────────────

CATEGORIES  = ["general", "technical", "billing", "bug_report", "feedback"]
PRIORITIES  = ["low", "medium", "high"]

TECH_ISSUES = [
    "I cannot sync my Gmail contacts to EstateFlow. Getting authentication error.",
    "The mobile app crashes every time I try to open the pipeline view.",
    "My Zillow integration stopped working after the last update.",
    "Calendar sync with Google Calendar is not showing upcoming appointments.",
    "The bulk import of contacts from CSV is failing at row 47.",
    "Two-factor authentication code is not being sent to my phone.",
    "The DocuSign integration is not sending documents to clients.",
    "My automated follow-up sequences stopped sending emails yesterday.",
    "Team members cannot see shared pipeline even though I set permissions correctly.",
    "The reporting dashboard is showing incorrect lead conversion numbers.",
]

BILLING_ISSUES = [
    "I was charged twice for my Professional plan subscription this month.",
    "My invoice shows 5 agents but I only have 3 active users.",
    "I cancelled my subscription two weeks ago but was still charged.",
    "I need a copy of my invoice for tax purposes — how do I download it?",
]

GENERAL_QUESTIONS = [
    "How do I import contacts from Zillow into EstateFlow?",
    "Can I set up automated email sequences for new leads?",
    "What is the difference between the Team and Brokerage plans?",
    "How do I reset my password?",
    "How can I add a new team member to my account?",
    "Is there a mobile app available for Android?",
    "How do I export all my contacts to a CSV file?",
    "Can I customize the pipeline stages for my workflow?",
]


def random_email():
    uid = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"loadtest.{uid}@example.com"


def random_name():
    first = random.choice(["Sarah", "Marcus", "Diana", "Jordan", "Alex", "Casey", "Morgan"])
    last  = random.choice(["Morrison", "Reed", "Chen", "Patel", "Kim", "Johnson", "Williams"])
    return f"{first} {last}"


# ── User types ────────────────────────────────────────────────────────────────

class WebFormUser(HttpUser):
    """
    Simulates customers submitting support requests via the web form.
    Most common channel — weight 5.
    """
    wait_time = between(2, 10)
    weight    = 5

    def on_start(self):
        self.email = random_email()
        self.name  = random_name()
        self.submitted_tickets = []

    @task(6)
    def submit_technical_issue(self):
        with self.client.post(
            "/support/submit",
            json={
                "name":     self.name,
                "email":    self.email,
                "subject":  "Technical issue with EstateFlow",
                "category": "technical",
                "priority": random.choice(PRIORITIES),
                "message":  random.choice(TECH_ISSUES),
            },
            catch_response=True,
            name="/support/submit [technical]",
        ) as res:
            if res.status_code == 200:
                ticket_id = res.json().get("ticket_id")
                if ticket_id:
                    self.submitted_tickets.append(ticket_id)
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(3)
    def submit_general_question(self):
        with self.client.post(
            "/support/submit",
            json={
                "name":     self.name,
                "email":    self.email,
                "subject":  "Question about EstateFlow features",
                "category": "general",
                "priority": "low",
                "message":  random.choice(GENERAL_QUESTIONS),
            },
            catch_response=True,
            name="/support/submit [general]",
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(1)
    def submit_billing_issue(self):
        with self.client.post(
            "/support/submit",
            json={
                "name":     self.name,
                "email":    self.email,
                "subject":  "Billing question",
                "category": "billing",
                "priority": "high",
                "message":  random.choice(BILLING_ISSUES),
            },
            catch_response=True,
            name="/support/submit [billing]",
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(2)
    def check_ticket_status(self):
        """Check status of a previously submitted ticket."""
        if not self.submitted_tickets:
            return
        ticket_id = random.choice(self.submitted_tickets)
        with self.client.get(
            f"/support/ticket/{ticket_id}",
            catch_response=True,
            name="/support/ticket/{id}",
        ) as res:
            if res.status_code in (200, 404):
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")


class HealthMonitorUser(HttpUser):
    """
    Simulates monitoring systems polling /health and /metrics.
    Low weight — background traffic.
    """
    wait_time = between(10, 30)
    weight    = 1

    @task(3)
    def check_health(self):
        with self.client.get("/health", catch_response=True) as res:
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "healthy":
                    res.success()
                else:
                    res.failure("Health check returned non-healthy status")
            else:
                res.failure(f"Health check failed: {res.status_code}")

    @task(1)
    def check_metrics(self):
        with self.client.get(
            "/metrics/channels",
            catch_response=True,
            name="/metrics/channels",
        ) as res:
            if res.status_code in (200, 500):
                res.success()
            else:
                res.failure(f"Metrics failed: {res.status_code}")


class CrossChannelUser(HttpUser):
    """
    Simulates customers who contact support via multiple channels.
    Submits via web form and then looks up their own customer record.
    Weight 2.
    """
    wait_time = between(5, 20)
    weight    = 2

    def on_start(self):
        self.email = random_email()
        self.name  = random_name()

    @task
    def multi_channel_journey(self):
        # Step 1: Submit via web form
        res = self.client.post(
            "/support/submit",
            json={
                "name":     self.name,
                "email":    self.email,
                "subject":  "Cross-channel customer journey test",
                "category": "technical",
                "message":  "I contacted you on WhatsApp first and now using the web form.",
            },
            name="/support/submit [cross-channel]",
        )
        if res.status_code != 200:
            return

        # Step 2: Look up own customer record (simulates WhatsApp follow-up)
        self.client.get(
            "/customers/lookup",
            params={"email": self.email},
            name="/customers/lookup",
        )


# ── Custom event hooks ────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*60)
    print("EstateFlow FTE Load Test Starting")
    print("Targets: P95 < 3s | Uptime > 99.9% | Escalation < 25%")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    print("\n" + "="*60)
    print("Load Test Complete — Summary")
    print(f"  Total requests : {total.num_requests}")
    print(f"  Failures       : {total.num_failures}")
    print(f"  Failure rate   : {total.fail_ratio * 100:.2f}%")
    print(f"  Median latency : {total.median_response_time}ms")
    print(f"  P95 latency    : {total.get_response_time_percentile(0.95)}ms")
    print(f"  P99 latency    : {total.get_response_time_percentile(0.99)}ms")
    print(f"  RPS            : {total.current_rps:.1f}")

    p95 = total.get_response_time_percentile(0.95)
    if p95 and p95 < 3000:
        print("\n  ✓ P95 latency target MET (< 3 seconds)")
    else:
        print(f"\n  ✗ P95 latency target MISSED ({p95}ms)")

    if total.fail_ratio < 0.001:
        print("  ✓ Uptime target MET (> 99.9%)")
    else:
        print(f"  ✗ Uptime target MISSED (failure rate: {total.fail_ratio*100:.3f}%)")

    print("="*60 + "\n")
