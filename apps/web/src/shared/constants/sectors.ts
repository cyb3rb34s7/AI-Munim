export const Sector = {
  FASHION: 'fashion',
  BEAUTY: 'beauty',
  FMCG: 'fmcg',
  ELECTRONICS: 'electronics',
  HOME: 'home',
  GENERIC: 'generic',
} as const;
export type Sector = (typeof Sector)[keyof typeof Sector];

export const SECTOR_LABEL: Record<Sector, string> = {
  fashion: 'Fashion & Apparel',
  beauty: 'Beauty & Cosmetics',
  fmcg: 'FMCG / Consumables',
  electronics: 'Electronics & Gadgets',
  home: 'Home & Lifestyle',
  generic: 'Generic D2C',
};

export const SECTOR_OPTIONS: Sector[] = [
  Sector.FASHION,
  Sector.BEAUTY,
  Sector.FMCG,
  Sector.ELECTRONICS,
  Sector.HOME,
  Sector.GENERIC,
];
