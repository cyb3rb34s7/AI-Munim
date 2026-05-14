interface LoaderProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASS = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
} as const;

export function Loader({ label, size = 'md' }: LoaderProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-2 text-fg-muted"
    >
      <span
        className={`${SIZE_CLASS[size]} animate-spin rounded-full border-current border-r-transparent`}
        aria-hidden
      />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
