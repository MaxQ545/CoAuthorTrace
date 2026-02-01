import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { TimeFilterProvider } from './contexts/TimeFilterContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <TimeFilterProvider>
        <App />
      </TimeFilterProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
