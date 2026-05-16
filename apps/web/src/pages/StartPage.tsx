import { Link, Navigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { StartDemoForm, useAuthContext } from '@/modules/auth';

export function StartPage() {
  const { user, isLoading } = useAuthContext();
  if (isLoading) return null;
  if (user !== null) return <Navigate to="/chat" replace />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-fg">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface-elevated p-8 shadow-sm">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg"
        >
          <ArrowLeft size={14} aria-hidden />
          Back
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-fg">Start your demo</h1>
        <p className="mt-2 text-sm text-fg-muted">
          We&rsquo;ll set up a private workspace pre-populated with realistic Shopify, Meta Ads and
          Shiprocket data. No sign-up, no email.
        </p>
        <div className="mt-6">
          <StartDemoForm />
        </div>
      </div>
    </div>
  );
}
