import { createBrowserRouter, Navigate } from 'react-router-dom';

import { ConnectorsPage } from '@/modules/connectors';
import { RecordsPage } from '@/modules/records';
import { ChatPage } from '@/modules/chat/ChatPage';
import { AgentRunsPage } from '@/modules/agent_runs/AgentRunsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AppShell } from '@/shared/layout/AppShell';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'agents', element: <AgentRunsPage /> },
      { path: 'connectors', element: <ConnectorsPage /> },
      { path: 'records', element: <RecordsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
