import React, { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("LAF Application Error Boundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100vw',
          height: '100vh',
          background: '#090b11',
          color: '#f8fafc',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          textAlign: 'center',
          fontFamily: '"Inter", sans-serif'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
            fontSize: '28px'
          }}>
            ⚠️
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '8px', color: '#f8fafc' }}>
            UI Rendering Exception Intercepted
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '13.5px', maxWidth: '520px', marginBottom: '24px', lineHeight: '1.5' }}>
            {this.state.error?.message || 'An unexpected error occurred. Click below to recover your session.'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '10px 24px',
              fontSize: '13.5px',
              fontWeight: '600',
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)'
            }}
          >
            Reload LAF AI Workspace
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
