import { z } from 'zod';

/** Mirrors apps/api/src/munim/modules/health/service.py::HealthData. */
export const healthDataSchema = z.object({
  status: z.string(),
  version: z.string(),
});

export type HealthData = z.infer<typeof healthDataSchema>;
