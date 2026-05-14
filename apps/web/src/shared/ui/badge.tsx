import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight',
  {
    variants: {
      variant: {
        default: 'bg-accent text-accent-fg',
        outline: 'border border-border text-fg-muted',
        success: 'bg-success/15 text-success',
        warning: 'bg-warning/15 text-warning',
        destructive: 'bg-destructive/15 text-destructive',
        pop: 'bg-pop/15 text-pop',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
  ),
);
Badge.displayName = 'Badge';
