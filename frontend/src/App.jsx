import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import AdminPage from './pages/AdminPage.jsx';
import DriverPage from './pages/DriverPage.jsx';
import CustomerPage from './pages/CustomerPage.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{
        display: 'flex', alignItems: 'center', gap: 0,
        background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)',
        padding: '0 24px', height: 52, position: 'sticky', top: 0, zIndex: 9000,
      }}>
        <span style={{ fontWeight: 800, fontSize: 17, letterSpacing: '-0.5px', marginRight: 32, color: 'var(--accent-blue)' }}>
          🚇 TransitSync
        </span>
        {[
          { to: '/', label: '📊 Admin' },
          { to: '/driver', label: '🚗 Driver' },
          { to: '/customer', label: '👤 Customer' },
        ].map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              padding: '0 16px', height: 52, display: 'flex', alignItems: 'center',
              textDecoration: 'none', fontSize: 13, fontWeight: 600,
              color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)',
              borderBottom: isActive ? '2px solid var(--accent-blue)' : '2px solid transparent',
              transition: 'all 0.2s',
            })}
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <Routes>
        <Route path="/" element={<AdminPage />} />
        <Route path="/driver" element={<DriverPage />} />
        <Route path="/customer" element={<CustomerPage />} />
      </Routes>
    </BrowserRouter>
  );
}
