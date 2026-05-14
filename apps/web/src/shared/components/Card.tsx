import type { ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, trailing, children, className }: CardProps) {
  return (
    <section
      className={`rounded-lg border border-border bg-surface p-6 shadow-sm ${className ?? ''}`.trim()}
    >
      {(title || trailing) && (
        <header className="mb-4 flex items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold tracking-tight text-fg">{title}</h2>}
          {trailing}
        </header>
      )}
      {children}
    </section>
  );
}
