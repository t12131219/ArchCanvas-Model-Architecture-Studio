import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BottomPanel, InspectorPanel, NavigationPanel, TopBar } from "./StudioShell";

const tx = (english: string) => english;

describe("Studio shell boundaries", () => {
  it("renders the top-level project, mode, validation, and export controls", () => {
    const html = renderToStaticMarkup(<TopBar
      entrypointName="Transformer" revision="rev-1" mode="explore"
      modeLabels={{ explore: "Explore", layout: "Layout", model: "Model" }}
      locale="en" canUndo canRedo={false} writebackBlocked={false}
      invalidProofs={0} unprovenProofs={0} validationProfile="fast-static"
      diagnosticCount={3} kernelExport={null} exportBusy={null}
      exportMenuRef={createRef<HTMLDetailsElement>()} tx={tx}
      onOpenProject={() => undefined} onModeChange={() => undefined}
      onLocaleChange={() => undefined} onUndo={() => undefined} onRedo={() => undefined}
      onValidationProfileChange={() => undefined} onValidate={() => undefined}
      onExport={() => undefined}
    />);
    expect(html).toContain("Transformer");
    expect(html).toContain("Explore");
    expect(html).toContain("Publication export");
    expect(html).toContain("<span>3</span>");
  });

  it("keeps navigation, inspector, and bottom panels independently renderable", () => {
    const navigation = renderToStaticMarkup(<NavigationPanel tx={tx}><div>Tree</div></NavigationPanel>);
    const inspector = renderToStaticMarkup(<InspectorPanel mobileOpen activeTab="source" labels={{ inspect: "Inspect", source: "Source" }} onTabChange={() => undefined} onClose={() => undefined} tx={tx}><div>Evidence</div></InspectorPanel>);
    const bottom = renderToStaticMarkup(<BottomPanel activeTab="jobs" labels={{ problems: "Problems", jobs: "Jobs" }} badges={{ problems: 2, jobs: true }} onTabChange={() => undefined}><div>Running</div></BottomPanel>);
    expect(navigation).toContain("left-panel");
    expect(inspector).toContain("mobile-open");
    expect(inspector).toContain("Evidence");
    expect(bottom).toContain("<span>2</span>");
    expect(bottom).toContain("<span>1</span>");
  });
});
