import type { ReactNode } from 'react';

interface StatusBadgeProps {
  tone: 'success' | 'warning' | 'error' | 'muted' | 'accent';
  children: ReactNode;
}

const TONE_CLASS = {
  success: 'bg-success/15 text-success border-success/30',
  warning: 'bg-warning/15 text-warning border-warning/40',
  error: 'bg-error/15 text-error border-error/30',
  muted: 'bg-bg-subtle text-muted border-border',
  accent: 'bg-accent/15 text-accent border-accent/30',
} as const;

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}
