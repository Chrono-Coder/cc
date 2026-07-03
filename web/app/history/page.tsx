import { api, type HistoryEntry } from "@/lib/api";
import HistoryClient from "@/components/HistoryClient";

async function getEntries(days: number): Promise<HistoryEntry[]> {
  try {
    return await api.history(days);
  } catch {
    return [];
  }
}

export default async function HistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string; page?: string }>;
}) {
  const { days: daysParam, page: pageParam } = await searchParams;
  const days = Number(daysParam ?? 30);
  const page = Math.max(1, Number(pageParam ?? 1));
  const entries = await getEntries(days);

  return (
    <div className="">
      <HistoryClient entries={entries} days={days} page={page} />
    </div>
  );
}
