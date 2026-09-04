import { type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { PolicyDetail } from "./pages/PolicyDetail";
import { PolicyEdit } from "./pages/PolicyEdit";
import { Properties } from "./pages/Properties";
import { Register } from "./pages/Register";
import { Review } from "./pages/Review";
import { RemindersProvider } from "./reminder-count";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <RemindersProvider>{children}</RemindersProvider>
    </AuthProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/properties" element={<Properties />} />
      <Route path="/policies/:id/edit" element={<PolicyEdit />} />
      <Route path="/policies/:id" element={<PolicyDetail />} />
      <Route path="/documents/:id/review" element={<Review />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </BrowserRouter>
  );
}
