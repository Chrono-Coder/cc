import { Suspense } from "react";
import { api, type GithubPR, type GithubReviews } from "@/lib/api";
import { getProjects } from "@/lib/serverData";
import DashboardClient from "@/components/DashboardClient";
import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { timeAgo } from "@/lib/fmt";
import { TermPanel } from "@/components/ui/term-panel";

function PRRow({ pr, role }: { pr: GithubPR; role: "reviewer" | "author" }) {
  const parts = pr.repo.split("/");
  const short = parts[parts.length - 1];

  return (
    <a
      href={pr.html_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group relative flex items-center gap-3 py-2.5 pl-3 -ml-3 border-b border-border/30 last:border-0"
    >
      <span
        aria-hidden
        className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-cyan-400 opacity-0 scale-y-50 group-hover:opacity-100 group-hover:scale-y-100 transition-all duration-200 shadow-[0_0_8px_color-mix(in_oklch,var(--cc-cyan-400)_60%,transparent)]"
      />
      <img src={pr.author_avatar} alt={pr.author} className="w-5 h-5 rounded-full shrink-0 opacity-60 group-hover:opacity-100 transition-opacity" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-muted-foreground group-hover:text-foreground transition-colors truncate">
          {pr.draft && <span className="text-muted-foreground/70 mr-1">[Draft]</span>}
          {pr.title}
        </p>
      </div>
      <span className="text-[10px] text-muted-foreground/70 font-mono shrink-0">{short}</span>
      <span className="text-[10px] text-muted-foreground/60 shrink-0" suppressHydrationWarning>{timeAgo(pr.updated_at)}</span>
      {role === "reviewer" && (
        <span className="text-[10px] text-violet-400/70 shrink-0">review</span>
      )}
      <ArrowTopRightOnSquareIcon className="w-3 h-3 text-muted-foreground/20 group-hover:text-muted-foreground transition-colors shrink-0" />
    </a>
  );
}

async function ReviewsSection() {
  let reviews: GithubReviews | null = null;
  try { reviews = await api.githubReviews(); } catch {}

  const needsReview = reviews?.needs_review ?? [];
  const myPRs = reviews?.my_prs ?? [];
  const total = needsReview.length + myPRs.length;

  if (reviews === null) return null;
  if (total === 0) return null;

  return (
    <TermPanel
      title="code reviews"
      right={<span className="text-[10px] text-muted-foreground/70 font-mono tabular-nums">{total} open</span>}
      className="mt-6"
      bodyClassName="p-4"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {needsReview.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground/50 mb-3">Needs your review</p>
            {needsReview.map((pr) => <PRRow key={pr.id} pr={pr} role="reviewer" />)}
          </div>
        )}
        {myPRs.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground/50 mb-3">Your open PRs</p>
            {myPRs.map((pr) => <PRRow key={pr.id} pr={pr} role="author" />)}
          </div>
        )}
      </div>
    </TermPanel>
  );
}

function ReviewsSkeleton() {
  return (
    <TermPanel title="code reviews" className="mt-6" bodyClassName="p-4">
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 py-2.5">
            <div className="w-5 h-5 rounded-full bg-muted animate-pulse" />
            <div className="flex-1 h-3 bg-muted rounded animate-pulse" />
            <div className="w-12 h-3 bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    </TermPanel>
  );
}

export default async function HomePage() {
  let projects: Awaited<ReturnType<typeof getProjects>> = [];
  try { projects = getProjects(); } catch { /* DB unavailable → empty dashboard */ }
  return (
    <>
      <DashboardClient projects={projects} />
      <Suspense fallback={<ReviewsSkeleton />}>
        <ReviewsSection />
      </Suspense>
    </>
  );
}
