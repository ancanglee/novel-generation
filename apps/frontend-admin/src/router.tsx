import { createBrowserRouter } from "react-router-dom";
import AdminRootLayout from "./layouts/AdminRootLayout";
import AdminDashboard from "./pages/AdminDashboard";

export const router = createBrowserRouter([
  {
    path: "/admin",
    element: <AdminRootLayout />,
    children: [
      { index: true, element: <AdminDashboard /> },
      { path: "users", lazy: async () => ({ Component: (await import("./pages/users")).default }) },
      { path: "teams", lazy: async () => ({ Component: (await import("./pages/teams")).default }) },
      { path: "model-configs", lazy: async () => ({ Component: (await import("./pages/model-configs")).default }) },
      { path: "schemas", lazy: async () => ({ Component: (await import("./pages/schemas")).default }) },
      { path: "templates", lazy: async () => ({ Component: (await import("./pages/templates")).default }) },
      { path: "monitoring", lazy: async () => ({ Component: (await import("./pages/monitoring")).default }) },
      { path: "audit", lazy: async () => ({ Component: (await import("./pages/audit")).default }) },
      { path: "alerts", lazy: async () => ({ Component: (await import("./pages/alerts")).default }) },
      { path: "concurrency", lazy: async () => ({ Component: (await import("./pages/concurrency")).default }) },
    ],
  },
]);
