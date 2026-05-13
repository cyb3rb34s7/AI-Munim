import { createBrowserRouter } from 'react-router-dom';

import { ConnectorsPage } from '@/modules/connectors';
import { RecordsPage } from '@/modules/records';
import { IndexPage } from '@/pages/IndexPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AppShell } from '@/shared/components';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <IndexPage /> },
      { path: 'connectors', element: <ConnectorsPage /> },
      { path: 'records', element: <RecordsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
