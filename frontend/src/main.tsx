import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { SettingsPage } from './components/SettingsPage'

// Detecta se esta janela é a de configurações
const isSettings = new URLSearchParams(window.location.search).get('window') === 'settings'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isSettings ? <SettingsPage /> : <App />}
  </React.StrictMode>
)
