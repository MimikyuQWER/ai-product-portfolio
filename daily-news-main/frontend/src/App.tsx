import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import AppLayout from './components/Layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Selection from './pages/Selection';
import Generation from './pages/Generation';
import StandalonePreview from './pages/StandalonePreview';
import History from './pages/History';
import TaskManagement from './pages/TaskManagement';
import Agents from './pages/Agents';
import KnowledgeBase from './pages/KnowledgeBase';
import PluginManagement from './pages/PluginManagement';
import Settings from './pages/Settings';
import Login from './pages/Login';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <Router basename={import.meta.env.BASE_URL}>
            <Routes>
              <Route path="/login" element={<Login />} />
              {/* 日报页面和预览页面公开访问，不需要登录 */}
              <Route path="/" element={<Navigate to="/generation" replace />} />
              <Route path="/generation" element={<Generation />} />
              <Route path="/preview" element={<StandalonePreview />} />
              {/* 后台管理页面需要登录 */}
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <Routes>
                        <Route path="/dashboard" element={<Dashboard />} />
                        <Route path="/selection" element={<Selection />} />
                         <Route path="/history" element={<History />} />
                         <Route path="/tasks" element={<TaskManagement />} />
                         <Route path="/agents" element={<Agents />} />
                         <Route path="/knowledge" element={<KnowledgeBase />} />
                         <Route path="/plugins" element={<PluginManagement />} />
                         <Route path="/settings" element={<Settings />} />
                       </Routes>
                    </AppLayout>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </Router>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
