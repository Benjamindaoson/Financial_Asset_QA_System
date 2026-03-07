import React from 'react';
import { useUIStore } from '../store';

export const SettingsPage: React.FC = () => {
  const { theme, toggleTheme } = useUIStore();

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h1>Settings</h1>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h2>Appearance</h2>
          <div className="setting-item">
            <label>Theme</label>
            <button onClick={toggleTheme}>
              {theme === 'light' ? 'Switch to Dark' : 'Switch to Light'}
            </button>
          </div>
        </div>

        <div className="settings-section">
          <h2>API Configuration</h2>
          <div className="setting-item">
            <label>API Endpoint</label>
            <input type="text" placeholder="http://localhost:8000" />
          </div>
        </div>

        <div className="settings-section">
          <h2>Notifications</h2>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Enable price alerts
            </label>
          </div>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Enable news notifications
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};
