import { api, type Workspace } from "@/lib/api";
import { getDb } from "@/lib/db";
import WorkspacesClient, { type VersionOpt } from "@/components/WorkspacesClient";

// Reads the live SQLite DB per-request — never prerender at build (the DB dir
// doesn't exist on the build machine).
export const dynamic = "force-dynamic";

async function getWorkspaces(): Promise<Workspace[]> {
  try {
    return await api.workspaces();
  } catch {
    return [];
  }
}

function getVersions(): VersionOpt[] {
  try {
    return getDb()
      .prepare("SELECT id, name FROM version ORDER BY name")
      .all() as VersionOpt[];
  } catch {
    return [];
  }
}

export default async function WorkspacesPage() {
  const workspaces = await getWorkspaces();
  const versions = getVersions();

  return <WorkspacesClient initialWorkspaces={workspaces} versions={versions} />;
}
