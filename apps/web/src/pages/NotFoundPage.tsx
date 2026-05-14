export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-lg border border-dashed border-border bg-surface p-10 text-center">
        <p className="text-base font-semibold text-fg">Page not found</p>
        <p className="mt-1.5 text-sm text-fg-muted">
          Try Chat, Agents, Connectors, or Records from the sidebar.
        </p>
      </div>
    </div>
  );
}
