import React from "react";
import { createRoot } from "react-dom/client";

import { StudioApp } from "./app/StudioApp";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <StudioApp />
  </React.StrictMode>,
);
