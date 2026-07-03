import SkillsClient from "@/components/SkillsClient";

export default function SkillsPage() {
  // Page is fully client-side: filters drive every fetch and we want immediate
  // feedback when the user changes a date range, repo, or symbol search.
  return <SkillsClient />;
}
