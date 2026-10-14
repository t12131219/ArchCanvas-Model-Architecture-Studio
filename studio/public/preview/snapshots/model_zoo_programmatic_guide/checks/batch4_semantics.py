#!/usr/bin/env python3
"""Reproducible negative checks for the reviewed batch4 IR and caller evidence.

Only this prototype's adapters and validators run. Upstream Python/notebooks
are read as data, never imported or executed. This does not prove equivalence.
"""
import argparse,copy,importlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from models import BATCHES
from verify import source_checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated',type=Path,default=HERE/'generated')
    parser.add_argument('--out',type=Path,default=HERE/'generated/batch4_semantic_review.json')
    args=parser.parse_args();positive=[];negative=[];documents={}
    for key in BATCHES['batch4']:
        folder=args.generated/key
        ir=json.loads((folder/'semantic_ir.json').read_text())
        evidence=json.loads((folder/'source_evidence.json').read_text())
        adapter=importlib.import_module('adapters.'+key)
        checks=adapter.validate_ir(ir)
        source=source_checks(folder,evidence,ir)
        documents[key]=(ir,evidence,folder,adapter)
        positive.append(dict(model=key,passed=True,semantic_checks=len(checks),source=source))
    def reject(key,label,mutate):
        ir,evidence,folder,adapter=documents[key];bad=copy.deepcopy(ir)
        mutate(bad)
        try:adapter.validate_ir(bad)
        except ValueError as exc:negative.append(dict(model=key,case=label,rejected=True,error=str(exc)))
        else:raise AssertionError('Undetected semantic mutation: '+key+' '+label)
    def node(ir,identity):return next(n for n in ir['nodes'] if n['id']==identity)
    reject('mobilenetv3','IR4 SE gate incorrectly replaced by Sigmoid',
           lambda ir:node(ir,'m3.block4.se.gate').update(kind='sigmoid'))
    reject('mobilenetv3','IR4 squeeze width incorrectly set to unrounded C/4',
           lambda ir:node(ir,'m3.block4.se.fc1').update(out_channels=18))
    reject('mobilenetv3','IR12 SE retained input incorrectly sourced from block input',
           lambda ir:next(e for e in ir['edges'] if e['src']=='m3.block12.se' and e['role']=='retained_input').update(src='m3.block12'))
    reject('mobilenetv3','replacement head incorrectly assigned classifier.1 identity',
           lambda ir:node(ir,'m3.fc2').update(parameter='classifier.1'))
    reject('resnet101','Stage3 identity repeat incorrectly reduced22 to5',
           lambda ir:node(ir,'r101.stage3.identities')['repeat'].update(count=5))
    reject('vgg19','stale class name used to reduce actual Conv depth16 to13',
           lambda ir:ir['profile'].update(actual_convolution_depth=13))
    for key in ('convgan','dcwgan'):
        reject(key,'caller fake training detach incorrectly permits gradient to G',
               lambda ir,key=key:node(ir,key+'.detach').update(gradient_to_generator=True))
        reject(key,'noise lower bound incorrectly changed to Gaussian-like range',
               lambda ir,key=key:node(ir,key+'.noise').update(low=-2.))
    reject('graphnet','registered fixed adjacency incorrectly made learnable',
           lambda ir:node(ir,'graphnet.buffer').update(learnable=True))
    reject('graphnet','source Euclidean distance incorrectly squared in kernel',
           lambda ir:node(ir,'graphnet.kernel').update(distance_squared=True))
    key='mobilenetv3';ir,evidence,folder,_=documents[key]
    reference=next(s for s in evidence['symbols'] if s.endswith('::__module__'))
    for field,value in [('end',evidence['symbols'][reference]['end']-1),('snippet','invented caller code')]:
        bad=copy.deepcopy(evidence);bad['symbols'][reference][field]=value
        try:source_checks(folder,bad,ir)
        except ValueError as exc:negative.append(dict(model=key,case='module caller evidence tamper: '+field,rejected=True,error=str(exc)))
        else:raise AssertionError('Undetected module source evidence tamper: '+field)
    result=dict(passed=True,scope='batch4 source-bound IR and module caller evidence',
                model_executed=False,positive=positive,negative=negative,
                limitation='selected-profile assertions and deliberate negative examples; not full model equivalence')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(positive)} positive models; {len(negative)} deliberately incorrect cases rejected. {args.out}')


if __name__=='__main__':main()
