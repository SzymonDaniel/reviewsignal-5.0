/**
 * ReviewSignal 7.0 - Auth Store
 * Zustand store for authentication state management
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import Cookies from 'js-cookie';
import { api } from '@/lib/api';

// ============================================================================
// TYPES
// ============================================================================

export interface User {
  id: string;
  email: string;
  name: string;
  company?: string;
  role: 'viewer' | 'analyst' | 'manager' | 'admin' | 'superadmin';
  avatar?: string;
  createdAt: string;
  lastLoginAt: string;
}

export interface Subscription {
  id: string;
  tier: 'trial' | 'starter' | 'pro' | 'enterprise';
  status: 'active' | 'past_due' | 'canceled' | 'trialing';
  currentPeriodEnd: string;
  apiLimit: number;
  apiUsed: number;
  features: string[];
}

export interface AuthState {
  user: User | null;
  subscription: Subscription | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface AuthActions {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  refreshUser: () => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
  company?: string;
}

type AuthStore = AuthState & AuthActions;

// ============================================================================
// STORE
// ============================================================================

export const useAuthStore = create<AuthStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      user: null,
      subscription: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (email: string, password: string) => {
        set((state) => {
          state.isLoading = true;
          state.error = null;
        });

        try {
          const response = await api.post<{
            access_token: string;
            refresh_token: string;
            user: User;
            subscription: Subscription;
          }>('/api/v1/auth/login', { email, password });

          // Store tokens in cookies
          Cookies.set('access_token', response.access_token, {
            expires: 1,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
          });
          Cookies.set('refresh_token', response.refresh_token, {
            expires: 30,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
          });

          set((state) => {
            state.user = response.user;
            state.subscription = response.subscription;
            state.isAuthenticated = true;
            state.isLoading = false;
          });
        } catch (error: any) {
          set((state) => {
            state.error = error.message || 'Login failed';
            state.isLoading = false;
          });
          throw error;
        }
      },

      logout: async () => {
        try {
          await api.post('/api/v1/auth/logout');
        } catch {
          // Ignore logout errors
        } finally {
          Cookies.remove('access_token');
          Cookies.remove('refresh_token');
          
          set((state) => {
            state.user = null;
            state.subscription = null;
            state.isAuthenticated = false;
            state.error = null;
          });
        }
      },

      register: async (data: RegisterData) => {
        set((state) => {
          state.isLoading = true;
          state.error = null;
        });

        try {
          const response = await api.post<{
            access_token: string;
            refresh_token: string;
            user: User;
            subscription: Subscription;
          }>('/api/v1/auth/register', data);

          Cookies.set('access_token', response.access_token, {
            expires: 1,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
          });
          Cookies.set('refresh_token', response.refresh_token, {
            expires: 30,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
          });

          set((state) => {
            state.user = response.user;
            state.subscription = response.subscription;
            state.isAuthenticated = true;
            state.isLoading = false;
          });
        } catch (error: any) {
          set((state) => {
            state.error = error.message || 'Registration failed';
            state.isLoading = false;
          });
          throw error;
        }
      },

      refreshUser: async () => {
        const token = Cookies.get('access_token');
        if (!token) return;

        try {
          const response = await api.get<{
            user: User;
            subscription: Subscription;
          }>('/api/v1/auth/me');

          set((state) => {
            state.user = response.user;
            state.subscription = response.subscription;
            state.isAuthenticated = true;
          });
        } catch {
          // Token invalid - logout
          get().logout();
        }
      },

      updateProfile: async (data: Partial<User>) => {
        const response = await api.patch<User>('/api/v1/users/me', data);
        set((state) => {
          if (state.user) {
            Object.assign(state.user, response);
          }
        });
      },

      changePassword: async (oldPassword: string, newPassword: string) => {
        await api.post('/api/v1/auth/change-password', {
          old_password: oldPassword,
          new_password: newPassword,
        });
      },

      clearError: () => {
        set((state) => {
          state.error = null;
        });
      },

      setLoading: (loading: boolean) => {
        set((state) => {
          state.isLoading = loading;
        });
      },
    })),
    {
      name: 'reviewsignal-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        subscription: state.subscription,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
