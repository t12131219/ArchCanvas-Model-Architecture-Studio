"""Final captured inventory/state/binding readback; no browser mutation."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[4];WORK=ROOT/'docs/evidence/m4-draft-port-legibility-work';SOURCE=WORK/'browser-current-attempt-3';OUT=Path(__file__).parent/'current-final-readback-11'
OUT.mkdir(exist_ok=False);inputs=[];checks=[]
def check(name,value,detail=None):checks.append({'name':name,'pass':bool(value),'detail':detail})
def capture(path):
    data=path.read_bytes();target=OUT/'inputs'/path.relative_to(ROOT) if path.is_relative_to(ROOT) else OUT/'inputs/external'/path.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    inputs.append({'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'snapshot':str(target.relative_to(OUT))});return data
metadata=json.loads(capture(SOURCE/'manifest.json'));receipt=json.loads(capture(SOURCE/'receipt.json'))
check('current inventory exactly46raw artifacts',len(metadata['files'])==46)
check('current inventory exactly11complete frame records',len(metadata['frames'])==11)
check('current receipt11frames22images',receipt['frames']==11 and receipt['capturedImages']==22)
check('all frame records bound to current asset and public stable',all(row['assets']==['/assets/index-DuFXKOwG.js','/assets/index--unhoRTb.css'] and row['publicStable'] for row in metadata['frames']))
check('receipt retains zero humans and no model execution',receipt['humanParticipants']==0 and receipt['modelExecuted'] is False)
check('receipt retains current Concat modal pixel failures and historical camera scope',any('CurrentConcat03bothpixels failed' in value for value in receipt['limits']) and any('No currentnativecamera4direction repetition' in value for value in receipt['limits']))
for row in metadata['files']:
    data=capture(ROOT/row['path']);check('captured bytes match inventory '+row['path'],hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['bytes'])
check('inventory22jpg11DOM11public2Python',sum(row['path'].endswith('.jpg') for row in metadata['files'])==22 and sum(row['path'].endswith('.dom.txt') for row in metadata['files'])==11 and sum(row['path'].endswith('.public.json') for row in metadata['files'])==11 and sum(row['path'].endswith('.py') for row in metadata['files'])==2)
final=json.loads((SOURCE/'11-final-preview.public.json').read_text());generated=json.loads((SOURCE/'10-current-residual-generated-dialog.public.json').read_text());baseline=json.loads((SOURCE/'04-residual-preset-current.public.json').read_text())
check('final preview three public states stable',final['before']==final['middle']==final['after'] and final['publicStable'])
check('final preview public world exactly equals generated dialog underlying world',final['after']==generated['after'])
check('final preview restored exact baseline nodes/ports/edges/camera',all(final['after'][key]==baseline['after'][key] for key in ['nodes','edges','camera','flow','assets','viewport','warnings']))
check('final preview current residual six nodes and six paths',len(final['after']['nodes'])==6 and len(final['after']['edges'])==6)
phase_results=[];current_inputs={}
for name in ['current-target-01-04','current-moves-save-source-05-10']:
    folder=Path(__file__).parent/name;report=json.loads(capture(folder/'report.json'));manifest=json.loads(capture(folder/'manifest.json'))
    phase_results.append({'phase':name,'counts':report['counts'],'pass':report['pass']})
    check('bounded independent phase passed '+name,report['pass'])
    for row in manifest['inputs']:
        path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
        current_inputs[str(path)]={'source':path,'sha256':row['sha256'],'snapshot':folder/row['snapshot']}
for path,row in current_inputs.items():
    check('prior current input/source+snapshot unchanged '+path,hashlib.sha256(row['source'].read_bytes()).hexdigest()==row['sha256'] and hashlib.sha256(row['snapshot'].read_bytes()).hexdigest()==row['sha256'])
capture(Path(__file__))
report={'schema':'archcanvas-dufx-browser-final-independent-readback/1','pass':all(row['pass'] for row in checks),'checks':checks,'counts':{'checks':len(checks),'passed':sum(row['pass'] for row in checks),'failed':sum(not row['pass'] for row in checks),'currentArtifactBindings':len(metadata['files']),'priorUniqueCurrentInputs':len(current_inputs)},'phaseResultsSeparate':phase_results,'scope':{'currentBrowserFrames':11,'currentBrowserImages':22,'publicSamples':33,'artifactConsistencyIsPixelApproval':False,'pixelInspection':False,'modelExecuted':False,'fourCurrentNodeDirections':True,'currentCameraFourDirections':False,'redoOnCurrent':False,'globalOptimality':False,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');readback=[{'path':row['path'],'sourceUnchanged':hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],'snapshotMatches':hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']} for row in inputs]
(OUT/'manifest.json').write_text(json.dumps({'inputs':inputs,'readback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(inputs),'phaseResultsSeparate':phase_results,'failed':[row for row in checks if not row['pass']]},ensure_ascii=False));sys.exit(0 if report['pass'] else 2)
