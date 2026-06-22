import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { SettingsPage } from './components/SettingsPage'
import { AvatarFloat } from './components/AvatarFloat'

const windowParam = new URLSearchParams(window.location.search).get('window')

let root: React.ReactNode
if (windowParam === 'float') {
  root = <AvatarFloat />
} else if (windowParam === 'settings') {
  root = <SettingsPage />
} else {
  root = <App />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>{root}</React.StrictMode>
)
