import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { forwardRef, type ComponentPropsWithoutRef } from 'react';
import { cn } from '@/shared/utils/cn';

export const Avatar = forwardRef<
  HTMLSpanElement,
  ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Root
    ref={ref}
    className={cn('relative flex shrink-0 overflow-hidden rounded-full', className)}
    {...props}
  />
));
Avatar.displayName = 'Avatar';

export const AvatarImage = forwardRef<
  HTMLImageElement,
  ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Image ref={ref} className={cn('aspect-square h-full w-full', className)} {...props} />
));
AvatarImage.displayName = 'AvatarImage';

export const AvatarFallback = forwardRef<
  HTMLSpanElement,
  ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Fallback
    ref={ref}
    className={cn('flex h-full w-full items-center justify-center', className)}
    {...props}
  />
));
AvatarFallback.displayName = 'AvatarFallback';
