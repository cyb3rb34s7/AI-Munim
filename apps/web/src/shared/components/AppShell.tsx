import { Outlet } from 'react-router-dom';

import { NavLink } from './NavLink';

export function AppShell() {
  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="border-b border-border bg-bg-subtle/40 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div>
            <h1 className="text-base font-semibold tracking-tight">AI-Munim</h1>
            <p className="text-xs text-muted">AI employee for D2C brands · v0</p>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink to="/">Overview</NavLink>
            <NavLink to="/connectors">Connectors</NavLink>
            <NavLink to="/records">Records</NavLink>
            <NavLink to="/chat" disabled>
              Chat · soon
            </NavLink>
            <NavLink to="/agent" disabled>
              Agent · soon
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
