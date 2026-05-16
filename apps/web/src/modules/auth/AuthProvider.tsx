import { createContext, useContext, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Loader } from '@/shared/components';

import type { CurrentUser } from './api/client';
import { useCurrentUser } from './hooks/useAuth';

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useCurrentUser();
  return (
    <AuthContext.Provider value={{ user: data ?? null, isLoading }}>{children}</AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuthContext must be used inside <AuthProvider>.');
  }
  return ctx;
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuthContext();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader label="Loading…" />
      </div>
    );
  }
  if (user === null) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
