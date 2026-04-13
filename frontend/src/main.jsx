import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider, createRoutesFromElements, Route } from 'react-router-dom';
import App from './App.jsx';
import UploadPage from './pages/UploadPage.jsx';
import ResultsPage from './pages/ResultsPage.jsx';
import './index.css';

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route path = '/' element={<App />}> 
      <Route index element={<UploadPage />} />
      <Route path = 'results' element={<ResultsPage />} />
    </Route>
  )
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
