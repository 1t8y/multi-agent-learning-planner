import { create } from 'zustand';
import type { PlanStore } from '../types';

export const usePlanStore = create<PlanStore>((set) => ({
  userInput: '',
  setUserInput: (input) => set({ userInput: input }),
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),
  planResult: null,
  setPlanResult: (result) => set({ planResult: result }),
  error: null,
  setError: (error) => set({ error }),
}));
