from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as E

formal = Path.cwd()
base = formal / 'docs/evidence/m4-monochrome-role-work/pixel-review-attempt-1'
src = formal / 'docs/evidence/m4-monochrome-role-work/browser-current'
notes = {
    'cnn-level0-monochrome-180': {
        'originals': ['fit.jpg', 'local.jpg'],
        'result': 'bounded-local-role-distinction-observed',
        'observations': [
            'At 100% native local pixels, stem-to-blocks residual has separated long dashes; adjacent data is solid. Short collapsed residual route is straight, with two separated target ports, and no route over the node caption.',
            'Publication SVG converted pixels show full CNN chain and clear Data/Residual role samples. No node/legend collision is visible.',
            'Fit 44% is useful for composition but small captions and dash classification cannot be certified from fit alone. Large unused right page area remains; physical publication is not approved.',
        ],
    },
    'cnn-level0-monochrome-85': {
        'originals': ['fit.jpg', 'local.jpg'],
        'result': 'bounded-local-role-distinction-observed',
        'observations': [
            'Native matching revision4 fit/local pixels show the same separated solid data and long-dash residual at 100%. The extra expanded-fit revision5 experiment is excluded from this case review.',
            'Actual publication SVG conversion at 2x scene units is an enlarged digital observation; although identical world geometry is readable here, this is not an 85mm printed/actual-size readability test.',
            'Full role legend is visible and separated from node legend in converted publication pixels.',
        ],
    },
    'transformer-level3-monochrome-180': {'originals':['fit.jpg','local.jpg'],'result':'deep-transformer-role-samples-distinct-route-tracing-limited','observations':['Native fit14% is too small to assess role dashes, arrows or captions. Local58% shows ordinary vertical data and exterior residual/memory/mask channels but endpoints span far outside that local view.','Actual SVG converted full image shows a3213-unit tall two-column architecture. Encoder/decoder nested boundaries create multiple long exterior corridors; lower decoder has a long blank vertical region below its last node before final output projection. The full-page render remains difficult to navigate and trace.','Converted publication frontier shows mask paths overlapping source/target and same-gray data/residual lanes. Four different role legend samples are legible at converted footer scale, but they cannot resolve coincident routes.','Physical180mm readability, full canonical route tracing, global aesthetics and human usability are not approved.']},
    'cnn-level0-paper-180': {'originals':['fit.jpg','local.jpg'],'result':'collapsed-retained-layout-large-void','observations':['Native fit17% visibly shows an excessive empty vertical region after collapsed blocks. Actual SVG viewBox is595x2526; blocks bottom423 to pool top2030 leaves1607world units of empty space connected by one straight data arrow. This document arose after prior deep expansion and retained layout; it does not demonstrate compact collapse recovery.','Native local100% shows solid gray data and gold residual between stem and collapsed blocks, with no new role legend in paper mode. That mode scope matches the monochrome-only role-key change.','Converted publication full image confirms large void and wasteful aspect ratio. Publication aesthetics are not approved despite artifact consistency; final physical font and readability are not reviewed.']},
    'cnn-level2-monochrome-180': {'originals':['fit.jpg','local.jpg'],'result':'deep-hierarchy-tracing-limited','observations':['Native fit at17% cannot show caption or role-dash details. Native local58% gives a readable central block1/block2 corridor and dashed residual channel, but each full residual endpoint pair spans beyond that viewport.','The actual publication SVG conversion preserves the tall full deep hierarchy and clear Data/Residual legend. Long residual channels follow multiple nested borders; line style distinguishes role but does not resolve tall-page navigation or corridor aesthetics.','Physical180mm final-width readability, PDF font fidelity and human tracing are unapproved.']},
    'cnn-level2-monochrome-85': {'originals':['fit.jpg'],'result':'deep-hierarchy-fit-insufficient','observations':['The native fit screenshot at17% makes captions, role dashes and arrow routing unreadable; it is useful only for whole-page composition. No local screenshot was supplied for this case.','Actual publication SVG conversion shows the full deep hierarchy and clear Data/Residual samples, but residual edge9 and edge18 each take long exterior detours around nested boundaries. Their long dashes remain identifiable while zoomed, yet the routes create large unused corridors and visual competition with nested containers.','Independent axis-aligned relation check found same-tensor data edges2/3 share an intentional 88-unit vertical corridor and 70.67-unit horizontal segment; this is a collapsed/duplicated data route observation, not a failure by itself.','Physical 85mm readability, PDF fonts and human tracing are not certified.']},
    'cnn-level1-monochrome-180': {'originals':['fit.jpg','local.jpg'],'result':'nested-residual-routing-visual-limit','observations':['Native local pixels show input stem data and long-dash residual feeding the two expanded residual blocks; their distinct line roles remain visible at 100%.','The direct input data route detours left around the parent boundary before entering the nested block, while the residual route detours right. These separated channels are technically distinguishable but asymmetric and use a narrow boundary corridor; this remains a routing-aesthetics limitation.','The 180mm fit view is too small to judge the dashed channels or captions. Actual publication SVG conversion is digital observation and does not certify physical 180mm print readability.','The converted publication role legend shows Data and Residual samples clearly.']},
    'cnn-level1-monochrome-85': {'originals':['fit.jpg','local.jpg'],'result':'nested-residual-routing-visual-limit','observations':['Native local pixels show input stem data and long-dash residual feeding the two expanded residual blocks; their distinct line roles remain visible at 100%.','The direct input data route detours left around the parent boundary before entering the nested block, while the residual route detours right. At this 85mm case the routes are technically separated but asymmetric and consume a narrow corridor beside the boundary; this is a readability/aesthetics limitation, not a canonical fact failure.','Fit view is too small to judge the dashed channels or captions; physical 85mm readability is not certified.','The matching actual SVG conversion is digital observation only; role legend and residual sample are checked there, not as a print test.']},
    'transformer-level0-monochrome-180': {
        'originals': ['fit.jpg', 'local.jpg', 'footer-local.jpg', 'export-failed-attempt-1.jpg'],
        'result': 'role-key-improved-routing-trace-limited',
        'observations': [
            'Native local pixels show memory dash-dot across a short encoder/decoder corridor, solid data, long-dash residual stubs and short-dash mask. Actual publication conversion makes all four legend samples legible and visually different.',
            'Mask edges7/45/46 share y209 and y397 horizontal lanes and join/overlap independently bound paths. The y209 lane lies about1 world unit above source/target token top boundaries (y210). The y397 lane meets data/residual vertical input segments; parts of long-dash residual horizontals coincide with same-gray mask short dashes. These pixels do not make canonical routes easy to trace.',
            'Three exterior mask detours require4 bends each; edge7 extends beyond the ancestor right outline. Correctness/obstacle legality is not visually certified; this is a retained aesthetics/tracing limitation.',
            'Footer-local browser screenshot clips the first role-legend row with the bottom command strip and excludes the Mask row. It cannot certify browser role-footer readability; root has been asked for a new separate pan capture. Publication-converted footer does show both rows fully.',
            'Export-failed-attempt-1.jpg visibly reports unsupported publication attribute data-edge-legend-id; kept as historical failed attempt, not current PDF success. No PDF pixel/font review is performed.',
        ],
    },
}

for case, n in notes.items():
    if len(sys.argv) > 1 and case != sys.argv[1]:
        continue
    target = base / case
    receipt = json.loads((target / 'conversion-receipt.json').read_text())
    viewed = [src / case / x for x in n['originals']] + [target / x for x in ['actual-publication-svg-converted.png', 'actual-publication-svg-converted-frontier.png', 'actual-publication-svg-converted-footer.png']]
    metadata = E.parse(src / case / 'figure.svg').getroot().find('{http://www.w3.org/2000/svg}metadata')
    bindings = json.loads(metadata.text).get('renderedBindings', [])
    roles = {b['sceneEdgeId']: b['role'] for b in bindings}
    appearance = [{**e, 'roleFromActualMetadata': roles.get(e['id'])} for e in receipt['edgeFacts']]
    unchanged = []
    for b in receipt['beforeBindings']:
        path = formal / b['path']
        data = path.read_bytes()
        unchanged.append({'path': b['path'], 'exact': len(data) == b['bytes'] and hashlib.sha256(data).hexdigest() == b['sha256']})
    review = {
        'kind': 'independent-AI-pixel-observation',
        'humanParticipant': False,
        'modelExecuted': False,
        'case': case,
        **n,
        'personallyViewed': [{'path': str(p.relative_to(formal)), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in viewed],
        'actualMetadataEdgeAppearance': appearance,
        'imageStatePairs': [{'before': s['before'], 'after': s['after'], 'stateEqual': s['stateEqual']} for s in receipt['imageStatePairs']],
        'originalInputsRecheck': unchanged,
        'allOriginalInputsUnchanged': all(b['exact'] for b in unchanged),
        'excludedClaims': ['Presented FPS or input-to-paint performance', 'Human novice usability or participant completion', 'PDF rendered pixels, font embedding or font-family fidelity', 'Physical final-width publication readability', 'Complete movement/history/save workflow', 'Global route aesthetics/correctness'],
    }
    output = target / 'review.json'
    if output.exists():
        raise RuntimeError(f'Existing report is immutable: {output}')
    output.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n')
    print(case, len(viewed), review['allOriginalInputsUnchanged'])
