const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface Feature {
  id: number;
  name: string;
  namespace: string;
  source_path: string;
  updated_at: string;
}

export interface FeatureDetail extends Feature {
  jira_history: {
    ticket_key: string;
    summary: string;
    ticket_type: string;
    status: string;
    epic: string;
    branch: string;
    linked_at: string;
  }[];
  git_file_history: {
    file_path: string;
    last_modified: string;
    commit_count: number;
    authors: string[];
  }[];
  lob_overrides: {
    lob_name: string;
    override_pages: string[];
    notes: string;
  }[];
}

export interface Review {
  id: number;
  repo: string;
  pr_number: number;
  branch: string;
  jira_key: string;
  recommendation: string;
  issues_found: number;
  critical_count: number;
  created_at: string;
  features: string[];
}

export interface DashboardStats {
  total_features: number;
  total_lobs: number;
  total_reviews: number;
  reviews_this_month: number;
  recommendations: Record<string, number>;
  top_features: { name: string; review_count: number }[];
  stale_features: { name: string; last_change: string }[];
  recent_reviews: Review[];
}

export interface Lob {
  id: number;
  name: string;
  display_name: string;
}

export const api = {
  getDashboard: () => apiFetch<DashboardStats>("/api/dashboard"),
  getFeatures: () => apiFetch<Feature[]>("/api/features"),
  getFeature: (name: string) => apiFetch<FeatureDetail>(`/api/features/${name}`),
  getLobs: () => apiFetch<Lob[]>("/api/lobs"),
  getReviews: (limit = 50) => apiFetch<Review[]>(`/api/reviews?limit=${limit}`),
  queryKB: (question: string, useLive = true) =>
    apiFetch<{ answer: string }>("/api/kb/query", {
      method: "POST",
      body: JSON.stringify({ question, use_live: useLive }),
    }),
};
