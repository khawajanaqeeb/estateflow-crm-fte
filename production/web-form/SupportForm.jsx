/**
 * EstateFlow Customer Success FTE — Web Support Form
 * Standalone embeddable React component.
 *
 * Usage:
 *   import SupportForm from './SupportForm';
 *   <SupportForm apiEndpoint="https://your-api.com/support/submit" />
 *
 * Props:
 *   apiEndpoint  string  API URL (default: '/support/submit')
 */

import React, { useState } from 'react';

// ── Constants ─────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: 'general',   label: 'General Question' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'billing',   label: 'Billing Inquiry' },
  { value: 'bug_report',label: 'Bug Report' },
  { value: 'feedback',  label: 'Feedback' },
];

const PRIORITIES = [
  { value: 'low',    label: 'Low — Not urgent' },
  { value: 'medium', label: 'Medium — Need help soon' },
  { value: 'high',   label: 'High — Urgent issue' },
];

const INITIAL_FORM = {
  name:     '',
  email:    '',
  subject:  '',
  category: 'general',
  priority: 'medium',
  message:  '',
};

const MESSAGE_MAX = 1000;

// ── Validation ────────────────────────────────────────────────────────────────

function validate(form) {
  if (form.name.trim().length < 2)
    return 'Please enter your full name (at least 2 characters).';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
    return 'Please enter a valid email address.';
  if (form.subject.trim().length < 5)
    return 'Please enter a subject (at least 5 characters).';
  if (form.message.trim().length < 10)
    return 'Please describe your issue in more detail (at least 10 characters).';
  return null;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SuccessScreen({ ticketId, onReset }) {
  return (
    <div style={styles.card}>
      <div style={styles.successIcon}>✓</div>
      <h2 style={styles.successTitle}>Request Submitted!</h2>
      <p style={styles.successText}>
        Our AI support assistant will respond to your email within 5 minutes.
      </p>
      <div style={styles.ticketBox}>
        <p style={styles.ticketLabel}>Your Ticket ID</p>
        <p style={styles.ticketId}>{ticketId}</p>
      </div>
      <p style={styles.hint}>
        Save this ID to check your ticket status anytime.
      </p>
      <button style={styles.btnPrimary} onClick={onReset}>
        Submit Another Request
      </button>
    </div>
  );
}

function ErrorBanner({ message }) {
  if (!message) return null;
  return <div style={styles.errorBanner}>{message}</div>;
}

function Field({ label, required, children }) {
  return (
    <div style={styles.field}>
      <label style={styles.label}>
        {label}{required && <span style={styles.required}> *</span>}
      </label>
      {children}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function SupportForm({ apiEndpoint = '/support/submit' }) {
  const [form,   setForm]   = useState(INITIAL_FORM);
  const [status, setStatus] = useState('idle');   // idle | submitting | success | error
  const [ticketId, setTicketId] = useState(null);
  const [error,  setError]  = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
    if (error) setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validationError = validate(form);
    if (validationError) { setError(validationError); return; }

    setStatus('submitting');
    setError(null);

    try {
      const res = await fetch(apiEndpoint, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error (${res.status})`);
      }

      const data = await res.json();
      setTicketId(data.ticket_id);
      setStatus('success');

    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
      setStatus('error');
    }
  };

  const handleReset = () => {
    setForm(INITIAL_FORM);
    setStatus('idle');
    setTicketId(null);
    setError(null);
  };

  if (status === 'success') {
    return <SuccessScreen ticketId={ticketId} onReset={handleReset} />;
  }

  const isSubmitting = status === 'submitting';

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.logo}>EstateFlow</div>
        <h2 style={styles.title}>Contact Support</h2>
        <p style={styles.subtitle}>
          Fill out the form below and our AI-powered support team will get
          back to you within 5 minutes.
        </p>
      </div>

      <ErrorBanner message={error} />

      <form onSubmit={handleSubmit} noValidate>

        {/* Name */}
        <Field label="Your Name" required>
          <input
            style={styles.input}
            type="text"
            name="name"
            value={form.name}
            onChange={handleChange}
            placeholder="Sarah Morrison"
            disabled={isSubmitting}
            required
          />
        </Field>

        {/* Email */}
        <Field label="Email Address" required>
          <input
            style={styles.input}
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            placeholder="sarah@example.com"
            disabled={isSubmitting}
            required
          />
        </Field>

        {/* Subject */}
        <Field label="Subject" required>
          <input
            style={styles.input}
            type="text"
            name="subject"
            value={form.subject}
            onChange={handleChange}
            placeholder="Brief description of your issue"
            disabled={isSubmitting}
            required
          />
        </Field>

        {/* Category + Priority row */}
        <div style={styles.row}>
          <Field label="Category" required>
            <select
              style={styles.select}
              name="category"
              value={form.category}
              onChange={handleChange}
              disabled={isSubmitting}
            >
              {CATEGORIES.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </Field>

          <Field label="Priority">
            <select
              style={styles.select}
              name="priority"
              value={form.priority}
              onChange={handleChange}
              disabled={isSubmitting}
            >
              {PRIORITIES.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </Field>
        </div>

        {/* Message */}
        <Field label="How can we help?" required>
          <textarea
            style={styles.textarea}
            name="message"
            value={form.message}
            onChange={handleChange}
            placeholder="Please describe your issue or question in detail..."
            rows={6}
            maxLength={MESSAGE_MAX}
            disabled={isSubmitting}
            required
          />
          <p style={styles.charCount}>
            {form.message.length}/{MESSAGE_MAX} characters
          </p>
        </Field>

        {/* Submit */}
        <button
          style={{
            ...styles.btnPrimary,
            ...(isSubmitting ? styles.btnDisabled : {}),
          }}
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Support Request'}
        </button>

        <p style={styles.privacy}>
          By submitting, you agree to our{' '}
          <a href="/privacy" style={styles.link}>Privacy Policy</a>.
          We typically respond within 5 minutes.
        </p>
      </form>
    </div>
  );
}

// ── Inline styles (no external CSS dependency — fully embeddable) ─────────────

const styles = {
  card: {
    maxWidth: 600,
    margin: '0 auto',
    padding: '32px 36px',
    background: '#ffffff',
    borderRadius: 12,
    boxShadow: '0 4px 24px rgba(0,0,0,0.10)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    color: '#1a1a2e',
  },
  header: {
    marginBottom: 24,
  },
  logo: {
    fontSize: 13,
    fontWeight: 700,
    color: '#2563eb',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: 700,
    margin: '0 0 8px',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
    margin: 0,
    lineHeight: 1.5,
  },
  errorBanner: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    color: '#dc2626',
    borderRadius: 8,
    padding: '12px 16px',
    fontSize: 14,
    marginBottom: 20,
  },
  field: {
    marginBottom: 20,
  },
  label: {
    display: 'block',
    fontSize: 14,
    fontWeight: 500,
    color: '#374151',
    marginBottom: 6,
  },
  required: {
    color: '#dc2626',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: 14,
    color: '#111827',
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  },
  select: {
    width: '100%',
    padding: '10px 14px',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: 14,
    color: '#111827',
    background: '#fff',
    outline: 'none',
    boxSizing: 'border-box',
    cursor: 'pointer',
  },
  textarea: {
    width: '100%',
    padding: '10px 14px',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: 14,
    color: '#111827',
    outline: 'none',
    resize: 'vertical',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
    lineHeight: 1.5,
  },
  charCount: {
    fontSize: 12,
    color: '#9ca3af',
    margin: '4px 0 0',
    textAlign: 'right',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
  },
  btnPrimary: {
    width: '100%',
    padding: '12px 0',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 4,
    transition: 'background 0.15s',
  },
  btnDisabled: {
    background: '#93c5fd',
    cursor: 'not-allowed',
  },
  privacy: {
    fontSize: 12,
    color: '#9ca3af',
    textAlign: 'center',
    marginTop: 12,
  },
  link: {
    color: '#2563eb',
    textDecoration: 'none',
  },
  // Success screen
  successIcon: {
    width: 56,
    height: 56,
    background: '#dcfce7',
    color: '#16a34a',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 28,
    fontWeight: 700,
    margin: '0 auto 20px',
    lineHeight: '56px',
    textAlign: 'center',
  },
  successTitle: {
    fontSize: 22,
    fontWeight: 700,
    textAlign: 'center',
    margin: '0 0 10px',
    color: '#111827',
  },
  successText: {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 1.5,
  },
  ticketBox: {
    background: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '14px 20px',
    textAlign: 'center',
    marginBottom: 12,
  },
  ticketLabel: {
    fontSize: 12,
    color: '#6b7280',
    margin: '0 0 4px',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  ticketId: {
    fontSize: 18,
    fontWeight: 700,
    fontFamily: 'monospace',
    color: '#111827',
    margin: 0,
    wordBreak: 'break-all',
  },
  hint: {
    fontSize: 12,
    color: '#9ca3af',
    textAlign: 'center',
    marginBottom: 20,
  },
};
