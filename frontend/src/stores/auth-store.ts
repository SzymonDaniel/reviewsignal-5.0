import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  user: { name: 'User' },
  subscription: { apiLimit: 10000 },
}));
