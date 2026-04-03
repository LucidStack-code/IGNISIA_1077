import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import App from './App'
import { TransitProvider } from './context/TransitContext'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <TransitProvider>
        <App />
      </TransitProvider>
    </BrowserRouter>
  </React.StrictMode>
)
