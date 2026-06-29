import { createFileRoute, redirect } from "@tanstack/react-router";
import { Route as KnowledgeRoute } from "./app.knowledge";

export const Route = createFileRoute("/help")({
  beforeLoad: () => { throw redirect({ to: "/app/knowledge" as never, replace: true }); },
  component: () => null,
});
