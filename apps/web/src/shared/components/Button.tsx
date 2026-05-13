import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  loading?: boolean;
  children: ReactNode;
}

const VARIANT_CLASS = {
  primary: 'bg-primary text-primary-fg hover:opacity-90 disabled:opacity-50',
  secondary: 'border border-border bg-bg-subtle text-fg hover:bg-bg-subtle/70',
  ghost: 'text-fg hover:bg-bg-subtle',
} as const;

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      {...rest}
      disabled={isDisabled}
      className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className ?? ''}`.trim()}
    >
      {loading && (
        <span
          className="h-3 w-3 animate-spin rounded-full border-2 border-current border-r-transparent"
          aria-hidden
        />
      )}
      {children}
    </button>
  );
}
