import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface EmptyStateAction {
  label: string;
  href: string;
}

interface EmptyStateProps {
  title: string;
  hint?: ReactNode;
  action?: EmptyStateAction;
}

export function EmptyState({ title, hint, action }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface p-10 text-center">
      <p className="text-sm font-medium text-fg">{title}</p>
      {hint && <p className="mt-1 text-xs text-fg-muted">{hint}</p>}
      {action && (
        <Link
          to={action.href}
          className="mt-4 inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-fg shadow-sm hover:bg-primary-hover"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
