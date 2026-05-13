export function NotFoundPage() {
  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium text-fg">Page not found</p>
      <p className="mt-1 text-xs text-muted">
        Try Overview, Connectors, or Records from the nav above.
      </p>
    </div>
  );
}
