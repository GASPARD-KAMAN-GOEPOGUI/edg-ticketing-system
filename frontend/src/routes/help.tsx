import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/help")({
  beforeLoad: () => { throw redirect({ to: "/knowledge", replace: true }); },
  component: () => null,
});
