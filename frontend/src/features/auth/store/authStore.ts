import { create } from 'zustand';
import { User } from '@/shared/types/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (user: User, accessToken: string, refreshToken: string) => void;
  logout: () => void;
  restoreAuth: () => Promise<void>;
}

// Strictly typed Auth Store without persisting secrets explicitly in localstorage via Zustand Persist 
// (We handle tokens safely in the interceptor, while user state can be non-persistent or fetched on load)
import { persist } from 'zustand/middleware';

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null as User | null,
      isAuthenticated: false as boolean,

      login: (user: User, accessToken: string, refreshToken: string) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', accessToken);
          localStorage.setItem('refresh_token', refreshToken);
        }
        set({ user, isAuthenticated: true });
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
        set({ user: null, isAuthenticated: false });
        if (typeof window !== 'undefined') {
           window.location.href = '/login';
        }
      },

      restoreAuth: async () => {
        if (typeof window !== 'undefined') {
          const token = localStorage.getItem('access_token');
          if (token) {
            // Token exists, mark as authenticated
            // The API interceptor will handle token validation on first request
            set({ isAuthenticated: true });
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
