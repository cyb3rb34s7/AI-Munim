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
      className={`rounded-lg border border-border bg-bg-subtle/30 p-6 ${className ?? ''}`.trim()}
    >
      {(title || trailing) && (
        <header className="mb-4 flex items-center justify-between">
          {title && <h2 className="text-base font-medium">{title}</h2>}
          {trailing}
        </header>
      )}
      {children}
    </section>
  );
}
