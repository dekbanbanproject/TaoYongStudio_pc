import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ToastProvider } from "./components/common/feedback";
import Dashboard from "./pages/Dashboard";
import Planner from "./pages/Planner";
import Scripts from "./pages/Scripts";
import Clips from "./pages/Clips";
import CreatePublish from "./pages/CreatePublish";
import PostingSettings from "./pages/PostingSettings";
import Scheduler from "./pages/Scheduler";
import Settings from "./pages/Settings";
import FacebookProfile from "./pages/FacebookProfile";

export default function App() {
  return (
    <ToastProvider>
      <HashRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/scripts" element={<Scripts />} />
            <Route path="/clips" element={<Clips />} />
            <Route path="/create" element={<CreatePublish />} />
            <Route path="/create/:platform" element={<CreatePublish />} />
            <Route path="/posting-settings" element={<PostingSettings />} />
            <Route path="/scheduler" element={<Scheduler />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/facebook-profile" element={<FacebookProfile />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </HashRouter>
    </ToastProvider>
  );
}
