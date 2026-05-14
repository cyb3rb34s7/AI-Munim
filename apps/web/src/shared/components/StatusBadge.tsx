import type { ReactNode } from 'react';

interface StatusBadgeProps {
  tone: 'success' | 'warning' | 'error' | 'muted' | 'accent';
  children: ReactNode;
}

const TONE_CLASS = {
  success: 'bg-success/15 text-success border-success/30',
  warning: 'bg-warning/15 text-warning border-warning/40',
  error: 'bg-destructive/15 text-destructive border-destructive/30',
  muted: 'bg-surface-subtle text-fg-muted border-border',
  accent: 'bg-accent text-accent-fg border-transparent',
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
