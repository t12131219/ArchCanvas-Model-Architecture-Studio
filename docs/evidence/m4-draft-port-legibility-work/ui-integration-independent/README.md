# Draft port legibility — independent integration read

The new draft geometry is consistently consumed by the card renderer, route obstacles/endpoints, fit, node/preset placement, layout and tooltip bounds in the inspected source. Two-input cards now occupy 176 × 140 world units and their side input anchors are 32 units apart.

Two findings were sent to the implementation agents and retained in [report.json](report.json): the selected stroke originally used a role-colored arrow tip, and the original vertical output label could overlap the kind caption in nominal text geometry at compensated overview scale. Readback now shows a selected gold marker with selection priority and vertical labels outside the top/bottom of the card. These are bounded source resolutions; new-build rendered pixels remain unreviewed.

The edge CSS uses `path:nth-of-type(2)`, so the new direct SVG `title` does not redirect styling to the transparent interaction path. Tooltip owner and obstacle rectangles use the dynamic card height; actual tooltip dimensions are measured before replacement. Horizontal merge slots have separated hit rectangles in the nominal geometry. The role classifier remains conservative and based on current graph connectivity, with a matching solid-data/dashed-bypass legend.

[source-read-bindings.json](source-read-bindings.json) binds the initial files after the actual initial reads. It is **not a pre-read freeze**. Product agents were editing concurrently, and this report does not assert a final product/build freeze. The root will notify the final version before new-build pixel evidence is collected and independently inspected. Original findings will remain visible alongside the final resolution readback.

No product or test file was edited by this reviewer. No test, build, model execution or browser action was performed during this integration read. Nominal text geometry is not a measurement of browser glyph pixels. Actual overview/detail, vertical labels, selected arrow tips and merge tooltip frames remain required.

This evidence is AI-only. Real research participants added: **0**. Human publication reviewers added: **0**. It does not replace the M4 human acceptance tasks.
