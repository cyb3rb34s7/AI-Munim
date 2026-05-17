export { AuthProvider, ProtectedRoute, useAuthContext } from './AuthProvider';
export {
  useCurrentUser,
  useStartDemo,
  useOnboard,
  useLogout,
  AUTH_QUERY_KEY,
} from './hooks/useAuth';
export { StartDemoForm } from './components/StartDemoForm';
export type { CurrentUser, OnboardingResult } from './api/client';
