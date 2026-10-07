# Large viewport and native toggle diagnostic

This is a bounded diagnostic of frozen resize build `index-_KAUBMcR.js`, not an M4 performance or human acceptance result. The service opened the source-backed DenseStress300 typed-move candidate at saved Canvas5/storage1. Root selected and pinned the unrelated features input, then performed four ordinary native tree toggles at actual window4096×2700/DPR1. Revisions6→7→8→9→10 and304→4→304→4→304 are recorded. Final saved Canvas10/storage2 differs from the candidate only in revision and that one pin.

The full [native receipt](browser/07-native-300-four-toggle.complete.json) has4 captured,4 valid and4 matched toggle trials. Durations are280/504/248/520ms, matched p95 **520ms**. All4 unrelated pins are measured at zero canvas displacement; maximum screen anchor displacement is0.0001550913CSSpx. The official validator exits0 for receipt consistency; it does not certify numeric targets. Session elapsed67545.2ms/rAF3957 callbacks/58.5809 callbacks per second includes user-tool preparation and waits. It is not presentedFPS. Fixed resolved fonts/hardware/power, full continuous-input denominator, A/B×3, medium workload and real users remain unverified.

## Concrete collapse defect

The [finite independent readback](root-readback-attempt-1/report.json) returns **353/357**, with four failed common-body-position comparisons. It deliberately retains those failures. The broad expectation that every common body stays at exactly the same position across collapse is too strong for an unpinned neighbor: ordinary container shrink can legitimately reposition output. Independently of that oracle limitation, this case has a real malformed saved collapsed layout: the output moves from(80,1756) to **(80,-28236)** on each collapse, then restores on expand. Its collapsed frontier localy is-28328. The preparer's dy=-28590 ordinary move was propagated to both saved frontiers by the current `document.ts` move contract. The collapsed saved frontier was not suitable for that large delta. This invalidates spatial/readability acceptance for the toggled workload; the consistency validator does not check viewport containment.

No product or historic candidate was altered to hide the defect. This diagnostic is useful for actual timing and regression analysis, but is not a passing stress scenario. The complete reexpanded leaf body geometry and304source identities match the prepared scene. Canonical facts and source/IR digests remain exact. Four failures are not four failures of the official product test suite; they are this explicitly stronger independent diagnostic.

## Actual object and text observations

Default window1102×835/canvas672×641 fit15percent gives nominal leaf-title1.9466CSSpx. The first large view3800×2100/canvas3303×1906 fit69.8997percent gives title9.087CSSpx. Requested4800×2700 was clamped by the browser to **4096×2700**, canvas3599×2506, fit76.3514percent. [Final publicDOM](browser/09-final-rev10-public-dom.json) has304unique canonical card groups and300source-bound leaf groups; all304body bounding rectangles are inside the canvas. Nominal leaf titles are9.9257CSSpx and subtitles7.6351CSSpx. Public glyph rectangles are positive, but actual resolved font files are unknown. Root viewed the complete screenshot and explicit offline crop; its small labels remain unsuitable for reliable full inventory reading. The300readable-object gate is unapproved.

These are distinct real browser measurements, not the previous projection3400/3800 assumptions. Large viewport testing is for the300visible-object condition; the temporary override was reset after collection. No calibrated publication-size or first-paint/all-pixel-freshness claim is made.

## Readout limitations retained

- Browser01/02 initially selected mixed907node/port groups; those are not907objects. Public03 and final09 independently count304canonical cards.
- Embedded SVG strings in01/02/03/06 were capped at200011characters by the read-only tool serializer. Only [09 completeSVG](browser/09-final-rev10-complete.svg), read in18chunks and length861749, is the full XML authority.
- Native first read was capped at200000characters and failed JSON parsing. [Original truncated attempt](browser/07-native-300-four-toggle.raw.json) remains; the complete same textarea was read in13chunks. The [readout record](browser/07-native-readout-attempt.json) explains the correction.
- CUA screenshot clip04 returned a900×450top-left view instead of the requested scene region. It is not used as that region's evidence.05 is an explicitly labeled offline crop of the full03screenshot.
- Only public served script filename and frozen resize source/build bindings were compared; no HTTP asset-byte readback was performed. Concurrent routing source changes do not inherit this diagnostic.

The [performance design audit](performance-design-audit/README.md) distinguishes ordinary native toggle sampling, synthetic20pair sampling, continuous DOM proxies and actual presentation. New continuous measurement work is a separate scope; no runtime model execution or semantic source writeback occurred. M4 remainspartial, M5not_started, human participants0.
