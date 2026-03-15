"use client";

import { useEffect, useState } from "react";
import { api, type DashboardStats } from "@/lib/api";

// ---------------------------------------------------------------------------
// Mock data for demo (used when API is unavailable)
// ---------------------------------------------------------------------------

const MOCK_STATS: DashboardStats = {
  total_features: 178,
  total_lobs: 35,
  total_reviews: 47,
  reviews_this_month: 12,
  recommendations: { APPROVE: 8, REQUEST_CHANGES: 3, COMMENT: 1 },
  top_features: [
    { name: "order_checkout", review_count: 8 },
    { name: "cart", review_count: 6 },
    { name: "sfa_attendance", review_count: 5 },
    { name: "catalogue", review_count: 4 },
    { name: "payment_dashboard", review_count: 3 },
    { name: "auth", review_count: 3 },
    { name: "banner_v2", review_count: 2 },
    { name: "ck_consumer_promo", review_count: 2 },
  ],
  stale_features: [
    { name: "about", last_change: "2025-09-15" },
    { name: "app_update", last_change: "2025-10-02" },
    { name: "biometric_auth", last_change: "2025-08-20" },
    { name: "buckets", last_change: "2025-11-01" },
    { name: "digivyapar_coupons", last_change: "2025-07-10" },
  ],
  recent_reviews: [
    { id: 47, repo: "org/channelkart-flutter", pr_number: 1892, branch: "feat/COCA-912-cart-total-fix", jira_key: "COCA-912", recommendation: "REQUEST_CHANGES", issues_found: 4, critical_count: 1, created_at: "2026-03-14T10:22:00Z", features: ["cart", "order_checkout"] },
    { id: 46, repo: "org/channelkart-flutter", pr_number: 1889, branch: "feat/CSLC-440-attendance-gps", jira_key: "CSLC-440", recommendation: "APPROVE", issues_found: 1, critical_count: 0, created_at: "2026-03-13T16:05:00Z", features: ["sfa_attendance"] },
    { id: 45, repo: "org/channelkart-flutter", pr_number: 1885, branch: "fix/COCA-889-cart-flicker", jira_key: "COCA-889", recommendation: "APPROVE", issues_found: 0, critical_count: 0, created_at: "2026-03-12T09:30:00Z", features: ["cart"] },
    { id: 44, repo: "org/channelkart-flutter", pr_number: 1880, branch: "feat/CT-321-catalogue-v2", jira_key: "CT-321", recommendation: "APPROVE", issues_found: 2, critical_count: 0, created_at: "2026-03-11T14:18:00Z", features: ["catalogue"] },
    { id: 43, repo: "org/channelkart-flutter", pr_number: 1876, branch: "fix/CSLC-438-payment-crash", jira_key: "CSLC-438", recommendation: "REQUEST_CHANGES", issues_found: 3, critical_count: 2, created_at: "2026-03-10T11:45:00Z", features: ["payment_dashboard"] },
    { id: 42, repo: "org/channelkart-flutter", pr_number: 1870, branch: "feat/UI-102-banner-redesign", jira_key: "UI-102", recommendation: "APPROVE", issues_found: 1, critical_count: 0, created_at: "2026-03-08T08:12:00Z", features: ["banner_v2"] },
  ],
};

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function StatCard({ label, value, subtitle }: { label: string; value: string | number; subtitle?: string }) {
  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <p className="mb-1 text-xs text-[var(--muted)]">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtitle && <p className="mt-1 text-xs text-[var(--muted)]">{subtitle}</p>}
    </div>
  );
}

function RecommendationBadge({ rec }: { rec: string }) {
  const colors: Record<string, string> = {
    APPROVE: "bg-[var(--success)]/10 text-[var(--success)]",
    REQUEST_CHANGES: "bg-[var(--danger)]/10 text-[var(--danger)]",
    COMMENT: "bg-[var(--warning)]/10 text-[var(--warning)]",
  };
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-medium ${colors[rec] || "bg-[var(--card)] text-[var(--muted)]"}`}>
      {rec.replace("_", " ")}
    </span>
  );
}

function BarChart({ data, maxValue }: { data: { label: string; value: number }[]; maxValue: number }) {
  return (
    <div className="space-y-2">
      {data.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="w-36 shrink-0 truncate text-xs text-[var(--muted)]">{item.label}</span>
          <div className="flex-1">
            <div className="h-5 w-full overflow-hidden rounded-md bg-[var(--background)]">
              <div
                className="h-full rounded-md bg-[var(--accent)]/30"
                style={{ width: `${Math.max((item.value / maxValue) * 100, 4)}%` }}
              />
            </div>
          </div>
          <span className="w-6 text-right text-xs font-medium text-white">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>(MOCK_STATS);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    api.getDashboard()
      .then((data) => {
        setStats(data);
        setIsLive(true);
      })
      .catch(() => {
        // Use mock data
      });
  }, []);

  const recTotal = Object.values(stats.recommendations).reduce((a, b) => a + b, 0) || 1;
  const approveRate = Math.round(((stats.recommendations["APPROVE"] || 0) / recTotal) * 100);
  const maxReviews = Math.max(...stats.top_features.map((f) => f.review_count), 1);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-xs text-[var(--muted)]">PR Reviewer overview and analytics</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${isLive ? "bg-[var(--success)]" : "bg-[var(--warning)]"}`} />
          <span className="text-xs text-[var(--muted)]">{isLive ? "Live" : "Demo data"}</span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Features" value={stats.total_features} subtitle="Across 3 namespaces" />
        <StatCard label="Lines of Business" value={stats.total_lobs} subtitle="With override tracking" />
        <StatCard label="Reviews This Month" value={stats.reviews_this_month} subtitle={`${stats.total_reviews} total`} />
        <StatCard label="Approval Rate" value={`${approveRate}%`} subtitle={`${stats.reviews_this_month} reviews this month`} />
      </div>

      {/* Two column layout */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Top features */}
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
          <h3 className="mb-4 text-sm font-semibold text-white">Most Reviewed Features</h3>
          <BarChart
            data={stats.top_features.map((f) => ({ label: f.name, value: f.review_count }))}
            maxValue={maxReviews}
          />
        </div>

        {/* Recommendation breakdown */}
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
          <h3 className="mb-4 text-sm font-semibold text-white">Recommendation Breakdown</h3>
          <div className="mb-6 space-y-3">
            {Object.entries(stats.recommendations).map(([rec, count]) => (
              <div key={rec} className="flex items-center justify-between">
                <RecommendationBadge rec={rec} />
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-[var(--background)]">
                    <div
                      className={`h-full rounded-full ${rec === "APPROVE" ? "bg-[var(--success)]" : rec === "REQUEST_CHANGES" ? "bg-[var(--danger)]" : "bg-[var(--warning)]"}`}
                      style={{ width: `${(count / recTotal) * 100}%` }}
                    />
                  </div>
                  <span className="w-6 text-right text-xs text-white">{count}</span>
                </div>
              </div>
            ))}
          </div>

          <h3 className="mb-3 text-sm font-semibold text-white">Stale Features</h3>
          <p className="mb-2 text-[10px] text-[var(--muted)]">No commits in 90+ days</p>
          <div className="space-y-1">
            {stats.stale_features.map((f) => (
              <div key={f.name} className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs hover:bg-[var(--background)]">
                <span className="text-[var(--muted)]">{f.name}</span>
                <span className="text-[10px] text-[#52525b]">{f.last_change || "never"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent reviews */}
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
        <h3 className="mb-4 text-sm font-semibold text-white">Recent Reviews</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--card-border)] text-left text-[var(--muted)]">
                <th className="pb-2 pr-4 font-medium">PR</th>
                <th className="pb-2 pr-4 font-medium">Branch</th>
                <th className="pb-2 pr-4 font-medium">Jira</th>
                <th className="pb-2 pr-4 font-medium">Features</th>
                <th className="pb-2 pr-4 font-medium">Issues</th>
                <th className="pb-2 pr-4 font-medium">Result</th>
                <th className="pb-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_reviews.map((r) => (
                <tr key={r.id} className="border-b border-[var(--card-border)]/50 hover:bg-[var(--background)]">
                  <td className="py-2.5 pr-4 font-mono text-white">#{r.pr_number}</td>
                  <td className="py-2.5 pr-4 max-w-[180px] truncate text-[var(--muted)]">{r.branch}</td>
                  <td className="py-2.5 pr-4">
                    <span className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 font-mono text-[10px] text-[var(--accent-light)]">
                      {r.jira_key}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-[var(--muted)]">{r.features.join(", ")}</td>
                  <td className="py-2.5 pr-4">
                    <span className="text-white">{r.issues_found}</span>
                    {r.critical_count > 0 && (
                      <span className="ml-1 text-[10px] text-[var(--danger)]">({r.critical_count} critical)</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4"><RecommendationBadge rec={r.recommendation} /></td>
                  <td className="py-2.5 text-[var(--muted)]">
                    {new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
