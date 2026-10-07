# Transformer L3 routing candidates for future review

Product/build and captures remain frozen. All four L3 cases have the same serialized route geometry and canonical bindings. The representative paper180 scene retains 34 strict-perpendicular, 56 collinear-overlap and 102 point-touch segment incidences. These are source geometry observations, not automatically defects.

Tensor pair categories: {'different-tensor': 39, 'same-tensor': 23}. Segment incidence categories: {'different-tensor:point-touch': 44, 'different-tensor:collinear-overlap': 22, 'same-tensor:collinear-overlap': 34, 'same-tensor:point-touch': 58, 'different-tensor:strict-perpendicular-crossing': 23, 'same-tensor:strict-perpendicular-crossing': 11}. Review priority pair counts: {1: 19, 2: 20, 3: 17, 4: 6}.

Prioritize different-tensor positive-length overlap spans, then different-tensor strict crossings. Same-tensor overlap may be intended sharing and needs canonical binding and role/style review before rerouting. Different-tensor contacts are candidates for readability review, not proof of wrong endpoints or unnecessary route geometry.

Concrete first candidates:

- Rank 1: edge:6 data / edge:7 mask; different-tensor; canonical A=['edge:6'], B=['edge:7']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 466.0]]}, {'segmentA': 3, 'segmentB': 3, 'type': 'collinear-overlap', 'span': [[74.0, 466.0], [214.67, 466.0]]}].
- Rank 1: edge:6 data / edge:11 mask; different-tensor; canonical A=['edge:6'], B=['edge:11']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 466.0]]}].
- Rank 1: edge:7 mask / edge:8 data; different-tensor; canonical A=['edge:7'], B=['edge:8', 'edge:9', 'edge:10']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 466.0]]}].
- Rank 1: edge:7 mask / edge:13 residual; different-tensor; canonical A=['edge:7'], B=['edge:13']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 466.0]]}].
- Rank 1: edge:7 mask / edge:50 mask; different-tensor; canonical A=['edge:7'], B=['edge:50']; serialized intersections=[{'segmentA': 1, 'segmentB': 1, 'type': 'collinear-overlap', 'span': [[317.0, 202.0], [479.0, 202.0]]}].
- Rank 1: edge:7 mask / edge:57 mask; different-tensor; canonical A=['edge:7'], B=['edge:57']; serialized intersections=[{'segmentA': 1, 'segmentB': 1, 'type': 'collinear-overlap', 'span': [[155.0, 202.0], [479.0, 202.0]]}].
- Rank 1: edge:8 data / edge:11 mask; different-tensor; canonical A=['edge:8', 'edge:9', 'edge:10'], B=['edge:11']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 528.0]]}, {'segmentA': 3, 'segmentB': 3, 'type': 'collinear-overlap', 'span': [[74.0, 528.0], [204.67, 528.0]]}].
- Rank 1: edge:11 mask / edge:13 residual; different-tensor; canonical A=['edge:11'], B=['edge:13']; serialized intersections=[{'segmentA': 2, 'segmentB': 2, 'type': 'collinear-overlap', 'span': [[74.0, 378.0], [74.0, 528.0]]}].

JSON records complete canonical edge IDs, tensor IDs, source/target public ports, exact route points and all62pair incidences. Future fixes could reserve distinct lanes and reduce crossings while preserving endpoints, pinned positions and expansion continuity. No fix is applied or accepted here; actual publication-scale pixels, glyphs/arrowheads and export consistency still need review.
