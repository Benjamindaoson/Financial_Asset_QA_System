import React from 'react';
import { useMarketStore } from '../store';

export const MarketPage: React.FC = () => {
  const { marketData, watchlist, isLoading } = useMarketStore();

  return (
    <div className="market-page">
      <div className="market-header">
        <h1>Market Analysis</h1>
      </div>

      <div className="market-overview">
        <div className="market-section">
          <h2>Watchlist</h2>
          {watchlist.length === 0 ? (
            <p>No symbols in watchlist</p>
          ) : (
            <div className="watchlist-grid">
              {watchlist.map((symbol) => {
                const data = marketData[symbol];
                return (
                  <div key={symbol} className="market-card">
                    <h3>{symbol}</h3>
                    {data ? (
                      <>
                        <div className="price">${data.price.toFixed(2)}</div>
                        <div className={`change ${data.change >= 0 ? 'positive' : 'negative'}`}>
                          {data.change >= 0 ? '+' : ''}{data.changePercent.toFixed(2)}%
                        </div>
                      </>
                    ) : (
                      <div>Loading...</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="market-section">
          <h2>Market Indices</h2>
          <div className="indices-grid">
            <div className="index-card">
              <h3>S&P 500</h3>
              <div className="price">Loading...</div>
            </div>
            <div className="index-card">
              <h3>NASDAQ</h3>
              <div className="price">Loading...</div>
            </div>
            <div className="index-card">
              <h3>DOW</h3>
              <div className="price">Loading...</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
