/**
 * Client-side fetch utility for cc companion.
 *
 * Centralizes error handling, abort signals, and response parsing
 * so client components don't each re-implement fetch boilerplate.
 */

type FetchOptions = {
  signal?: AbortSignal;
};

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function clientFetch<T>(path: string, opts?: FetchOptions): Promise<T> {
  const res = await fetch(path, { cache: "no-store", signal: opts?.signal });
  if (!res.ok) throw new ApiError(res.status, `API error: ${res.status}`);
  return res.json();
}

export const clientApi = {
  projects: (opts?: FetchOptions) => clientFetch<any[]>("/api/projects", opts),
  versions: (opts?: FetchOptions) => clientFetch<any[]>("/api/versions", opts),
  workspaces: (opts?: FetchOptions) => clientFetch<any[]>("/api/workspaces", opts),
  timesheet: (days = 30, opts?: FetchOptions) => clientFetch<any[]>(`/api/timesheet?days=${days}`, opts),
  timesheetSummary: (days = 30, opts?: FetchOptions) => clientFetch<any[]>(`/api/timesheet/summary?days=${days}`, opts),
  history: (days = 30, opts?: FetchOptions) => clientFetch<any[]>(`/api/history?days=${days}`, opts),
  health: (opts?: FetchOptions) => clientFetch<any>("/api/health", opts),
  databases: (opts?: FetchOptions) => clientFetch<any[]>("/api/databases", opts),
  githubReviews: (opts?: FetchOptions) => clientFetch<any>("/api/github/reviews", opts),
};

export { ApiError };
