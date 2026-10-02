import React from "react";
import { createRoot } from "react-dom/client";

import { SceneStudioApp } from "./scene-studio/SceneStudioApp";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SceneStudioApp />
  </React.StrictMode>,
);
