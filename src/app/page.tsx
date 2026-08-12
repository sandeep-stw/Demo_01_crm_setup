"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Contact = {
  id: string;
  name: string;
  email: string;
  company: string | null;
  phone: string | null;
  status: string;
  createdAt: string;
};

const emptyForm = {
  name: "",
  email: "",
  company: "",
  phone: "",
  status: "lead",
};

export default function HomePage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/contacts");
      if (!response.ok) {
        throw new Error("Failed to load contacts.");
      }
      const data = (await response.json()) as Contact[];
      setContacts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load contacts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadContacts();
  }, [loadContacts]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);

    try {
      const response = await fetch("/api/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        const payload = (await response.json()) as { error?: string };
        throw new Error(payload.error ?? "Failed to create contact.");
      }

      setForm(emptyForm);
      setMessage("Contact created successfully.");
      await loadContacts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create contact.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    setMessage(null);

    try {
      const response = await fetch(`/api/contacts/${id}`, { method: "DELETE" });
      if (!response.ok) {
        throw new Error("Failed to delete contact.");
      }
      setMessage("Contact deleted.");
      await loadContacts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete contact.");
    }
  }

  return (
    <main className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 shadow-sm">
          <p className="text-sm font-medium uppercase tracking-wide text-[var(--accent)]">
            Demo CRM Setup
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Contact Pipeline</h1>
          <p className="mt-3 max-w-2xl text-[var(--muted)]">
            Create and manage contacts in this minimal CRM. Use it to verify the Cloud Agent
            development environment end to end.
          </p>
        </header>

        {(error || message) && (
          <div
            className={`rounded-xl border px-4 py-3 text-sm ${
              error
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            {error ?? message}
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-[360px_1fr]">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Add contact</h2>
            <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
              <label className="block text-sm font-medium">
                Name
                <input
                  className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                  required
                />
              </label>
              <label className="block text-sm font-medium">
                Email
                <input
                  className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                  required
                />
              </label>
              <label className="block text-sm font-medium">
                Company
                <input
                  className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                  value={form.company}
                  onChange={(event) => setForm({ ...form, company: event.target.value })}
                />
              </label>
              <label className="block text-sm font-medium">
                Phone
                <input
                  className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </label>
              <label className="block text-sm font-medium">
                Status
                <select
                  className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value })}
                >
                  <option value="lead">Lead</option>
                  <option value="qualified">Qualified</option>
                  <option value="customer">Customer</option>
                </select>
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Saving..." : "Create contact"}
              </button>
            </form>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold">Contacts</h2>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-[var(--muted)]">
                {contacts.length} total
              </span>
            </div>

            {loading ? (
              <p className="mt-6 text-sm text-[var(--muted)]">Loading contacts...</p>
            ) : contacts.length === 0 ? (
              <p className="mt-6 text-sm text-[var(--muted)]">
                No contacts yet. Add your first lead to verify the CRM flow.
              </p>
            ) : (
              <ul className="mt-6 divide-y divide-[var(--border)]">
                {contacts.map((contact) => (
                  <li
                    key={contact.id}
                    className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="font-medium">{contact.name}</p>
                      <p className="text-sm text-[var(--muted)]">{contact.email}</p>
                      <p className="text-sm text-[var(--muted)]">
                        {[contact.company, contact.phone].filter(Boolean).join(" · ") ||
                          "No company or phone"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium uppercase tracking-wide text-blue-700">
                        {contact.status}
                      </span>
                      <button
                        type="button"
                        onClick={() => void handleDelete(contact.id)}
                        className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] transition hover:border-red-200 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
