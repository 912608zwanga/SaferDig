"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { createClient, Session } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

type Intention = {
  id: string; recipient_name: string; amount: string; currency: string; purpose: string;
  reference?: string | null; status: string; expires_at: string; created_at: string;
};
type VerifyResult = {
  overall_result: "match" | "mismatch" | "needs_review";
  recipient_match: boolean; recipient_needs_review: boolean; amount_match: boolean;
  purpose_match: boolean | null; explanation: string[]; disclaimer: string;
};
type HistoryItem = { id: string; intention_id: string; overall_result: string; created_at: string };

function money(value: string | number) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(Number(value));
}
function date(value: string) {
  return new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
function statusLabel(status: string) {
  return ({ pending: "Waiting to be checked", verified_match: "Details matched", mismatch: "Mismatch found", needs_review: "Review carefully", expired: "Expired" } as Record<string, string>)[status] ?? status;
}

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [intentions, setIntentions] = useState<Intention[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [purpose, setPurpose] = useState("");
  const [reference, setReference] = useState("");
  const [selected, setSelected] = useState<Intention | null>(null);
  const [payee, setPayee] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payPurpose, setPayPurpose] = useState("");
  const [payReference, setPayReference] = useState("");
  const [result, setResult] = useState<VerifyResult | null>(null);

  useEffect(() => {
    if (!supabase) { setReady(true); return; }
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  async function api(path: string, options: RequestInit = {}) {
    if (!session?.access_token) throw new Error("Please sign in again.");
    const response = await fetch(apiBase + path, {
      ...options,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}`, ...(options.headers ?? {}) }
    });
    if (response.status === 204) return null;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail ?? "Something went wrong. Please try again.");
    return body;
  }

  async function refresh() {
    if (!session) return;
    try {
      const [items, logs] = await Promise.all([
        api("/api/v1/intentions?limit=50"),
        api("/api/v1/verification-history?limit=10")
      ]);
      setIntentions(items.items ?? []);
      setHistory(logs ?? []);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not load your data."); }
  }
  useEffect(() => { if (session) refresh(); }, [session]);

  async function authenticate(event: FormEvent) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true); setAuthMessage("");
    try {
      const action = authMode === "signup"
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password });
      if (action.error) throw action.error;
      if (authMode === "signup" && !action.data.session) {
        setAuthMessage("Account created. Check your email to confirm your address, then sign in.");
      } else setAuthMessage("You're signed in.");
    } catch (error) { setAuthMessage(error instanceof Error ? error.message : "Could not authenticate."); }
    finally { setBusy(false); }
  }

  async function createIntention(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(""); setResult(null);
    try {
      await api("/api/v1/intentions", { method: "POST", body: JSON.stringify({
        recipient_name: recipient, amount, purpose, reference: reference || null, expires_in_minutes: 1440
      }) });
      setRecipient(""); setAmount(""); setPurpose(""); setReference("");
      setMessage("Your payment intention has been saved. Compare the details before confirming a payment.");
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save intention."); }
    finally { setBusy(false); }
  }

  function choose(item: Intention) {
    setSelected(item); setPayee(item.recipient_name); setPayAmount(item.amount);
    setPayPurpose(item.purpose); setPayReference(item.reference ?? ""); setResult(null);
    document.getElementById("check-payment")?.scrollIntoView({ behavior: "smooth" });
  }

  async function verify(event: FormEvent) {
    event.preventDefault(); if (!selected) return;
    setBusy(true); setMessage(""); setResult(null);
    try {
      const data = await api("/api/v1/verify", { method: "POST", body: JSON.stringify({
        intention_id: selected.id, recipient_name: payee, amount: payAmount,
        purpose: payPurpose || null, reference: payReference || null
      }) });
      setResult(data); await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not compare payment details."); }
    finally { setBusy(false); }
  }

  async function remove(item: Intention) {
    if (!window.confirm("Delete this saved intention?")) return;
    setBusy(true);
    try { await api(`/api/v1/intentions/${item.id}`, { method: "DELETE" }); setMessage("Intention deleted."); await refresh(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not delete intention."); }
    finally { setBusy(false); }
  }

  const counts = useMemo(() => ({
    open: intentions.filter(x => x.status === "pending").length,
    checked: intentions.filter(x => ["verified_match", "mismatch", "needs_review"].includes(x.status)).length
  }), [intentions]);

  if (!ready) return <main className="loading">Loading SaferDig…</main>;
  if (!supabase) return <main className="auth-wrap"><div className="auth-card"><Brand /><h1>Configuration needed</h1><p>Add the Supabase URL and publishable key to the frontend environment variables.</p></div></main>;
  if (!session) return (
    <main className="auth-wrap">
      <div className="auth-card">
        <Brand />
        <p className="eyebrow">SAFER DIGITAL PAYMENTS</p>
        <h1>Check before you confirm.</h1>
        <p className="muted">Write down what you intend to pay. Then compare it with the details shown before you approve a transaction.</p>
        <div className="tabs"><button className={authMode === "signin" ? "tab active" : "tab"} onClick={() => setAuthMode("signin")}>Sign in</button><button className={authMode === "signup" ? "tab active" : "tab"} onClick={() => setAuthMode("signup")}>Create account</button></div>
        <form onSubmit={authenticate} className="stack">
          <label>Email address<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" /></label>
          <label>Password<input type="password" autoComplete={authMode === "signin" ? "current-password" : "new-password"} minLength={8} required value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" /></label>
          <button className="primary full" disabled={busy}>{busy ? "Please wait…" : authMode === "signin" ? "Sign in" : "Create account"}</button>
        </form>
        {authMessage && <p className="notice">{authMessage}</p>}
        <p className="small muted">Prototype only. Never enter bank passwords, PINs or OTPs here.</p>
      </div>
    </main>
  );

  return (
    <main className="shell">
      <header className="topbar"><Brand /><div className="account"><span>{session.user.email}</span><button className="text-button" onClick={() => supabase.auth.signOut()}>Sign out</button></div></header>
      <section className="hero">
        <div><p className="eyebrow">YOUR PAYMENT, YOUR DECISION</p><h1>Pause. Check. Then confirm.</h1><p>Keep a record of what you meant to pay, and compare it with the payment details in front of you.</p></div>
        <div className="hero-mark"><span>✓</span><small>Take a moment<br />before you pay</small></div>
      </section>
      <div className="notice safety"><strong>Important:</strong> SaferDig is a demonstration tool. It does not connect to banks, inspect real transactions, stop payments or guarantee that a recipient is trustworthy.</div>
      {message && <div className="notice" role="status">{message}<button className="dismiss" onClick={() => setMessage("")}>×</button></div>}
      <section className="stats">
        <div className="stat"><span>Saved intentions</span><strong>{intentions.length}</strong></div>
        <div className="stat"><span>Waiting to be checked</span><strong>{counts.open}</strong></div>
        <div className="stat"><span>Checked</span><strong>{counts.checked}</strong></div>
      </section>
      <div className="columns">
        <section className="panel">
          <div className="section-heading"><div><p className="eyebrow">STEP 1</p><h2>Record your intention</h2></div><span className="step">01</span></div>
          <p className="muted">Enter the details you expect to see. This creates your own reference for the comparison.</p>
          <form onSubmit={createIntention} className="stack">
            <label>Who are you paying?<input required maxLength={120} value={recipient} onChange={e => setRecipient(e.target.value)} placeholder="Recipient or business name" /></label>
            <label>How much?<div className="money-input"><span>R</span><input required inputMode="decimal" type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0.00" /></div></label>
            <label>What is the payment for?<input required maxLength={200} value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="e.g. Electricity, groceries" /></label>
            <label>Reference <span className="optional">Optional</span><input maxLength={60} value={reference} onChange={e => setReference(e.target.value)} placeholder="Account or payment reference" /></label>
            <button className="primary" disabled={busy}>{busy ? "Saving…" : "Save my intention"}</button>
          </form>
        </section>
        <section className="panel" id="check-payment">
          <div className="section-heading"><div><p className="eyebrow">STEP 2</p><h2>Check payment details</h2></div><span className="step">02</span></div>
          <p className="muted">Choose a saved intention, then enter the recipient and amount displayed on the payment screen. Do not share any banking credentials.</p>
          <label>Choose an intention<select value={selected?.id ?? ""} onChange={e => { const item = intentions.find(x => x.id === e.target.value); if (item) choose(item); else setSelected(null); }}><option value="">Select a saved intention</option>{intentions.filter(x => ["pending", "mismatch", "needs_review"].includes(x.status)).map(x => <option key={x.id} value={x.id}>{x.recipient_name} · {money(x.amount)}</option>)}</select></label>
          {selected ? <form onSubmit={verify} className="stack verify-form">
            <label>Recipient shown<input required maxLength={120} value={payee} onChange={e => setPayee(e.target.value)} /></label>
            <label>Amount shown<div className="money-input"><span>R</span><input required type="number" min="0.01" step="0.01" value={payAmount} onChange={e => setPayAmount(e.target.value)} /></div></label>
            <label>Purpose <span className="optional">Optional</span><input maxLength={200} value={payPurpose} onChange={e => setPayPurpose(e.target.value)} /></label>
            <label>Reference <span className="optional">Optional</span><input maxLength={60} value={payReference} onChange={e => setPayReference(e.target.value)} /></label>
            <button className="primary" disabled={busy}>{busy ? "Comparing…" : "Compare details"}</button>
          </form> : <div className="empty compact">Save an intention first, then select it here.</div>}
          {result && <div className={`result ${result.overall_result}`}>
            <div className="result-title"><span>{result.overall_result === "match" ? "✓" : result.overall_result === "mismatch" ? "!" : "?"}</span><div><strong>{result.overall_result === "match" ? "Details match" : result.overall_result === "mismatch" ? "Mismatch found" : "Review carefully"}</strong><small>Comparison result</small></div></div>
            <ul>{result.explanation.map((line, i) => <li key={i}>{line}</li>)}</ul>
            <p className="small">{result.disclaimer}</p>
          </div>}
        </section>
      </div>
      <section className="panel list-panel">
        <div className="section-heading"><div><p className="eyebrow">YOUR RECORDS</p><h2>Saved intentions</h2></div><button className="text-button" onClick={refresh}>Refresh</button></div>
        {intentions.length === 0 ? <div className="empty">Your saved intentions will appear here.</div> : <div className="records">{intentions.map(item => <article className="record" key={item.id}>
          <div className="record-main"><div className="avatar">{item.recipient_name.trim().charAt(0).toUpperCase()}</div><div><strong>{item.recipient_name}</strong><p>{item.purpose} · {date(item.created_at)}</p><span className={`pill ${item.status}`}>{statusLabel(item.status)}</span></div></div>
          <div className="record-actions"><strong>{money(item.amount)}</strong>{["pending", "mismatch", "needs_review"].includes(item.status) && <button className="outline small-button" onClick={() => choose(item)}>Check details</button>}<button className="icon-button" aria-label="Delete intention" onClick={() => remove(item)}>×</button></div>
        </article>)}</div>}
      </section>
      <section className="panel list-panel">
        <div className="section-heading"><div><p className="eyebrow">ACTIVITY</p><h2>Recent checks</h2></div></div>
        {history.length === 0 ? <div className="empty">Your completed comparisons will appear here.</div> : <div className="records">{history.map(h => <article className="record" key={h.id}><div><strong>{h.overall_result === "match" ? "Details matched" : h.overall_result === "mismatch" ? "Mismatch found" : "Review carefully"}</strong><p>{date(h.created_at)}</p></div><span className={`pill ${h.overall_result}`}>{h.overall_result.replace("_", " ")}</span></article>)}</div>}
      </section>
      <footer><Brand /><p>SaferDig helps you compare what you intended with what you see. It is not a fraud-detection system or a payment authorization service.</p><small>Prototype · Simulation only · No bank connection</small></footer>
    </main>
  );
}

function Brand() { return <div className="brand"><span className="brand-icon" aria-hidden="true">✓</span><span>Safer<span>Dig</span></span></div>; }
