# Read-only browser and export source binding

This review does not rerun tests, start services, operate the browser, import
user model code, install dependencies, or change frozen source/tests/build/raw
captures. New reviewer helpers and receipts live only in this directory.

The saved Transformer storage envelope remains at storage revision 1 and Canvas
revision 27, exactly matching the source-bound L3 input and the original session
input binding. Source digest, IR digest, full architecture, source facts,
expanded IDs, layout and all Canvas facts are unchanged. Current renderer replay
is exact to root/capture-attempt-3 Scene and static SVG (SHA256
c1ea12490d8d5e5e3cd21bd521c5cfc1c9f299b03db18bbf711a81c0af813a7d).
The replay is an observed-output readback, not an independent expected renderer.
Independent oracle parsing checks the public paths/cards/circles/metadata.

The committed browser SVG in l3-public.json equals l3.svg. Browser assets are the
current index-au3IB_0Q.js (SHA256
dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b)
and index-B6WbMowt.css (SHA256
172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0).
Current source/build receipt/log bindings remain exact. Static, interactive,
committed public browser and actual SVG export paths, cards, circles, styles,
metadata, canonical coverage and viewBox agree. L3 has 20 strict pairs/23 points
and 17 different-tensor overlap pairs.

Actual export UUIDs were discovered under the session `exports` directory:
72f21096acbc4dc1a3d98e1193baa8c9/figure.svg and
187559f6e5984e84bddbf16eff24a613/figure.pdf. Their saved document.json files equal
the stored/source-bound Canvas. SVG and PDF receipt source/IR/document/revision,
renderer input digest, output bytes and output hashes agree with actual files.
The SVG file is 150,384 bytes, SHA256
e088f8cebcbbe824a5d48840ce42a23cabe188f65ee10e1d150a8425c1d7de89.
The PDF is 36,333 bytes, SHA256
0fcec8de89c5494b8f81a2075ec124c349bb7c7e0e1e55b5c02c045bdb4aca9b.
Its signature, one page and MediaBox match 180 × 605.611052 mm. The actual SVG
XML tree equals l3-export-browser.svg after XML parsing; different byte sizes
reflect serialization, and raw bytes remain untouched.

The 211-byte l3-export-preview.svg is the modal's 18×18 close icon. It has no
architecture metadata and is explicitly excluded as model preview evidence.

The role/native port raw captures each show two draft nodes, one draft edge,
three public draft ports, and equal hit/visible route paths. Endpoints agree with
the Input output and Linear input circles in the translated draft coordinate
space. The generated edge IDs differ between the two states; this distinction
is recorded. They carry no canonical Canvas/Scene metadata, and this readback
makes no persistence claim. Root's later fresh four-node/three-edge save/reopen
has separate scope. Root reported that its first batched connection attempt
still had one edge; this review does not treat that attempt as success or infer
a confirmed cause.

The renderer-readback.json and artifact-readback.json bind all inputs and
observations; replay-process.json and artifact-attempt-2-process.json record
successful read-only executions. Earlier reviewer helper failures remain:
incorrect relative import depth was corrected before replay, and an overstrict
role/native raw byte equality assumption was corrected to record their actual
generated edge-ID difference. The prior failed artifact receipt incorrectly
called it a CSS difference; the next receipt explicitly corrects that statement.

A 14% fit panorama does not demonstrate publication clarity. The actual export
screenshot covers only the top region. This round has no new full visual matrix
or human review. PDF glyph/font fidelity and rendered pixel quality are not
independently certified by these file checks. Receipt physical-size measurements
and adjustable text-size suggestions are preserved as measurements, not a
journal standard or publication approval.
