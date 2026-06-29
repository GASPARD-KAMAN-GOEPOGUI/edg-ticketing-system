import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/app/triage")({
  beforeLoad: () => {
    throw redirect({ to: "/app/queue", search: { tab: "qualify" } });
  },
  component: () => null,
});
