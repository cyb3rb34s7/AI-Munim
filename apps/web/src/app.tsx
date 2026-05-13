import { HealthSection } from '@/modules/health';
import { ThemeProvider } from '@/shared/theme';

export function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-bg text-fg">
        <header className="border-b border-border bg-bg-subtle/40 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <div>
              <h1 className="text-lg font-semibold tracking-tight">AI-Munim</h1>
              <p className="text-xs text-muted">AI employee for D2C brands · v0</p>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
          <HealthSection />
        </main>
      </div>
    </ThemeProvider>
  );
}
