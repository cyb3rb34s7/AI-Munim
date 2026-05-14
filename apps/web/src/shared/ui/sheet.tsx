import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { forwardRef, type ComponentPropsWithoutRef, type HTMLAttributes } from 'react';
import { cn } from '@/shared/utils/cn';

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

const SheetOverlay = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof Dialog.Overlay>>(
  ({ className, ...props }, ref) => (
    <Dialog.Overlay
      ref={ref}
      className={cn(
        'fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
        className,
      )}
      {...props}
    />
  ),
);
SheetOverlay.displayName = 'SheetOverlay';

export const SheetContent = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof Dialog.Content>>(
  ({ className, children, ...props }, ref) => (
    <Dialog.Portal>
      <SheetOverlay />
      <Dialog.Content
        ref={ref}
        className={cn(
          'fixed right-0 top-0 z-50 flex h-full w-full max-w-[560px] flex-col gap-0 border-l border-border bg-surface shadow-xl',
          'data-[state=open]:animate-in data-[state=closed]:animate-out',
          'data-[state=open]:slide-in-from-right-12 data-[state=closed]:slide-out-to-right-12',
          'duration-300',
          className,
        )}
        {...props}
      >
        {children}
        <Dialog.Close className="absolute right-5 top-5 rounded-md text-fg-muted transition-colors hover:bg-surface-elevated hover:text-fg p-1.5">
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  ),
);
SheetContent.displayName = 'SheetContent';

export const SheetHeader = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-1.5 border-b border-border p-6', className)} {...props} />
);

export const SheetTitle = forwardRef<HTMLHeadingElement, ComponentPropsWithoutRef<typeof Dialog.Title>>(
  ({ className, ...props }, ref) => (
    <Dialog.Title
      ref={ref}
      className={cn('text-lg font-semibold tracking-tight text-fg', className)}
      {...props}
    />
  ),
);
SheetTitle.displayName = 'SheetTitle';

export const SheetDescription = forwardRef<
  HTMLParagraphElement,
  ComponentPropsWithoutRef<typeof Dialog.Description>
>(({ className, ...props }, ref) => (
  <Dialog.Description ref={ref} className={cn('text-sm text-fg-muted', className)} {...props} />
));
SheetDescription.displayName = 'SheetDescription';
