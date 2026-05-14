import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { FeedPanel } from './FeedPanel';
import { fadeUp } from '@/shared/utils/motion';

export function AppShell() {
  const location = useLocation();
  return (
    <div className="grid h-screen grid-cols-[248px_minmax(0,1fr)] lg:grid-cols-[248px_minmax(0,1fr)_360px] bg-bg">
      <Sidebar />
      <main className="overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            className="min-h-full"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <FeedPanel />
    </div>
  );
}
