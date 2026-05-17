import { createBrowserRouter, Navigate } from 'react-router-dom';

import { ConnectorsPage } from '@/modules/connectors';
import { RecordsPage } from '@/modules/records';
import { ChatPage } from '@/modules/chat/ChatPage';
import { AgentRunsPage } from '@/modules/agent_runs/AgentRunsPage';
import { LandingPage } from '@/pages/LandingPage';
import { StartPage } from '@/pages/StartPage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ProtectedRoute } from '@/modules/auth';
import { AppShell } from '@/shared/layout/AppShell';

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  { path: '/start', element: <StartPage /> },
  {
    path: '/onboarding',
    element: (
      <ProtectedRoute>
        <OnboardingPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: 'chat', element: <ChatPage /> },
      { path: 'agents', element: <AgentRunsPage /> },
      { path: 'connectors', element: <ConnectorsPage /> },
      { path: 'records', element: <RecordsPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
  { path: '/index', element: <Navigate to="/" replace /> },
]);
