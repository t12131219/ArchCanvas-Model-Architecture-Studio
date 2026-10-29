import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import './WorkspaceUI.css';
import { getLocale, subscribeLocale } from './i18n';

function LocalizedWorkspace() {
  const locale = React.useSyncExternalStore(subscribeLocale, getLocale);
  React.useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  return <App />;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><LocalizedWorkspace /></React.StrictMode>);
