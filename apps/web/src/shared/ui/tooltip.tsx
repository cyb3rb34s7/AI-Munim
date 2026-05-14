import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { forwardRef, type ComponentPropsWithoutRef } from 'react';
import { cn } from '@/shared/utils/cn';

export const TooltipProvider = ({
  delayDuration = 200,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Provider>) => (
  <TooltipPrimitive.Provider delayDuration={delayDuration} {...props}>
    {children}
  </TooltipPrimitive.Provider>
);

export const Tooltip = ({
  children,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Root>) => (
  <TooltipPrimitive.Root {...props}>
    <TooltipProvider>{children}</TooltipProvider>
  </TooltipPrimitive.Root>
);

export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 overflow-hidden rounded-md border border-border bg-surface-elevated px-3 py-2 text-xs text-fg shadow-md',
        'data-[state=delayed-open]:animate-in data-[state=closed]:animate-out',
        'data-[state=delayed-open]:fade-in-0 data-[state=closed]:fade-out-0',
        'data-[state=delayed-open]:zoom-in-95 data-[state=closed]:zoom-out-95',
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = 'TooltipContent';
