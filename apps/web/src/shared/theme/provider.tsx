import { useEffect, type ReactNode } from 'react';

import { useThemeStore } from '@/shared/store/theme';

const DARK_CLASS = 'dark';
const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useThemeStore((s) => s.theme);
  const setResolvedTheme = useThemeStore((s) => s.setResolvedTheme);

  useEffect(() => {
    const html = document.documentElement;
    const apply = (resolved: 'light' | 'dark') => {
      html.classList.toggle(DARK_CLASS, resolved === 'dark');
      setResolvedTheme(resolved);
    };

    if (theme === 'system') {
      const media = window.matchMedia(SYSTEM_DARK_QUERY);
      apply(media.matches ? 'dark' : 'light');
      const handler = (event: MediaQueryListEvent) => apply(event.matches ? 'dark' : 'light');
      media.addEventListener('change', handler);
      return () => media.removeEventListener('change', handler);
    }

    apply(theme);
    return undefined;
  }, [theme, setResolvedTheme]);

  return <>{children}</>;
}
