import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { ReadOnlyProvider } from './contexts/ReadOnlyContext';
import 'katex/dist/katex.min.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ReadOnlyProvider>
      <App />
    </ReadOnlyProvider>
  </React.StrictMode>
);