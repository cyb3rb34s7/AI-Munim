import { NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquareText,
  BotMessageSquare,
  Plug,
  Database,
  SunMedium,
  MoonStar,
  Monitor,
  LogOut,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/shared/utils/cn';
import { useThemeStore, type ThemePreference } from '@/shared/store/theme';
import { Button } from '@/shared/ui';
import { useAuthContext, useLogout } from '@/modules/auth';

const navItems = [
  { to: '/chat', label: 'Chat', icon: MessageSquareText },
  { to: '/agents', label: 'Agents', icon: BotMessageSquare },
  { to: '/connectors', label: 'Connectors', icon: Plug },
  { to: '/records', label: 'Records', icon: Database },
] as const;

const NEXT_THEME: Record<ThemePreference, ThemePreference> = {
  light: 'dark',
  dark: 'system',
  system: 'light',
};

const THEME_ICON: Record<ThemePreference, typeof SunMedium> = {
  light: SunMedium,
  dark: MoonStar,
  system: Monitor,
};

function initials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return 'D';
  const parts = trimmed.split(/\s+/);
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Sidebar() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const ThemeIcon = THEME_ICON[theme];
  const { user } = useAuthContext();
  const logout = useLogout();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout.mutateAsync();
    navigate('/', { replace: true });
  };

  return (
    <aside className="flex h-screen w-[248px] flex-col bg-sidebar-bg text-sidebar-fg p-4 gap-2">
      <div className="flex items-center gap-3 px-2 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-md bg-primary text-primary-fg font-bold">
          M
        </div>
        <div>
          <div className="text-base font-semibold tracking-tight">Munim</div>
          <div className="text-xs text-sidebar-muted">AI for D2C</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 mt-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-hover text-sidebar-fg'
                  : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-primary"
                  />
                )}
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2">
        {user && (
          <div className="flex items-center gap-3 rounded-md bg-sidebar-hover/40 px-3 py-2.5">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/20 text-primary-fg text-xs font-semibold">
              {initials(user.display_name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-sidebar-fg">
                {user.display_name}
              </div>
              <div className="truncate text-[11px] text-sidebar-muted">Demo workspace</div>
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setTheme(NEXT_THEME[theme])}
          className="text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg justify-start"
        >
          <ThemeIcon className="h-4 w-4" />
          Theme: {theme}
        </Button>
        {user && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            disabled={logout.isPending}
            className="text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg justify-start"
          >
            <LogOut className="h-4 w-4" />
            {logout.isPending ? 'Signing out…' : 'Sign out'}
          </Button>
        )}
      </div>
    </aside>
  );
}
