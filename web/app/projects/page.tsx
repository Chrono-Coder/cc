import { api, type Project } from "@/lib/api";
import ProjectsGridClient from "@/components/ProjectsGridClient";

async function getProjects(): Promise<Project[]> {
  try {
    return await api.projects();
  } catch {
    return [];
  }
}

export default async function ProjectsPage() {
  const projects = await getProjects();

  if (projects.length === 0) {
    return (
      <div className=" flex flex-col items-center justify-center py-40 text-center gap-4">
        <p className="text-4xl font-normal text-foreground/70 tracking-tight">no projects</p>
        <p className="text-sm text-muted-foreground/60">
          Make sure <span className="font-mono text-muted-foreground">cc web</span> is running.
        </p>
      </div>
    );
  }

  return <ProjectsGridClient initialProjects={projects} />;
}
