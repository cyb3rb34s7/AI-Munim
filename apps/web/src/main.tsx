import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';

import { App } from '@/app';
import { queryClient } from '@/shared/api';

import './styles/globals.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  // Fail loud — index.html guarantees this element exists.
  throw new Error('Root element #root not found in index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
