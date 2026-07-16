import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import PrefectureDetail from './components/PrefectureDetail';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/prefecture/:name" element={<PrefectureDetail />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
