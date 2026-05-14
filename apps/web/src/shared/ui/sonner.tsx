import { Toaster as SonnerToaster, type ToasterProps } from 'sonner';
import { useThemeStore } from '@/shared/store/theme';

export function Toaster(props: ToasterProps) {
  const resolved = useThemeStore((s) => s.resolvedTheme);
  return (
    <SonnerToaster
      theme={resolved}
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-surface group-[.toaster]:text-fg group-[.toaster]:border group-[.toaster]:border-border group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-fg-muted',
          actionButton: 'group-[.toast]:bg-primary group-[.toast]:text-primary-fg',
          cancelButton: 'group-[.toast]:bg-surface-elevated group-[.toast]:text-fg-muted',
        },
      }}
      {...props}
    />
  );
}
