import { HealthSection } from '@/modules/health';

export function IndexPage() {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold">Overview</h2>
        <p className="mt-1 text-sm text-muted">
          One AI employee for D2C brands. Three connectors behind one abstraction. Citations on
          every number. Read the README before judging the build.
        </p>
      </section>
      <HealthSection />
    </div>
  );
}
