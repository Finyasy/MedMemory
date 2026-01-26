import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary'

const initTheme = () => {
  const stored = localStorage.getItem('medmemory_theme') as 'light' | 'dark' | 'system' | null;
  const theme = stored || 'system';
  const root = document.documentElement;
  
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    root.setAttribute('data-theme', theme);
  }
};

initTheme();

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  const stored = localStorage.getItem('medmemory_theme');
  if (!stored || stored === 'system') {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
  }
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
