import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[background-color,box-shadow,transform] duration-150 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-fg shadow-sm hover:bg-primary-hover',
        secondary:
          'bg-surface-elevated text-fg border border-border hover:bg-surface-subtle',
        ghost: 'text-fg hover:bg-surface-elevated',
        destructive: 'bg-destructive text-white hover:opacity-90',
        pop: 'bg-pop text-white hover:opacity-90',
      },
      size: {
        sm: 'h-8 px-3',
        md: 'h-10 px-4',
        lg: 'h-11 px-5 text-base',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  },
);
Button.displayName = 'Button';
