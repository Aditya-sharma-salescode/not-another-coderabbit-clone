"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Hardcoded KB demo responses
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

| LOB           | Override Pages                              | Notes                |
|---------------|---------------------------------------------|----------------------|
| cokearg_sfa   | attendanceFeedback.dart, attendanceMarking.dart | Custom GPS validation |
| unnati        | attendanceScreen.dart                       | Photo-based attendance |
| SFA_Generic   | attendanceHelper.dart                       | Standard SFA flow    |
| fieldmax      | attendanceFeedback.dart                     | Geo-fenced only      |`,

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
};

function matchDemo(input: string): string {
  const lower = input.toLowerCase().trim();
  for (const [key, value] of Object.entries(KB_DEMOS)) {
    if (lower.includes(key.split(" ").slice(0, 3).join(" ").toLowerCase())) {
      return value;
    }
  }
  if (lower.includes("feature")) return KB_DEMOS["list all features"];
  if (lower.includes("bug")) return KB_DEMOS["what open bugs exist for cart?"];
  if (lower.includes("override") || lower.includes("lob"))
    return KB_DEMOS["which lobs override attendance?"];
  if (lower.includes("recent") || lower.includes("change"))
    return KB_DEMOS["show recent changes for order_checkout"];

  return `I can answer questions about features, LOBs, Jira history, and code changes.

Try asking:
- "who updated order_checkout for cokearg_sfa?"
- "list all features"
- "what open bugs exist for cart?"
- "which lobs override attendance?"`;
}

// ---------------------------------------------------------------------------
// Flow Step
// ---------------------------------------------------------------------------

function FlowStep({
  number,
  title,
  description,
  icon,
}: {
  number: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent)]/10 text-[var(--accent)]">
        {icon}
      </div>
      <span className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--muted)]">
        Step {number}
      </span>
      <h3 className="mb-1.5 text-sm font-semibold text-white">{title}</h3>
      <p className="text-xs leading-relaxed text-[var(--muted)]">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature Card
// ---------------------------------------------------------------------------

function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 transition-colors hover:border-[var(--accent)]/30">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
        {icon}
      </div>
      <h3 className="mb-1.5 text-sm font-semibold text-white">{title}</h3>
      <p className="text-xs leading-relaxed text-[var(--muted)]">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KB Terminal Demo
// ---------------------------------------------------------------------------

function KBTerminalDemo() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<{ type: "q" | "a"; text: string }[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    const question = input.trim();
    setInput("");
    setHistory((prev) => [...prev, { type: "q", text: question }]);
    setIsTyping(true);
    setTimeout(() => {
      const answer = matchDemo(question);
      setHistory((prev) => [...prev, { type: "a", text: answer }]);
      setIsTyping(false);
    }, 600 + Math.random() * 800);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--card-border)] bg-[#0c0c0f]">
      {/* Title bar */}
      <div className="flex items-center gap-2 border-b border-[var(--card-border)] px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <span className="ml-2 text-xs text-[var(--muted)]">
          Knowledge Base — pr-reviewer
        </span>
      </div>

      {/* Terminal body */}
      <div ref={scrollRef} className="h-72 overflow-y-auto p-4 font-mono text-xs leading-relaxed">
        <div className="mb-3 text-[var(--muted)]">
          Knowledge Base Shell — channelkart-flutter registry + Jira
          <br />
          Type a question and press Enter. Try: &quot;list all features&quot;
        </div>

        {history.map((entry, i) => (
          <div key={i} className="mb-3 animate-typing">
            {entry.type === "q" ? (
              <div>
                <span className="text-[var(--accent-light)]">kb&gt; </span>
                <span className="text-white">{entry.text}</span>
              </div>
            ) : (
              <div className="whitespace-pre-wrap pl-1 text-[#a1a1aa]">{entry.text}</div>
            )}
          </div>
        ))}

        {isTyping && (
          <div className="text-[var(--muted)]">
            <span className="cursor-blink">_</span>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex items-center border-t border-[var(--card-border)] px-4 py-2.5">
        <span className="mr-2 font-mono text-xs text-[var(--accent-light)]">kb&gt;</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 bg-transparent font-mono text-xs text-white outline-none placeholder:text-[#3f3f46]"
          disabled={isTyping}
        />
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icons (inline SVG)
// ---------------------------------------------------------------------------

const IconPR = () => (
  <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);
const IconBrain = () => (
  <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
  </svg>
);
const IconJira = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15a2.25 2.25 0 012.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
  </svg>
);
const IconFigma = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
  </svg>
);
const IconRegistry = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
  </svg>
);
const IconShield = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);
const IconGit = () => (
  <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
  </svg>
);
const IconArrowRight = () => (
  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
  </svg>
);
const IconChevronRight = () => (
  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
  </svg>
);

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  return (
    <div className="mx-auto max-w-6xl px-6">
      {/* ---- Hero ---- */}
      <section className="pb-20 pt-24 text-center">
        <div className="animate-fade-in">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[var(--card-border)] bg-[var(--card)] px-3 py-1 text-xs text-[var(--muted)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
            Self-hosted &middot; Open source
          </div>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-white sm:text-5xl">
            AI code reviews that
            <br />
            <span className="text-[var(--accent-light)]">understand your codebase</span>
          </h1>
          <p className="mx-auto mb-8 max-w-xl text-sm leading-relaxed text-[var(--muted)]">
            Context-aware PR reviews powered by Claude. Automatically pulls Jira tickets,
            Figma designs, feature history, and LOB overrides to deliver reviews that
            actually understand what changed and why.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-light)]"
            >
              Open Dashboard <IconArrowRight />
            </Link>
            <Link
              href="/kb"
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--card-border)] px-4 py-2 text-sm font-medium text-[var(--muted)] transition-colors hover:border-[var(--accent)]/40 hover:text-white"
            >
              Try KB Terminal
            </Link>
          </div>
        </div>
      </section>

      {/* ---- How it works ---- */}
      <section className="pb-20">
        <h2 className="mb-10 text-center text-lg font-semibold text-white">How it works</h2>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-4">
          <FlowStep number="1" title="PR Opened" description="GitHub Action triggers on every pull request to your repository" icon={<IconPR />} />
          <FlowStep number="2" title="Context Gathered" description="Fetches Jira ticket, Figma designs, feature registry, and git history" icon={<IconGit />} />
          <FlowStep number="3" title="AI Review" description="Claude analyzes the diff with full business and design context" icon={<IconBrain />} />
          <FlowStep number="4" title="Review Posted" description="Structured review comment posted directly on the PR with recommendations" icon={<IconPR />} />
        </div>
        <div className="mt-6 hidden items-center justify-center gap-2 sm:flex">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2 text-[var(--muted)]">
              <div className="h-px w-32 bg-gradient-to-r from-[var(--accent)]/60 to-[var(--accent)]/20" />
              <IconChevronRight />
            </div>
          ))}
        </div>
      </section>

      {/* ---- Features ---- */}
      <section className="pb-20">
        <h2 className="mb-2 text-center text-lg font-semibold text-white">What makes it different</h2>
        <p className="mb-10 text-center text-xs text-[var(--muted)]">Not just a diff reader — a context-aware reviewer</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FeatureCard title="Jira Integration" description="Extracts ticket key from branch name, fetches acceptance criteria, description, epic context, and open bugs automatically." icon={<IconJira />} />
          <FeatureCard title="Figma Awareness" description="Detects Figma links in Jira tickets and PR body, fetches design specs including colors, spacing, and component structure." icon={<IconFigma />} />
          <FeatureCard title="Feature Registry" description="Maintains a knowledge base of 150+ features with Jira history, git activity, LOB overrides, and related features." icon={<IconRegistry />} />
          <FeatureCard title="Sentinel Detection" description="Flags changes to critical files like go_router.dart, main.dart, and LOB config that affect the entire application." icon={<IconShield />} />
          <FeatureCard title="LOB-Aware Reviews" description="Understands 35 Lines of Business with custom override pages, ensuring LOB-specific logic is reviewed correctly." icon={<IconGit />} />
          <FeatureCard title="Auto-Updating Registry" description="Every merge to master automatically updates the feature registry with new Jira history and git file changes." icon={<IconRegistry />} />
        </div>
      </section>

      {/* ---- KB Demo ---- */}
      <section className="pb-24">
        <h2 className="mb-2 text-center text-lg font-semibold text-white">Knowledge Base Terminal</h2>
        <p className="mb-8 text-center text-xs text-[var(--muted)]">
          Ask natural language questions about your codebase, features, and history
        </p>
        <div className="mx-auto max-w-2xl">
          <KBTerminalDemo />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {["who updated order_checkout?", "list all features", "open bugs for cart", "which lobs override attendance?"].map((q) => (
            <span key={q} className="rounded-md border border-[var(--card-border)] px-2.5 py-1 text-[10px] text-[var(--muted)]">
              {q}
            </span>
          ))}
        </div>
      </section>

      {/* ---- Architecture ---- */}
      <section className="pb-24">
        <h2 className="mb-2 text-center text-lg font-semibold text-white">Architecture</h2>
        <p className="mb-8 text-center text-xs text-[var(--muted)]">Self-hosted, runs entirely on GitHub Actions — no server required</p>
        <div className="mx-auto max-w-2xl rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-6">
          <div className="space-y-3 font-mono text-xs">
            <div className="text-[var(--muted)]"># PR opened on channelkart-flutter</div>
            {[
              ["GitHub Action", "triggers pr-ai-reviewer.yml"],
              ["Diff Parser", "parse unified diff, skip *.g.dart / *.freezed.dart"],
              ["Jira Client", "COCA-850 → AC, description, epic, open bugs"],
              ["Figma Client", "design specs → colors, spacing, components"],
              ["Registry", "feature history, LOB overrides, sentinel warnings"],
              ["Claude AI", "structured review → posted as PR comment"],
            ].map(([label, desc]) => (
              <div key={label} className="flex items-center gap-3">
                <span className="inline-block w-32 shrink-0 text-[var(--accent-light)]">{label}</span>
                <span className="text-[var(--card-border)]">→</span>
                <span className="text-white">{desc}</span>
              </div>
            ))}
            <div className="border-t border-[var(--card-border)] pt-3 text-[var(--muted)]"># Branch merged to master</div>
            <div className="flex items-center gap-3">
              <span className="inline-block w-32 shrink-0 text-[var(--accent-light)]">Registry Update</span>
              <span className="text-[var(--card-border)]">→</span>
              <span className="text-white">Jira history + git file history → registry JSON + DB</span>
            </div>
          </div>
        </div>
      </section>

      {/* ---- Footer ---- */}
      <footer className="border-t border-[var(--card-border)] py-8 text-center text-xs text-[var(--muted)]">
        PR Reviewer — Built by SalesCode AI &middot; Self-hosted &middot; Powered by Claude
      </footer>
    </div>
  );
}
