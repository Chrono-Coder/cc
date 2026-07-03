import { api, type TimesheetSummary } from "@/lib/api";
import TimesheetClient from "@/components/TimesheetClient";

async function getSummary(days: number): Promise<TimesheetSummary[]> {
  try {
    return await api.timesheetSummary(days);
  } catch {
    return [];
  }
}

export default async function TimesheetPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days: daysParam } = await searchParams;
  const days = Number(daysParam ?? 30);
  const summary = await getSummary(days);

  return (
    <div className="">
      <TimesheetClient summary={summary} days={days} />
    </div>
  );
}
