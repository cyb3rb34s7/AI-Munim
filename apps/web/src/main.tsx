import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';

import { router } from '@/router';
import { queryClient } from '@/shared/api';
import { ThemeProvider } from '@/shared/theme';
import { Toaster } from '@/shared/ui';

import './styles/globals.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found in index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster position="bottom-right" />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
