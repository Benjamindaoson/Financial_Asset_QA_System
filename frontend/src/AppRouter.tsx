import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ChatPage, MarketPage, PortfolioPage, SettingsPage } from './pages';
import { useUIStore } from './store';
import { C, F } from './theme';

const Navigation: React.FC = () => {
  const location = useLocation();
  const { theme } = useUIStore();

  const navItems = [
    { path: '/', label: 'Chat', icon: '💬' },
    { path: '/market', label: 'Market', icon: '📈' },
    { path: '/portfolio', label: 'Portfolio', icon: '💼' },
    { path: '/settings', label: 'Settings', icon: '⚙️' }
  ];

  return (
    <nav style={{
      background: C.white,
      borderBottom: `1px solid ${C.border}`,
      padding: '0 20px',
      height: 56,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexShrink: 0
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: `linear-gradient(135deg,${C.accent},#3B82F6)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          fontWeight: 900,
          color: '#fff'
        }}>
          F
        </div>
        <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>FinSight AI</span>
      </div>

      <div style={{ display: 'flex', gap: 4 }}>
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              borderRadius: 8,
              textDecoration: 'none',
              fontSize: 13,
              fontWeight: 600,
              background: location.pathname === item.path ? C.accentL : 'transparent',
              color: location.pathname === item.path ? C.accent : C.ts,
              transition: 'all 0.2s'
            }}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </div>

      <span style={{
        fontSize: 10,
        padding: '4px 8px',
        borderRadius: 4,
        background: C.upL,
        color: C.up,
        fontWeight: 700,
        fontFamily: F.m
      }}>
        ● LIVE
      </span>
    </nav>
  );
};

export default function App() {
  return (
    <BrowserRouter>
      <div style={{
        width: '100vw',
        height: '100vh',
        background: C.bg,
        fontFamily: F.s,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        <style>{`
          @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
          *{box-sizing:border-box;margin:0;padding:0}
          ::-webkit-scrollbar{width:6px}
          ::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:10px}
          input::placeholder{color:${C.td}}
        `}</style>

        <Navigation />

        <div style={{ flex: 1, overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/market" element={<MarketPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
