"use client";

import { useEffect, useState } from "react";
import { api, type Feature, type FeatureDetail } from "@/lib/api";

// ---------------------------------------------------------------------------
// Mock features for demo
// ---------------------------------------------------------------------------

const MOCK_FEATURES: Feature[] = [
  { id: 1, name: "order_checkout", namespace: "lib/features/", source_path: "lib/features/order_checkout/", updated_at: "2026-03-14" },
  { id: 2, name: "cart", namespace: "lib/features/", source_path: "lib/features/cart/", updated_at: "2026-03-12" },
  { id: 3, name: "sfa_attendance", namespace: "lib/sfa/features/", source_path: "lib/sfa/features/sfa_attendance/", updated_at: "2026-03-13" },
  { id: 4, name: "catalogue", namespace: "lib/features/", source_path: "lib/features/catalogue/", updated_at: "2026-03-11" },
  { id: 5, name: "payment_dashboard", namespace: "lib/channelKart/features/", source_path: "lib/channelKart/features/payment_dashboard/", updated_at: "2026-03-10" },
  { id: 6, name: "auth", namespace: "lib/features/", source_path: "lib/features/auth/", updated_at: "2026-03-08" },
  { id: 7, name: "banner_v2", namespace: "lib/features/", source_path: "lib/features/banner_v2/", updated_at: "2026-03-08" },
  { id: 8, name: "ck_consumer_promo", namespace: "lib/channelKart/features/", source_path: "lib/channelKart/features/ck_consumer_promo/", updated_at: "2026-03-05" },
  { id: 9, name: "ck_payment_dashboard", namespace: "lib/channelKart/features/", source_path: "lib/channelKart/features/ck_payment_dashboard/", updated_at: "2026-03-01" },
  { id: 10, name: "auto_sync", namespace: "lib/features/", source_path: "lib/features/auto_sync/", updated_at: "2026-02-28" },
  { id: 11, name: "barcode", namespace: "lib/features/", source_path: "lib/features/barcode/", updated_at: "2026-02-25" },
  { id: 12, name: "biometric_auth", namespace: "lib/features/", source_path: "lib/features/biometric_auth/", updated_at: "2025-08-20" },
];

const MOCK_DETAIL: FeatureDetail = {
  id: 1,
  name: "order_checkout",
  namespace: "lib/features/",
  source_path: "lib/features/order_checkout/",
  updated_at: "2026-03-14",
  jira_history: [
    { ticket_key: "COCA-912", summary: "Cart total mismatch on multi-LOB order", ticket_type: "Bug", status: "In Progress", epic: "Order Flow Reliability", branch: "feat/COCA-912-cart-total-fix", linked_at: "2026-03-14" },
    { ticket_key: "COCA-850", summary: "Fix cart state persistence during checkout", ticket_type: "Bug", status: "Done", epic: "Order Flow Reliability", branch: "fix/COCA-850-cart-state", linked_at: "2026-02-10" },
    { ticket_key: "CSLC-380", summary: "Add order summary collapse animation", ticket_type: "Story", status: "Done", epic: "UX Polish", branch: "feat/CSLC-380-summary-anim", linked_at: "2026-01-15" },
  ],
  git_file_history: [
    { file_path: "lib/features/order_checkout/view/orderFeedback.dart", last_modified: "2026-03-10", commit_count: 3, authors: ["bob@salescode.ai", "alice@salescode.ai"] },
    { file_path: "lib/features/order_checkout/view/order_page.dart", last_modified: "2026-02-28", commit_count: 5, authors: ["alice@salescode.ai"] },
    { file_path: "lib/features/order_checkout/model/order_model.dart", last_modified: "2026-02-15", commit_count: 2, authors: ["charlie@salescode.ai"] },
    { file_path: "lib/features/order_checkout/service/order_service.dart", last_modified: "2026-02-01", commit_count: 4, authors: ["alice@salescode.ai", "dev@salescode.ai"] },
    { file_path: "lib/features/order_checkout/provider/order_provider.dart", last_modified: "2026-01-20", commit_count: 2, authors: ["bob@salescode.ai"] },
  ],
  lob_overrides: [
    { lob_name: "cokearg_sfa", override_pages: ["orderFeedback.dart", "orderHelperFunctions.dart", "orderplacing.dart"], notes: "Custom order feedback flow" },
    { lob_name: "unnati", override_pages: ["orderFeedback.dart"], notes: "Simplified feedback" },
  ],
};

// ---------------------------------------------------------------------------
// Namespace badge
// ---------------------------------------------------------------------------

function NamespaceBadge({ ns }: { ns: string }) {
  const label = ns.replace("lib/", "").replace("features/", "").replace(/\/$/, "") || "core";
  const colors: Record<string, string> = {
    core: "bg-[var(--accent)]/10 text-[var(--accent-light)]",
    "sfa/": "bg-emerald-500/10 text-emerald-400",
    "channelKart/": "bg-amber-500/10 text-amber-400",
  };
  const matchKey = Object.keys(colors).find((k) => ns.includes(k)) || "core";
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[matchKey] || colors.core}`}>
      {label || "features"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Feature Detail Panel
// ---------------------------------------------------------------------------

function FeatureDetailPanel({ detail }: { detail: FeatureDetail }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-white">{detail.name}</h2>
          <NamespaceBadge ns={detail.namespace} />
        </div>
        <p className="mt-1 font-mono text-xs text-[var(--muted)]">{detail.source_path}</p>
      </div>

      {/* LOB Overrides */}
      {detail.lob_overrides.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold text-white">LOB Overrides ({detail.lob_overrides.length})</h3>
          <div className="space-y-2">
            {detail.lob_overrides.map((o) => (
              <div key={o.lob_name} className="rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-[var(--accent-light)]">{o.lob_name}</span>
                  <span className="text-[10px] text-[var(--muted)]">{o.override_pages.length} pages</span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {o.override_pages.map((p) => (
                    <span key={p} className="rounded bg-[var(--card)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">{p}</span>
                  ))}
                </div>
                {o.notes && <p className="mt-1.5 text-[10px] text-[#52525b]">{o.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Jira History */}
      <div>
        <h3 className="mb-2 text-xs font-semibold text-white">Jira History ({detail.jira_history.length})</h3>
        <div className="space-y-1.5">
          {detail.jira_history.map((j) => (
            <div key={j.ticket_key} className="flex items-start gap-3 rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-3">
              <span className="shrink-0 rounded bg-[var(--accent)]/10 px-1.5 py-0.5 font-mono text-[10px] text-[var(--accent-light)]">{j.ticket_key}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white">{j.summary}</p>
                <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--muted)]">
                  <span className={j.status === "Done" ? "text-[var(--success)]" : "text-[var(--warning)]"}>{j.status}</span>
                  <span>&middot;</span>
                  <span>{j.ticket_type}</span>
                  {j.epic && <><span>&middot;</span><span>{j.epic}</span></>}
                </div>
              </div>
              <span className="shrink-0 text-[10px] text-[#52525b]">{j.linked_at}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Git File History */}
      <div>
        <h3 className="mb-2 text-xs font-semibold text-white">File Activity ({detail.git_file_history.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--card-border)] text-left text-[var(--muted)]">
                <th className="pb-2 pr-4 font-medium">File</th>
                <th className="pb-2 pr-4 font-medium">Last Modified</th>
                <th className="pb-2 pr-4 font-medium">Commits</th>
                <th className="pb-2 font-medium">Authors</th>
              </tr>
            </thead>
            <tbody>
              {detail.git_file_history.map((g) => (
                <tr key={g.file_path} className="border-b border-[var(--card-border)]/50">
                  <td className="py-2 pr-4 font-mono text-[var(--muted)]">
                    {g.file_path.split("/").pop()}
                  </td>
                  <td className="py-2 pr-4 text-white">{g.last_modified}</td>
                  <td className="py-2 pr-4 text-white">{g.commit_count}</td>
                  <td className="py-2 text-[var(--muted)]">{g.authors.map((a) => a.split("@")[0]).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RegistryPage() {
  const [features, setFeatures] = useState<Feature[]>(MOCK_FEATURES);
  const [selected, setSelected] = useState<FeatureDetail | null>(null);
  const [search, setSearch] = useState("");
  const [nsFilter, setNsFilter] = useState<string>("all");
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    api.getFeatures()
      .then((data) => { setFeatures(data); setIsLive(true); })
      .catch(() => {});
  }, []);

  const handleSelect = async (name: string) => {
    if (isLive) {
      try {
        const detail = await api.getFeature(name);
        setSelected(detail);
        return;
      } catch { /* fall through to mock */ }
    }
    // Mock detail
    setSelected({ ...MOCK_DETAIL, name, id: 0, namespace: features.find((f) => f.name === name)?.namespace || "", source_path: features.find((f) => f.name === name)?.source_path || "", updated_at: features.find((f) => f.name === name)?.updated_at || "" });
  };

  const namespaces = [...new Set(features.map((f) => f.namespace))];
  const filtered = features.filter((f) => {
    const matchSearch = f.name.toLowerCase().includes(search.toLowerCase());
    const matchNs = nsFilter === "all" || f.namespace === nsFilter;
    return matchSearch && matchNs;
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Feature Registry</h1>
          <p className="text-xs text-[var(--muted)]">{features.length} features across {namespaces.length} namespaces</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${isLive ? "bg-[var(--success)]" : "bg-[var(--warning)]"}`} />
          <span className="text-xs text-[var(--muted)]">{isLive ? "Live" : "Demo data"}</span>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Sidebar — Feature list */}
        <div className="w-72 shrink-0">
          {/* Search */}
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search features..."
            className="mb-3 w-full rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-3 py-2 text-xs text-white outline-none placeholder:text-[#3f3f46] focus:border-[var(--accent)]/40"
          />

          {/* Namespace filter */}
          <div className="mb-3 flex flex-wrap gap-1">
            <button
              onClick={() => setNsFilter("all")}
              className={`rounded-md px-2 py-1 text-[10px] transition-colors ${nsFilter === "all" ? "bg-[var(--accent)]/20 text-[var(--accent-light)]" : "text-[var(--muted)] hover:text-white"}`}
            >
              All
            </button>
            {namespaces.map((ns) => (
              <button
                key={ns}
                onClick={() => setNsFilter(ns)}
                className={`rounded-md px-2 py-1 text-[10px] transition-colors ${nsFilter === ns ? "bg-[var(--accent)]/20 text-[var(--accent-light)]" : "text-[var(--muted)] hover:text-white"}`}
              >
                {ns.replace("lib/", "").replace("features/", "").replace(/\/$/, "") || "core"}
              </button>
            ))}
          </div>

          {/* Feature list */}
          <div className="max-h-[calc(100vh-240px)] space-y-0.5 overflow-y-auto">
            {filtered.map((f) => (
              <button
                key={f.name}
                onClick={() => handleSelect(f.name)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                  selected?.name === f.name
                    ? "bg-[var(--accent)]/10 text-[var(--accent-light)]"
                    : "text-[var(--muted)] hover:bg-[var(--card)] hover:text-white"
                }`}
              >
                <span className="truncate">{f.name}</span>
                <NamespaceBadge ns={f.namespace} />
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="py-4 text-center text-xs text-[#52525b]">No features found</p>
            )}
          </div>
        </div>

        {/* Main content — Feature detail */}
        <div className="flex-1 rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-6">
          {selected ? (
            <FeatureDetailPanel detail={selected} />
          ) : (
            <div className="flex h-64 items-center justify-center text-sm text-[var(--muted)]">
              Select a feature to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
