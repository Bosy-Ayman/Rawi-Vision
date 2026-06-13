import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';
import LandingPage from './pages/LandingPage';
import VideoFeedPage from './pages/VideoFeed';
import SmartSearch from './pages/SmartSearch';
import Anomalies from './pages/Anomalies';
import Clips from './pages/Clips';
import EmployeeOnboarding from './pages/EmployeeOnboarding';
import AllEmployees from './pages/AllEmployees';
import EmployeeDetails from './pages/EmployeeDetails';
import EmployeeInsights from './pages/EmployeeInsights';
import SystemUserManagement from './pages/SystemUserManagement';
import Settings from './pages/Settings';
import CustomCursor from './components/CustomCursor';
import DashboardMain from './pages/DashboardMain';

import CameraOnboarding from './pages/CameraOnboarding';
import AllCameras from './pages/AllCameras';

import { SubscriptionProvider } from './context/SubscriptionContext';
import SubscriptionGuard from './components/dashboard/SubscriptionGuard';

function App() {
  return (
    <SubscriptionProvider>
      <Router>
        <div className="App">
          {/* Cursor is global, but LandingPage also had it. 
              We can keep it here to be global, or let pages handle it. 
              Since Sidebar has hover effects, global is better. */}
          <CustomCursor />

          <Routes>
            <Route path="/" element={<LandingPage />} />

            {/* Guarded dashboard and admin routes */}
            <Route path="/dashboard/main" element={<SubscriptionGuard><DashboardMain /></SubscriptionGuard>} />
            <Route path="/dashboard/video-feed" element={<SubscriptionGuard><VideoFeedPage /></SubscriptionGuard>} />
            <Route path="/dashboard/smart-search" element={<SubscriptionGuard><SmartSearch /></SubscriptionGuard>} />
            <Route path="/dashboard/anomalies" element={<SubscriptionGuard><Anomalies /></SubscriptionGuard>} />
            <Route path="/dashboard/clips" element={<SubscriptionGuard><Clips /></SubscriptionGuard>} />
            <Route path="/dashboard/employee-onboarding" element={<SubscriptionGuard><EmployeeOnboarding /></SubscriptionGuard>} />
            <Route path="/dashboard/all-employees" element={<SubscriptionGuard><AllEmployees /></SubscriptionGuard>} />
            <Route path="/dashboard/employee-insights" element={<SubscriptionGuard><EmployeeInsights /></SubscriptionGuard>} />
            <Route path="/dashboard/employee/:id" element={<SubscriptionGuard><EmployeeDetails /></SubscriptionGuard>} />

            <Route path="/dashboard/camera-onboarding" element={<SubscriptionGuard><CameraOnboarding /></SubscriptionGuard>} />
            <Route path="/dashboard/all-cameras" element={<SubscriptionGuard><AllCameras /></SubscriptionGuard>} />

            <Route path="/admin/system-users" element={<SubscriptionGuard><SystemUserManagement /></SubscriptionGuard>} />
            <Route path="/dashboard/settings" element={<SubscriptionGuard><Settings /></SubscriptionGuard>} />

            {/* Fallback for demo purposes */}
            <Route path="/dashboard/*" element={<SubscriptionGuard><VideoFeedPage /></SubscriptionGuard>} />
          </Routes>
        </div>
      </Router>
    </SubscriptionProvider>
  );
}

export default App;
