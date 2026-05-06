import { createBrowserRouter } from "react-router-dom";
import RootLayout from "./layouts/RootLayout";
import Dashboard from "./pages/Dashboard";
import ErrorFallback from "./components/ErrorFallback";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <ErrorFallback />,
    children: [
      { index: true, element: <Dashboard /> },
      {
        path: "novels",
        lazy: async () => {
          const mod = await import("./pages/novels");
          return { Component: mod.default };
        },
      },
      {
        path: "novels/:novelId",
        lazy: async () => {
          const mod = await import("./pages/novels/NovelDetailPage");
          return { Component: mod.default };
        },
      },
      {
        path: "novels/:novelId/analysis",
        lazy: async () => {
          const mod = await import("./pages/analysis");
          return { Component: mod.default };
        },
      },
      {
        path: "generations/:gid/outline",
        lazy: async () => {
          const mod = await import("./pages/outline");
          return { Component: mod.default };
        },
      },
      {
        path: "generations/:gid/chapters/:n",
        lazy: async () => {
          const mod = await import("./pages/chapter");
          return { Component: mod.default };
        },
      },
      {
        path: "read/:gid",
        lazy: async () => {
          const mod = await import("./pages/reader");
          return { Component: mod.default };
        },
      },
      {
        path: "settings",
        lazy: async () => {
          const mod = await import("./pages/settings");
          return { Component: mod.default };
        },
      },
    ],
  },
]);
