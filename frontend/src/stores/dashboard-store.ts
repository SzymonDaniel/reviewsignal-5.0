import { create } from 'zustand';

export const useDashboardStore = create((set) => ({
  dateRange: { from: new Date(), to: new Date() },
  setDateRange: (range: any) => set({ dateRange: range }),
  selectedChains: [],
  toggleChain: (chain: string) => set((state: any) => ({
    selectedChains: state.selectedChains.includes(chain)
      ? state.selectedChains.filter((c: string) => c !== chain)
      : [...state.selectedChains, chain]
  })),
}));
