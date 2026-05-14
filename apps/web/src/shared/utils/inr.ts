const FORMATTER = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

export class InvalidMoneyError extends Error {
  readonly raw: unknown;
  constructor(raw: unknown) {
    super(`Invalid money value: ${String(raw)}`);
    this.name = 'InvalidMoneyError';
    this.raw = raw;
  }
}

export function inr(value: string | number): string {
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) throw new InvalidMoneyError(value);
  return FORMATTER.format(num);
}
