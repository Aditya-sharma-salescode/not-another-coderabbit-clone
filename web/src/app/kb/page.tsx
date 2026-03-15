"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Same hardcoded responses as landing page (for demo mode)
// ---------------------------------------------------------------------------

const KB_DEMOS: Record<string, string> = {
  "who updated order_checkout for cokearg_sfa?": `Last changed by dev@salescode.ai on 2026-03-10.

cokearg_sfa has 3 override pages: orderFeedback.dart, orderHelperFunctions.dart, orderplacing.dart.

Last Jira ticket: COCA-850 — Cart state fix (merged 2026-02-10)`,

  "list all features": `Found 178 features across 3 namespaces:

| Namespace              | Count |
|------------------------|-------|
| lib/features/          | 92    |
| lib/sfa/features/      | 48    |
| lib/channelKart/features/ | 38 |

Top features by activity: order_checkout (23 commits), cart (18), sfa_attendance (15), catalogue (14)`,

  "what open bugs exist for cart?": `Found 3 open bugs for cart:

| Key       | Summary                                      | Priority |
|-----------|----------------------------------------------|----------|
| COCA-912  | Cart total mismatch on multi-LOB order       | High     |
| COCA-889  | Empty cart screen flickers on slow network   | Medium   |
| CSLC-445  | Cart badge count not updating after remove   | Low      |`,

  "which lobs override attendance?": `4 LOBs have custom overrides for sfa_attendance:

| LOB           | Override Pages                                    | Notes                |
|---------------|---------------------------------------------------|----------------------|
| cokearg_sfa   | attendanceFeedback.dart, attendanceMarking.dart    | Custom GPS validation |
| unnati        | attendanceScreen.dart                              | Photo-based attendance |
| SFA_Generic   | attendanceHelper.dart                              | Standard SFA flow    |
| fieldmax      | attendanceFeedback.dart                            | Geo-fenced only      |`,

  "what does coca-850 do?": `COCA-850 — Fix cart state persistence during checkout flow

Status: Done | Type: Bug | Epic: Order Flow Reliability
Assignee: dev@salescode.ai

Acceptance Criteria:
- Cart state must survive app backgrounding during checkout
- Order total must recalculate on resume
- No duplicate line items after state restore`,

  "show recent changes for order_checkout": `order_checkout — 6 files changed in the last 90 days:

| File                          | Last Modified | Commits | Authors      |
|-------------------------------|--------------|---------|--------------|
| view/orderFeedback.dart       | 2026-03-10   | 3       | bob, alice   |
| view/order_page.dart          | 2026-02-28   | 5       | alice        |
| model/order_model.dart        | 2026-02-15   | 2       | charlie      |
| service/order_service.dart    | 2026-02-01   | 4       | alice, dev   |
| provider/order_provider.dart  | 2026-01-20   | 2       | bob          |
| widgets/order_summary.dart    | 2026-01-10   | 1       | alice        |`,

  "help": `Available commands and example queries:

Features:
  "list all features"                         — show all 178 features
  "show recent changes for order_checkout"   — files changed in last 90 days

LOBs:
  "which lobs override attendance?"          — LOB-specific overrides
  "who updated order_checkout for cokearg_sfa?" — LOB-filtered history

Jira:
  "what open bugs exist for cart?"           — search Jira for open bugs
  "what does COCA-850 do?"                   — fetch ticket details

Tips:
  Ask in natural language — the AI figures out which tools to call.`,
};

function matchDemo(input: string): string {
  const lower = input.toLowerCase().trim();
  if (lower === "help" || lower === "?") return KB_DEMOS["help"];
  for (const [key, value] of Object.entries(KB_DEMOS)) {
    if (lower.includes(key.split(" ").slice(0, 3).join(" ").toLowerCase())) return value;
  }
  if (lower.includes("feature")) return KB_DEMOS["list all features"];
  if (lower.includes("bug")) return KB_DEMOS["what open bugs exist for cart?"];
  if (lower.includes("override") || lower.includes("lob")) return KB_DEMOS["which lobs override attendance?"];
  if (lower.includes("recent") || lower.includes("change")) return KB_DEMOS["show recent changes for order_checkout"];
  return `I don't have a demo response for that query.

Type "help" for example queries, or try:
  "list all features"
  "who updated order_checkout for cokearg_sfa?"`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HistoryEntry {
  type: "q" | "a" | "error" | "system";
  text: string;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function KBPage() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([
    { type: "system", text: `Knowledge Base Shell — pr-reviewer\nType a question and press Enter. Type "help" for examples.\nBackend: attempting connection...` },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLive, setIsLive] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check API connectivity on mount
  useEffect(() => {
    api.getDashboard()
      .then(() => {
        setIsLive(true);
        setHistory((prev) => [
          ...prev,
          { type: "system", text: "Connected to live backend. Queries will use real data." },
        ]);
      })
      .catch(() => {
        setHistory((prev) => [
          ...prev,
          { type: "system", text: "Backend unavailable — running in demo mode with sample data." },
        ]);
      });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const question = input.trim();
    setInput("");
    setHistory((prev) => [...prev, { type: "q", text: question }]);

    if (question.toLowerCase() === "clear") {
      setHistory([{ type: "system", text: "Terminal cleared." }]);
      return;
    }

    setIsLoading(true);

    if (isLive) {
      try {
        const result = await api.queryKB(question);
        setHistory((prev) => [...prev, { type: "a", text: result.answer }]);
      } catch (err) {
        // Fallback to demo
        const answer = matchDemo(question);
        setHistory((prev) => [
          ...prev,
          { type: "a", text: answer },
          { type: "system", text: "(Live query failed — showing demo response)" },
        ]);
      }
    } else {
      // Simulate delay for demo
      await new Promise((r) => setTimeout(r, 400 + Math.random() * 600));
      const answer = matchDemo(question);
      setHistory((prev) => [...prev, { type: "a", text: answer }]);
    }

    setIsLoading(false);
  };

  const suggestions = [
    "list all features",
    "who updated order_checkout for cokearg_sfa?",
    "what open bugs exist for cart?",
    "which lobs override attendance?",
    "show recent changes for order_checkout",
    "what does COCA-850 do?",
  ];

  return (
    <div className="mx-auto flex max-w-4xl flex-col px-6 py-10" style={{ height: "calc(100vh - 56px)" }}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">KB Terminal</h1>
          <p className="text-xs text-[var(--muted)]">
            Query your feature registry, Jira history, and codebase knowledge
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${isLive ? "bg-[var(--success)]" : "bg-[var(--warning)]"}`} />
          <span className="text-xs text-[var(--muted)]">{isLive ? "Live" : "Demo"}</span>
        </div>
      </div>

      {/* Terminal */}
      <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-[var(--card-border)] bg-[#0c0c0f]">
        {/* Title bar */}
        <div className="flex items-center gap-2 border-b border-[var(--card-border)] px-4 py-2.5">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </div>
          <span className="ml-2 text-xs text-[var(--muted)]">kb — pr-reviewer</span>
        </div>

        {/* Output */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
          onClick={() => inputRef.current?.focus()}
        >
          {history.map((entry, i) => (
            <div key={i} className="mb-3 animate-typing">
              {entry.type === "q" ? (
                <div>
                  <span className="text-[var(--accent-light)]">kb&gt; </span>
                  <span className="text-white">{entry.text}</span>
                </div>
              ) : entry.type === "system" ? (
                <div className="text-[#52525b] italic">{entry.text}</div>
              ) : entry.type === "error" ? (
                <div className="text-[var(--danger)]">{entry.text}</div>
              ) : (
                <div className="whitespace-pre-wrap pl-1 text-[#a1a1aa]">{entry.text}</div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="text-[var(--muted)]">
              <span className="cursor-blink">_</span>
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex items-center border-t border-[var(--card-border)] px-4 py-2.5">
          <span className="mr-2 font-mono text-xs text-[var(--accent-light)]">kb&gt;</span>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isLoading ? "Processing..." : "Ask a question..."}
            className="flex-1 bg-transparent font-mono text-xs text-white outline-none placeholder:text-[#3f3f46]"
            disabled={isLoading}
            autoFocus
          />
        </form>
      </div>

      {/* Suggestion chips */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => {
              setInput(s);
              inputRef.current?.focus();
            }}
            className="rounded-md border border-[var(--card-border)] px-2 py-1 text-[10px] text-[var(--muted)] transition-colors hover:border-[var(--accent)]/30 hover:text-white"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
