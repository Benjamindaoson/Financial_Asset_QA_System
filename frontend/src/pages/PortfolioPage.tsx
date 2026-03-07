import React from 'react';

export const PortfolioPage: React.FC = () => {
  return (
    <div className="portfolio-page">
      <div className="portfolio-header">
        <h1>Portfolio Management</h1>
      </div>

      <div className="portfolio-overview">
        <div className="portfolio-stats">
          <div className="stat-card">
            <h3>Total Value</h3>
            <div className="value">$0.00</div>
          </div>
          <div className="stat-card">
            <h3>Today's Change</h3>
            <div className="value">$0.00 (0.00%)</div>
          </div>
          <div className="stat-card">
            <h3>Total Return</h3>
            <div className="value">$0.00 (0.00%)</div>
          </div>
        </div>

        <div className="portfolio-holdings">
          <h2>Holdings</h2>
          <p>No holdings yet. Add positions to track your portfolio.</p>
        </div>
      </div>
    </div>
  );
};
