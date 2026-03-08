# EstateFlow CRM — Product Documentation
**Document Type:** Knowledge Base for AI Customer Success FTE
**Audience:** Internal AI Agent Reference
**Last Updated:** 2026-03-08
**Purpose:** This document is the primary knowledge source the AI agent uses to answer customer questions. When a customer asks how something works, search here first.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Account & Billing](#account--billing)
3. [Lead & Contact Management](#lead--contact-management)
4. [Pipeline & Deal Tracker](#pipeline--deal-tracker)
5. [Task & Follow-Up Automation](#task--follow-up-automation)
6. [Communication Hub](#communication-hub)
7. [Transaction Coordination](#transaction-coordination)
8. [Reporting & Analytics](#reporting--analytics)
9. [Mobile App](#mobile-app)
10. [Integrations](#integrations)
11. [Team & Brokerage Features](#team--brokerage-features)
12. [Data, Privacy & Security](#data-privacy--security)
13. [Troubleshooting](#troubleshooting)
14. [Frequently Asked Questions](#frequently-asked-questions)

---

## Getting Started

### Creating Your Account
1. Go to app.estateflow.io and click **Start Free Trial**.
2. Enter your name, email address, and create a password.
3. Select your role: **Solo Agent**, **Team Lead**, or **Brokerage Admin**.
4. Choose a plan (you can change this later). All plans start with a 14-day free trial — no credit card required.
5. Complete the onboarding wizard: import contacts, connect your email, and set up your first pipeline.

### Onboarding Wizard
The onboarding wizard runs automatically on first login. It walks you through:
- Connecting your email (Gmail or Outlook)
- Importing contacts from a CSV or from Zillow/Realtor.com
- Creating your first pipeline board
- Setting up your first follow-up task

You can re-run the onboarding wizard at any time from **Settings → Onboarding**.

### System Requirements
- **Browser:** Chrome 110+, Firefox 110+, Safari 16+, Edge 110+
- **Mobile:** iOS 15+ or Android 10+
- **Internet:** Stable broadband connection required. Offline mode not supported.

### Switching Plans
You can upgrade or downgrade your plan at any time from **Settings → Billing → Change Plan**. Upgrades take effect immediately. Downgrades take effect at the end of your current billing cycle.

---

## Account & Billing

### Plans and Pricing
| Plan | Monthly (per agent) | Annual (per agent) | Contact Limit | Key Features |
|---|---|---|---|---|
| Starter | $39 | $31.20 | 500 | Core CRM, 1 pipeline, basic tasks |
| Professional | $79 | $63.20 | Unlimited | Automations, drip campaigns, advanced reporting |
| Team | $149 | $119.20 | Unlimited | Shared pipelines, team dashboards, role permissions |
| Brokerage | Custom | Custom | Unlimited | SSO, compliance checklists, dedicated support, admin controls |

Annual billing saves 20%. You can switch between monthly and annual at any time.

### Free Trial
- All plans include a **14-day free trial**.
- No credit card is required to start the trial.
- At the end of the trial, you must enter a payment method to continue. Your data is retained for 30 days after trial expiration before being deleted.
- Trial accounts have access to all Professional plan features.

### Adding a Payment Method
1. Go to **Settings → Billing**.
2. Click **Add Payment Method**.
3. Enter your credit card or debit card details.
4. Click **Save**. Your card is encrypted and stored securely via Stripe.

### Invoices and Receipts
Invoices are emailed automatically on each billing date. To download past invoices, go to **Settings → Billing → Invoice History**.

### Cancellation Policy
- You can cancel at any time from **Settings → Billing → Cancel Plan**.
- Cancellation takes effect at the end of your current billing period. You will not be charged again.
- Data is retained for 30 days post-cancellation, after which it is permanently deleted.
- Refunds are not issued for partial months. For disputes, contact team@estateflow.io.

### Adding or Removing Agents (Team/Brokerage Plans)
- To add an agent: **Settings → Team → Invite Agent**. Enter their email and assign a role.
- To remove an agent: **Settings → Team → Manage Agents → Deactivate**. Their contacts and deals are reassigned to you or another agent.
- Billing adjusts automatically at the next cycle.

---

## Lead & Contact Management

### Adding Contacts
**Manually:**
1. Click **Contacts** in the left sidebar.
2. Click **+ New Contact**.
3. Fill in name, email, phone, and lead source.
4. Click **Save**.

**Via CSV Import:**
1. Go to **Contacts → Import → Upload CSV**.
2. Download the CSV template to see required column headers.
3. Upload your file. EstateFlow maps columns automatically — review and confirm the mapping.
4. Click **Import**. Duplicate contacts are detected and flagged for review.

**Via Integration (Zillow, Realtor.com):**
See the [Integrations](#integrations) section.

### Contact Fields
Each contact record includes:
- **Basic info:** Name, email, phone, address
- **Lead source:** Where they came from (Zillow, referral, open house, etc.)
- **Lifecycle stage:** Lead → Prospect → Active Client → Past Client → Archived
- **Property preferences:** Budget, bedrooms, neighborhoods, property type (buyer profile)
- **Tags:** Custom labels for filtering and grouping
- **Custom fields:** Add any field specific to your workflow (e.g., pre-approval status, HOA preference)
- **Activity timeline:** All emails, calls, notes, tasks, and messages in chronological order

### Lifecycle Stages
| Stage | Meaning |
|---|---|
| Lead | New, unqualified contact — hasn't been reached yet |
| Prospect | Contacted and showing interest — in conversation |
| Active Client | Actively working with you on a transaction |
| Past Client | Transaction closed — nurture for referrals |
| Archived | Inactive, unresponsive, or removed from active pipeline |

Move contacts between stages by dragging on the Contacts board view or editing the field on their record.

### Duplicate Detection
EstateFlow automatically detects duplicate contacts based on email address and phone number. When a duplicate is found:
- You receive an in-app notification.
- You can **Merge** records (combines all activity history) or **Ignore** (keeps both).
- Merge is irreversible — review carefully before confirming.

### Filtering and Searching Contacts
- Use the **Search** bar (top of Contacts page) to find by name, email, or phone.
- Use **Filters** to narrow by lifecycle stage, lead source, tags, assigned agent, or last activity date.
- Save frequently used filters as **Saved Views** for quick access.

### Tagging Contacts
Tags are custom labels you create. Examples: `hot-lead`, `referral`, `investor`, `first-time-buyer`.
- Add tags from the contact record or in bulk from the Contacts list.
- Filter by tag to send targeted email campaigns or bulk tasks.

---

## Pipeline & Deal Tracker

### What is a Pipeline?
A pipeline is a visual Kanban board representing your sales or transaction process. Each column is a **stage**, and each card is a **deal** (buyer search, listing, or transaction).

### Creating a Pipeline
1. Go to **Pipelines** in the left sidebar.
2. Click **+ New Pipeline**.
3. Name your pipeline (e.g., "Buyer Pipeline", "Listing Pipeline").
4. Add stages by clicking **+ Add Stage**. Default stages: New Lead → Consultation → Active Search → Under Contract → Closed.
5. Click **Save Pipeline**.

You can create multiple pipelines (e.g., separate ones for buyers and sellers).

### Adding a Deal
1. In your pipeline, click **+ Add Deal** in the desired stage.
2. Link the deal to an existing contact or create a new one.
3. Fill in deal details: property address, price range, closing date target.
4. Click **Save**.

### Deal Card Details
Each deal card contains:
- Linked contact(s)
- Property address and details
- Key dates: offer date, inspection date, appraisal date, closing date
- Deal value (commission estimate)
- Assigned agent
- Documents (upload PDFs, contracts, disclosures)
- Notes and activity log
- Linked tasks

### Moving Deals Through Stages
- **Drag and drop** deal cards between stages on the Kanban board.
- Moving a deal can trigger **automated tasks** (if automations are configured).
- Stage change history is logged in the deal's activity timeline.

### Pipeline Health Score
The Pipeline Health Score is an AI-generated indicator (shown as a colored dot on each deal card) that flags at-risk deals:
- **Green:** On track — recent activity, no overdue tasks
- **Yellow:** Attention needed — no activity in 7+ days or upcoming milestone
- **Red:** At risk — no activity in 14+ days, overdue tasks, or stale stage

Hover over the dot to see the reason. Click to see suggested next actions.

### Archiving and Closing Deals
- **Close a deal:** Move it to the "Closed" stage. You'll be prompted to enter the final sale price and commission.
- **Archive a deal:** For lost or cancelled deals. Go to the deal card → **More Options → Archive**. Archived deals are hidden from the board but remain in reporting.

---

## Task & Follow-Up Automation

### Manual Tasks
To create a task:
1. Click **Tasks** in the sidebar, or open a contact/deal record and click **+ Task**.
2. Set a title, due date, and priority (Low / Medium / High).
3. Assign to yourself or a team member.
4. Click **Save**.

Tasks appear in your **Today's Tasks** dashboard and trigger push notifications on mobile when due.

### Automation Sequences
Available on **Professional plan and above.**

Automations are triggered by events (e.g., a new lead is added, a deal moves to a new stage) and perform a series of actions automatically.

**Creating an Automation:**
1. Go to **Settings → Automations → + New Automation**.
2. Choose a **Trigger:** New contact added, Stage changed, Tag applied, Date-based (e.g., 3 days before closing).
3. Add **Actions:** Send email, send SMS, create task, update lifecycle stage, assign to agent.
4. Set **Delays** between actions (e.g., wait 2 days, then send follow-up email).
5. Activate the automation.

**Example Automation — New Lead Follow-Up:**
- Trigger: New contact with stage "Lead" is added
- Action 1 (immediately): Send welcome email using template "New Lead Welcome"
- Action 2 (2 days later): Create task "Call [Contact Name]" assigned to agent
- Action 3 (5 days later, if no reply): Send follow-up email "Checking In"

### Email & SMS Drip Campaigns
Drip campaigns are automated sequences of emails and/or SMS messages sent over time.
- Go to **Automations → Drip Campaigns → + New Campaign**.
- Add messages, set intervals, and choose an audience (filter by tag, stage, or lead source).
- Drip campaigns pause automatically if the contact replies (to avoid spamming).

### Task Templates
Create reusable task checklists for recurring workflows (e.g., "New Listing Checklist", "Buyer Onboarding").
- Go to **Settings → Task Templates → + New Template**.
- Add tasks with relative due dates (e.g., "Day 1: Send intro email", "Day 3: Schedule consultation").
- Apply a template to any contact or deal with one click.

---

## Communication Hub

### Connecting Your Email
**Gmail:**
1. Go to **Settings → Integrations → Gmail**.
2. Click **Connect Gmail Account**.
3. Sign in to your Google account and grant permissions.
4. All sent and received emails from/to contacts in EstateFlow are synced automatically.

**Outlook / Microsoft 365:**
1. Go to **Settings → Integrations → Outlook**.
2. Click **Connect Outlook Account**.
3. Sign in with your Microsoft credentials and grant permissions.

### Sending Emails from EstateFlow
1. Open a contact record.
2. Click **Send Email** in the Communication tab.
3. Choose a template or write a new message.
4. Click **Send**. The email is sent from your connected email address.

All emails are logged to the contact's activity timeline automatically.

### Email Templates
Create reusable email templates for common messages.
- Go to **Settings → Email Templates → + New Template**.
- Use merge tags to personalize: `{{first_name}}`, `{{property_address}}`, `{{agent_name}}`, `{{closing_date}}`.
- Templates are available when composing emails from any contact record.

### Two-Way SMS
Available on **Professional plan and above.**
- EstateFlow provides a dedicated business SMS number (powered by Twilio).
- Send and receive SMS from within the contact record, same as email.
- SMS conversations are logged to the activity timeline.
- To enable: **Settings → Integrations → SMS → Enable SMS**.

### Client Portal
Available on **Team and Brokerage plans.**
- Each active client can be invited to a branded portal where they view their transaction status, uploaded documents, and task progress.
- To invite a client: Open the deal record → **Client Portal → Send Invite**.
- Clients log in with a one-time link (no account needed). They cannot edit anything — view only.

---

## Transaction Coordination

### What is a Transaction?
A transaction is a formal record for an active deal under contract. It includes a structured checklist of all tasks required to get from accepted offer to closing.

### Creating a Transaction
1. When a deal moves to "Under Contract" stage in your pipeline, you'll be prompted to **Create Transaction**.
2. Alternatively, go to **Transactions → + New Transaction** and link it to a deal.
3. Select a **Transaction Template** (buyer-side, seller-side, or custom).
4. EstateFlow auto-populates key dates based on the contract dates you enter.

### Transaction Checklists
Each transaction includes a checklist of required steps. Default buyer-side checklist:
- [ ] Executed purchase agreement uploaded
- [ ] Earnest money confirmed
- [ ] Inspection scheduled
- [ ] Inspection report reviewed
- [ ] Appraisal ordered
- [ ] Appraisal received
- [ ] Loan commitment received
- [ ] Final walkthrough scheduled
- [ ] Closing disclosure reviewed
- [ ] Keys transferred — deal closed

Tasks are assigned to agents, transaction coordinators, or external parties (e.g., lender, title company) by entering their email.

### Deadline Alerts
EstateFlow sends automatic reminders:
- **7 days before** any deadline: In-app notification + email
- **3 days before:** Push notification (mobile)
- **Day of:** SMS alert (if SMS enabled)
- **1 day overdue:** Red flag on transaction + escalation alert to team lead (Team/Brokerage plans)

### Compliance Checklists (Brokerage Plan)
Brokerage admins can define mandatory compliance checklists that agents cannot mark a transaction as closed without completing.
- Set up at: **Brokerage Admin → Compliance → + New Checklist**.
- Admins can audit all transactions for compliance status from the admin dashboard.

---

## Reporting & Analytics

### Main Dashboard
The dashboard (home screen after login) shows:
- **Today's Tasks** — due today
- **Pipeline Summary** — total deal value by stage
- **Recent Activity** — latest interactions across all contacts
- **Lead Volume** — new leads added this week vs. last week
- **Follow-Up Alerts** — contacts with no activity in 7+ days

### Reports Available
Go to **Reports** in the sidebar to access:

| Report | Description |
|---|---|
| Lead Conversion | % of leads converted to active clients by source |
| Pipeline Value | Total estimated commission value by stage and agent |
| Agent Activity | Calls, emails, tasks completed per agent (Team/Brokerage) |
| Days to Close | Average time from first contact to closed deal |
| Closed Deals | All closed transactions with sale price and commission |
| Email Performance | Open rates, click rates for campaigns and templates |
| Drip Campaign Stats | Engagement metrics per automation sequence |

### Exporting Reports
All reports can be exported to **CSV** or **PDF**.
- Click **Export** (top right of any report).
- Choose format and date range.
- The file downloads immediately.

### Custom Date Ranges
All reports support custom date ranges. Use the date picker at the top of each report to set your range.

---

## Mobile App

### Downloading the App
- **iOS:** Search "EstateFlow CRM" on the App Store
- **Android:** Search "EstateFlow CRM" on Google Play

### Logging In
Use the same email and password as your web account. The app supports Face ID / Touch ID after initial login.

### Features Available on Mobile
- View, add, and edit contacts
- View and move pipeline deals
- Create and complete tasks
- Send emails and SMS
- Receive push notifications for new leads, task due dates, and messages
- View today's schedule and activity feed
- Access uploaded documents (view only)

### Push Notifications
Notifications are enabled by default. To customize:
- iOS: **iPhone Settings → EstateFlow → Notifications**
- Android: **Phone Settings → Apps → EstateFlow → Notifications**
- In-app: **Profile → Notification Preferences**

### Offline Mode
EstateFlow mobile does **not** support offline mode. An internet connection is required to load data. Previously viewed records may appear briefly while reconnecting, but no edits can be made offline.

---

## Integrations

### Zillow Integration
1. Go to **Settings → Integrations → Zillow**.
2. Enter your Zillow Premier Agent account credentials.
3. New leads from Zillow are automatically imported as contacts with source tagged "Zillow".
4. Lead routing rules apply (for Team plans).

### Realtor.com Integration
1. Go to **Settings → Integrations → Realtor.com**.
2. Follow the OAuth connection flow.
3. Leads are imported automatically with source tagged "Realtor.com".

### DocuSign Integration
1. Go to **Settings → Integrations → DocuSign**.
2. Connect your DocuSign account.
3. Send documents for e-signature directly from a deal record: **Deal → Documents → Send for Signature**.
4. Signature status updates automatically in EstateFlow.

### Dotloop Integration
1. Go to **Settings → Integrations → Dotloop**.
2. Connect your Dotloop account.
3. Loops linked to EstateFlow deals sync status and documents back automatically.

### Google Calendar Integration
1. Go to **Settings → Integrations → Google Calendar**.
2. Connect your Google account.
3. Tasks with due dates sync as calendar events. Meeting events from Google Calendar appear in your EstateFlow activity feed.

### Zapier / Webhooks
For custom integrations not natively supported:
- **Zapier:** Search "EstateFlow" in Zapier's app directory. Supported triggers: New Contact, Stage Changed, Deal Closed. Supported actions: Create Contact, Create Task, Move Deal.
- **Webhooks:** Go to **Settings → Integrations → Webhooks → + New Webhook**. Enter your endpoint URL and select events to subscribe to.

---

## Team & Brokerage Features

### Roles and Permissions
| Role | Access Level |
|---|---|
| Agent | Own contacts, own pipeline, own tasks only |
| Team Lead | All agents' contacts, pipelines, and tasks within the team |
| Brokerage Admin | Full access to all agents, settings, billing, compliance |
| Transaction Coordinator | Assigned transactions only — no pipeline access |

To change a team member's role: **Settings → Team → [Agent Name] → Edit Role**.

### Lead Routing
Available on **Team and Brokerage plans.**

Automatically assign inbound leads to agents based on rules:
- **Round-robin:** Distribute leads evenly across agents
- **Geographic:** Route by zip code or neighborhood
- **Price range:** Route by buyer budget or listing price
- **Source:** Route Zillow leads to Agent A, Realtor.com leads to Agent B

Set up at: **Settings → Lead Routing → + New Rule**.

### Team Dashboard (Team Lead View)
Team leads see an aggregated view of:
- All agents' pipelines and deal counts
- Agent activity scores (tasks completed, emails sent, calls logged)
- Team-wide lead volume and conversion rates
- Overdue tasks across all agents

### Brokerage Admin Panel
Brokerage admins have access to:
- All agents and team management
- Company-wide reporting
- Compliance checklist management
- Billing and invoice management
- SSO configuration (SAML 2.0)
- Data export (full account export)
- Audit logs (all user actions for the past 12 months)

### SSO (Single Sign-On)
Available on **Brokerage plan only.**
- Supports SAML 2.0.
- Compatible with Okta, Azure AD, Google Workspace, and most major identity providers.
- Set up at: **Brokerage Admin → Security → SSO Configuration**.
- Once enabled, all agents must log in through the SSO provider.

---

## Data, Privacy & Security

### Data Storage
- All data is stored on AWS servers in the US (us-east-1).
- Data is encrypted at rest (AES-256) and in transit (TLS 1.3).
- Backups run every 24 hours and are retained for 30 days.

### Data Export
- Any account owner can export all their data at any time.
- Go to **Settings → Account → Export My Data**.
- A CSV/ZIP archive of all contacts, deals, tasks, emails, and notes is emailed to you within 24 hours.

### Data Deletion
- On account cancellation, data is deleted after a 30-day grace period.
- To request immediate deletion: email privacy@estateflow.io with subject "Data Deletion Request".
- Deletion is permanent and irreversible.

### GDPR & CCPA Compliance
EstateFlow is compliant with GDPR (EU) and CCPA (California). Customers can request data access or deletion at any time. Contact privacy@estateflow.io for all data rights requests.

### Two-Factor Authentication (2FA)
Strongly recommended for all accounts. Enable at: **Settings → Security → Two-Factor Authentication**.
Supported methods: Authenticator app (Google Authenticator, Authy) or SMS.

---

## Troubleshooting

### Can't Log In
- Verify you're using the correct email address.
- Click **Forgot Password** on the login page to reset via email.
- If using SSO (Brokerage plan), contact your brokerage admin.
- If the issue persists, contact support@estateflow.io.

### Emails Not Syncing
1. Go to **Settings → Integrations → Gmail/Outlook**.
2. Check if the connection status shows **Connected**. If it shows an error, click **Reconnect**.
3. Grant all required permissions when prompted.
4. If still not syncing, disconnect and reconnect the account.

### Contacts Not Importing from Zillow
- Verify the Zillow integration is active: **Settings → Integrations → Zillow → Status**.
- Ensure your Zillow Premier Agent account is active and in good standing.
- New leads from Zillow can take up to 15 minutes to appear in EstateFlow.

### Pipeline Not Displaying Correctly
- Try a hard refresh: **Ctrl+Shift+R** (Windows) or **Cmd+Shift+R** (Mac).
- Clear browser cache and cookies.
- Try a different browser.
- If the issue persists, note the URL and screenshot, and contact support.

### Mobile App Not Loading
- Check your internet connection.
- Force-close the app and reopen.
- Log out and log back in.
- Uninstall and reinstall the app if the issue persists.

### Automation Not Triggering
- Verify the automation is **Active** (toggle in **Settings → Automations**).
- Check the trigger conditions match your contact/deal data exactly.
- Check the automation's **Run History** for error messages: **Automations → [Name] → View History**.

### Transaction Checklist Not Saving
- Ensure you're on a stable internet connection.
- Try refreshing and re-checking the items.
- If the problem persists, contact support with the transaction ID.

---

## Frequently Asked Questions

**Q: Can I use EstateFlow for rental property management?**
A: EstateFlow is primarily designed for sales transactions (buyer/seller), but many property managers use it to track tenant leads and lease renewals. A dedicated property management module is on our roadmap.

**Q: Can I import contacts from my previous CRM (e.g., Follow Up Boss, LionDesk)?**
A: Yes. Export your contacts as a CSV from your previous CRM and import via **Contacts → Import → Upload CSV**. Contact support for help mapping custom fields.

**Q: Does EstateFlow work with my MLS?**
A: EstateFlow integrates with Zillow and Realtor.com for lead import. Direct MLS feed integration (IDX) is available on Brokerage plans — contact sales for setup.

**Q: Can multiple agents share the same contact?**
A: Yes, on Team and Brokerage plans. Go to the contact record → **Assigned Agents → Add Agent** to share access.

**Q: Is there a limit to how many pipelines I can create?**
A: Starter plan: 1 pipeline. Professional and above: unlimited pipelines.

**Q: Can I white-label EstateFlow for my brokerage?**
A: Custom branding (logo, colors) on the client portal is available on Brokerage plans. Full white-labeling is available as an enterprise add-on — contact sales.

**Q: How do I pause an automation without deleting it?**
A: Go to **Settings → Automations → [Automation Name]** and toggle the **Active** switch to off. The automation is paused and can be re-enabled at any time.

**Q: What happens to my data if I downgrade my plan?**
A: Your data is never deleted on a downgrade. However, features not included in the lower plan become inaccessible (e.g., automation sequences are paused on Starter). Data created with those features is preserved and becomes accessible again if you upgrade.

**Q: Can I set up EstateFlow for a team member who doesn't have their own email?**
A: Each agent must have a unique email address to create a user account. A shared email address is not supported.

**Q: How do I contact support?**
A: Email: support@estateflow.io | WhatsApp: Available via the in-app chat widget | Web Form: app.estateflow.io/support
