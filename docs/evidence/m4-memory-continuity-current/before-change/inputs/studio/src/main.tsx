import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import './perfBenchmark';
import { PerfBenchmarkPanel } from './PerfBenchmarkPanel';
import { StudyPanel } from './StudyPanel';

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /><PerfBenchmarkPanel /><StudyPanel /></React.StrictMode>);
