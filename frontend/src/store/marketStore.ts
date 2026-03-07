import { create } from 'zustand';

interface MarketData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: number;
}

interface MarketState {
  marketData: Record<string, MarketData>;
  watchlist: string[];
  isLoading: boolean;
  updateMarketData: (symbol: string, data: MarketData) => void;
  addToWatchlist: (symbol: string) => void;
  removeFromWatchlist: (symbol: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  marketData: {},
  watchlist: [],
  isLoading: false,

  updateMarketData: (symbol, data) => set((state) => ({
    marketData: { ...state.marketData, [symbol]: data }
  })),

  addToWatchlist: (symbol) => set((state) => ({
    watchlist: [...state.watchlist, symbol]
  })),

  removeFromWatchlist: (symbol) => set((state) => ({
    watchlist: state.watchlist.filter(s => s !== symbol)
  })),

  setLoading: (loading) => set({ isLoading: loading })
}));
