import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './app/App';
import { TelemetryErrorBoundary } from './components/common/TelemetryErrorBoundary';
import { initializeFrontendTelemetry } from './services/telemetry';
import './styles/globals.css';

initializeFrontendTelemetry();
const queryClient=new QueryClient({defaultOptions:{queries:{staleTime:60_000,retry:1,refetchOnWindowFocus:false}}});
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><TelemetryErrorBoundary><QueryClientProvider client={queryClient}><BrowserRouter><App/></BrowserRouter></QueryClientProvider></TelemetryErrorBoundary></React.StrictMode>);
