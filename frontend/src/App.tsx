import { type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { ForgotPassword } from "./pages/ForgotPassword";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { PolicyDetail } from "./pages/PolicyDetail";
import { PolicyEdit } from "./pages/PolicyEdit";
import { Profile } from "./pages/Profile";
import { Properties } from "./pages/Properties";
import { PropertyEdit } from "./pages/PropertyEdit";
import { PropertyNew } from "./pages/PropertyNew";
import { Register } from "./pages/Register";
import { Reminders } from "./pages/Reminders";
import { ResetPassword } from "./pages/ResetPassword";
import { Review } from "./pages/Review";
import { Uploads } from "./pages/Uploads";
import { VerifyEmail } from "./pages/VerifyEmail";
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
      <Route path="/uploads" element={<Uploads />} />
      <Route path="/properties/new" element={<PropertyNew />} />
      <Route path="/properties/:id/edit" element={<PropertyEdit />} />
      <Route path="/properties" element={<Properties />} />
      <Route path="/reminders" element={<Reminders />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/policies/:id/edit" element={<PolicyEdit />} />
      <Route path="/policies/:id" element={<PolicyDetail />} />
      <Route path="/documents/:id/review" element={<Review />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
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
