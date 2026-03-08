/**
 * EstateFlow — Ticket Status Checker
 * Standalone component that lets customers look up their ticket by ID.
 *
 * Usage:
 *   import TicketStatus from './TicketStatus';
 *   <TicketStatus apiBase="https://your-api.com" />
 */

import React, { useState } from 'react';

const STATUS_COLORS = {
  open:        { bg: '#eff6ff', text: '#1d4ed8', label: 'Open' },
  in_progress: { bg: '#fefce8', text: '#a16207', label: 'In Progress' },
  escalated:   { bg: '#fff7ed', text: '#c2410c', label: 'Escalated — Human review' },
  resolved:    { bg: '#f0fdf4', text: '#15803d', label: 'Resolved' },
  closed:      { bg: '#f9fafb', text: '#374151', label: 'Closed' },
};

export default function TicketStatus({ apiBase = '' }) {
  const [ticketId, setTicketId] = useState('');
  const [ticket,   setTicket]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  const handleLookup = async (e) => {
    e.preventDefault();
    if (!ticketId.trim()) return;

    setLoading(true);
    setError(null);
    setTicket(null);

    try {
      const res = await fetch(`${apiBase}/support/ticket/${ticketId.trim()}`);
      if (res.status === 404) throw new Error('Ticket not found. Please check your ticket ID.');
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      setTicket(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const statusInfo = ticket
    ? (STATUS_COLORS[ticket.status] || { bg: '#f9fafb', text: '#374151', label: ticket.status })
    : null;

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Check Ticket Status</h2>
      <p style={styles.subtitle}>Enter your ticket ID to see the current status and conversation.</p>

      <form onSubmit={handleLookup} style={styles.form}>
        <input
          style={styles.input}
          type="text"
          value={ticketId}
          onChange={e => setTicketId(e.target.value)}
          placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6"
          disabled={loading}
        />
        <button style={styles.btn} type="submit" disabled={loading || !ticketId.trim()}>
          {loading ? 'Looking up...' : 'Look Up'}
        </button>
      </form>

      {error && <div style={styles.error}>{error}</div>}

      {ticket && (
        <div style={styles.result}>
          {/* Status badge */}
          <div style={{ ...styles.badge, background: statusInfo.bg, color: statusInfo.text }}>
            {statusInfo.label}
          </div>

          <div style={styles.meta}>
            <span style={styles.metaItem}>
              Submitted: {new Date(ticket.created_at).toLocaleString()}
            </span>
            <span style={styles.metaItem}>
              Last updated: {new Date(ticket.last_updated).toLocaleString()}
            </span>
          </div>

          {/* Messages */}
          {ticket.messages && ticket.messages.length > 0 && (
            <div style={styles.messages}>
              <p style={styles.messagesLabel}>Conversation</p>
              {ticket.messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    ...styles.bubble,
                    ...(msg.role === 'customer' ? styles.bubbleCustomer : styles.bubbleAgent),
                  }}
                >
                  <p style={styles.bubbleRole}>
                    {msg.role === 'customer' ? 'You' : 'EstateFlow Support'}
                    <span style={styles.bubbleTime}>
                      {' · '}{new Date(msg.created_at).toLocaleTimeString()}
                    </span>
                  </p>
                  <p style={styles.bubbleContent}>{msg.content}</p>
                </div>
              ))}
            </div>
          )}

          {ticket.status === 'resolved' && (
            <p style={styles.resolved}>
              ✓ This ticket has been resolved. Reply to our email if you need further help.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

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
  title: {
    fontSize: 22,
    fontWeight: 700,
    margin: '0 0 8px',
    color: '#111827',
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
    margin: '0 0 20px',
  },
  form: {
    display: 'flex',
    gap: 10,
    marginBottom: 16,
  },
  input: {
    flex: 1,
    padding: '10px 14px',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: 14,
    color: '#111827',
    outline: 'none',
    fontFamily: 'monospace',
  },
  btn: {
    padding: '10px 20px',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  error: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    color: '#dc2626',
    borderRadius: 8,
    padding: '12px 16px',
    fontSize: 14,
    marginBottom: 16,
  },
  result: {
    marginTop: 8,
  },
  badge: {
    display: 'inline-block',
    padding: '4px 12px',
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 12,
  },
  meta: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    marginBottom: 20,
  },
  metaItem: {
    fontSize: 12,
    color: '#6b7280',
  },
  messages: {
    borderTop: '1px solid #e5e7eb',
    paddingTop: 16,
  },
  messagesLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin: '0 0 12px',
  },
  bubble: {
    padding: '12px 16px',
    borderRadius: 10,
    marginBottom: 10,
  },
  bubbleCustomer: {
    background: '#eff6ff',
    borderBottomRightRadius: 2,
  },
  bubbleAgent: {
    background: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderBottomLeftRadius: 2,
  },
  bubbleRole: {
    fontSize: 12,
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 4px',
  },
  bubbleTime: {
    fontWeight: 400,
    color: '#9ca3af',
  },
  bubbleContent: {
    fontSize: 14,
    color: '#111827',
    margin: 0,
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
  },
  resolved: {
    fontSize: 13,
    color: '#15803d',
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: 8,
    padding: '10px 14px',
    marginTop: 12,
  },
};
