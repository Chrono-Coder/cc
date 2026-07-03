import { redirect } from "next/navigation";

export default function VersionsRedirect() {
  redirect("/workspaces");
}
