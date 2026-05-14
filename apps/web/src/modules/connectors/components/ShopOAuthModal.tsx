import { useState, type FormEvent } from 'react';

import { Button } from '@/shared/components';

interface ShopOAuthModalProps {
  open: boolean;
  defaultShop: string;
  submitting: boolean;
  error: Error | null;
  onSubmit: (shop: string) => void;
  onClose: () => void;
}

const MYSHOPIFY_SUFFIX = '.myshopify.com';

function normalizeShopInput(value: string): string {
  // Accept "munim-dev" or "munim-dev.myshopify.com"; canonicalize to the latter.
  const trimmed = value.trim().toLowerCase();
  if (trimmed.endsWith(MYSHOPIFY_SUFFIX)) {
    return trimmed;
  }
  return `${trimmed}${MYSHOPIFY_SUFFIX}`;
}

export function ShopOAuthModal({
  open,
  defaultShop,
  submitting,
  error,
  onSubmit,
  onClose,
}: ShopOAuthModalProps) {
  const [value, setValue] = useState(defaultShop);

  if (!open) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(normalizeShopInput(value));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-fg/40"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <form
        className="w-[440px] max-w-[90vw] rounded-lg border border-border bg-bg p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h3 className="text-base font-semibold">Connect your Shopify store</h3>
        <p className="mt-1 text-sm text-muted">
          Enter your shop subdomain. You'll be redirected to Shopify to approve access.
        </p>

        <label className="mt-4 block text-xs font-medium text-muted">Shop</label>
        <div className="mt-1 flex items-center rounded-md border border-border bg-bg-subtle">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="munim-dev"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none"
            autoFocus
          />
          <span className="px-3 py-2 text-xs text-muted">.myshopify.com</span>
        </div>

        {error && <p className="mt-3 text-xs text-error">{error.message}</p>}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Continue to Shopify
          </Button>
        </div>
      </form>
    </div>
  );
}
