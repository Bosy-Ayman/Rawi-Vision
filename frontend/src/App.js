import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';
import LandingPage from './pages/LandingPage';
import VideoFeedPage from './pages/VideoFeed';
import SmartSearch from './pages/SmartSearch';
import Anomalies from './pages/Anomalies';
import EmployeeInsights from './pages/EmployeeInsights';
import EmployeeOnboarding from './pages/EmployeeOnboarding';
import AllEmployees from './pages/AllEmployees';
import EmployeeDetails from './pages/EmployeeDetails';
import CustomCursor from './components/CustomCursor';

function App() {
  return (
    <Router>
      <div className="App">
        {/* Cursor is global, but LandingPage also had it. 
            We can keep it here to be global, or let pages handle it. 
            Since Sidebar has hover effects, global is better. */}
        <CustomCursor />

        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard/video-feed" element={<VideoFeedPage />} />
          <Route path="/dashboard/smart-search" element={<SmartSearch />} />
          <Route path="/dashboard/anomalies" element={<Anomalies />} />
          <Route path="/dashboard/employee-insights" element={<EmployeeInsights />} />
          <Route path="/dashboard/employee-onboarding" element={<EmployeeOnboarding />} />
          <Route path="/dashboard/all-employees" element={<AllEmployees />} />
          <Route path="/dashboard/employee/:id" element={<EmployeeDetails />} />


          {/* Fallback for demo purposes */}
          <Route path="/dashboard/*" element={<VideoFeedPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
