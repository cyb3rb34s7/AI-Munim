import { NavLink as RouterNavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

interface NavLinkProps {
  to: string;
  disabled?: boolean;
  children: ReactNode;
}

const baseClass = 'rounded-md px-3 py-1.5 text-sm font-medium transition-colors';
const idleClass = 'text-muted hover:text-fg hover:bg-bg-subtle';
const activeClass = 'text-fg bg-bg-subtle';
const disabledClass = 'cursor-not-allowed text-muted/50';

export function NavLink({ to, disabled = false, children }: NavLinkProps) {
  if (disabled) {
    return <span className={`${baseClass} ${disabledClass}`}>{children}</span>;
  }
  return (
    <RouterNavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) => `${baseClass} ${isActive ? activeClass : idleClass}`}
    >
      {children}
    </RouterNavLink>
  );
}
