#!/usr/bin/env python3
"""Independent LSTM equation/edge table and semantic negative cases; no model execution."""
from pathlib import Path
import sys, json, hashlib, copy, argparse
HERE=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,help='Save the hash-bound review record')
args=parser.parse_args()
sys.path.insert(0,str(HERE))
from adapters import lstmcell

model=lstmcell.build()
expected=[]
def add(a,b,sp='out',dp='in',role='tensor'):
    expected.append((a,sp,b,dp,role))
for t in range(3):
    p=f'lstmcell.step{t}'
    # Independent equation binding table: two matmuls and source-ordered bias/add chain.
    for a,b,dp in [('x','x_mm','in'),('hx','h_mm','in'),('x_mm','b_ih','in'),
                   ('b_ih','affine_add','x_affine'),('h_mm','affine_add','h_affine'),
                   ('affine_add','b_hh','in'),('b_hh','chunk','in')]:
        add(p+'.'+a,p+'.'+b,dp=dp)
    for slot,gate in enumerate(('i','f','g','o')):
        add(p+'.chunk',p+'.'+gate,sp=f'item[{slot}]',role='gate_slice')
    # c=f*c_prev+i*g; h=o*tanh(c).
    for a,b,dp in [('f','forget_mul','f'),('cx','forget_mul','previous_c'),
                   ('i','input_mul','i'),('g','input_mul','g'),
                   ('forget_mul','cy','retained'),('input_mul','cy','new'),
                   ('cy','tanh_c','in'),('tanh_c','hy','tanh_c'),('o','hy','o'),
                   ('hy','return','output_hidden'),('hy','return','state_hidden'),('cy','return','state_cell')]:
        add(p+'.'+a,p+'.'+b,dp=dp)
add('lstmcell.sequence','lstmcell.unbind')
for t in range(3):
    add('lstmcell.unbind',f'lstmcell.x{t}',sp=f'item[{t}]',role='time_slice')
    add(f'lstmcell.x{t}',f'lstmcell.step{t}.x')
    add(f'lstmcell.step{t}.hy','lstmcell.stack',dp=f'item[{t}]',role='sequence_output')
for t in (1,2):
    add(f'lstmcell.step{t-1}.hy',f'lstmcell.step{t}.hx',role='recurrent_state')
    add(f'lstmcell.step{t-1}.cy',f'lstmcell.step{t}.cx',role='recurrent_state')
add('lstmcell.stack','lstmcell.return',dp='output_sequence')
add('lstmcell.step2.hy','lstmcell.return',dp='final_hidden',role='final_state')
add('lstmcell.step2.cy','lstmcell.return',dp='final_cell',role='final_state')
add('lstmcell.initial_h','lstmcell.step0.hx',role='initial_state')
add('lstmcell.initial_c','lstmcell.step0.cx',role='initial_state')
actual=[(e['src'],e.get('src_port','out'),e['dst'],e.get('dst_port','in'),e.get('role','tensor')) for e in model['extra_edges']]
assert len(actual)==len(set(actual)), 'Duplicate explicit edge'
assert set(actual)==set(expected), {'missing':sorted(set(expected)-set(actual)),'extra':sorted(set(actual)-set(expected))}
folder=HERE/'generated/lstmcell'
evidence=json.loads((folder/'source_evidence.json').read_text())
ir=json.loads((folder/'semantic_ir.json').read_text())
ir_edges=[(e['src'],e['src_port'],e['dst'],e['dst_port'],e['role']) for e in ir['edges']]
assert len(ir_edges)==len(expected) and set(ir_edges)==set(expected), 'IR introduced unsupported rank/containment edges'
nodes={n['id']:n for n in ir['nodes']}
for t in range(3):
    p=f'lstmcell.step{t}'
    assert nodes[p]['instance_identity']=='self.cell' and nodes[p]['parameter_scope']=='cell'
    for slot,g in enumerate(('i','f','g','o')):
        assert nodes[p+'.'+g]['parameter_slice']['rows']==[slot*16,(slot+1)*16]
        assert nodes[p+'.'+g]['parameter_slice']['parameters']==['cell.weight_ih','cell.weight_hh','cell.bias_ih','cell.bias_hh']
        assert nodes[p+'.'+g]['activation']==('tanh' if g=='g' else 'sigmoid')
    assert nodes[p+'.return']['aliases']=={'output':'state[0]'}
assert not any(n['kind'] in ('concat','softmax','norm') for n in ir['nodes']), 'Visual role leaked into mathematical operator kind'
positive=lstmcell.validate_ir(ir)
negative=[]
def challenge(label,mutate):
    damaged=copy.deepcopy(ir);mutate(damaged)
    try:lstmcell.validate_ir(damaged)
    except ValueError as exc:
        negative.append({'case':label,'status':'REJECTED','reason':str(exc)})
    else:negative.append({'case':label,'status':'ACCEPTED_UNEXPECTEDLY'})
def node(data,id):return next(n for n in data['nodes'] if n['id']==id)
def edge(data,src,dst):return next(e for e in data['edges'] if e['src']==src and e['dst']==dst)
challenge('chunk forget gate wrongly bound to input-gate slice',lambda d:edge(d,'lstmcell.step1.chunk','lstmcell.step1.f').update(src_port='item[0]'))
challenge('candidate row slice changed from g to f',lambda d:node(d,'lstmcell.step1.g')['parameter_slice'].update(rows=[16,32]))
challenge('candidate tanh changed into sigmoid',lambda d:node(d,'lstmcell.step1.g').update(activation='sigmoid'))
challenge('input MatMul incorrectly consumes hx',lambda d:edge(d,'lstmcell.step1.x','lstmcell.step1.x_mm').update(src='lstmcell.step1.hx'))
challenge('hidden state lane replaced by cell state',lambda d:edge(d,'lstmcell.step0.hy','lstmcell.step1.hx').update(src='lstmcell.step0.cy'))
challenge('bias addition order incorrectly rewired',lambda d:edge(d,'lstmcell.step1.affine_add','lstmcell.step1.b_hh').update(src='lstmcell.step1.h_mm'))
challenge('cell returned instead of output-hidden alias',lambda d:edge(d,'lstmcell.step1.hy','lstmcell.step1.return').update(src='lstmcell.step1.cy'))
challenge('initial state assumed zeros',lambda d:node(d,'lstmcell.initial_c').update(initial_state_default='zeros'))
challenge('stack hidden sequence order reversed',lambda d:node(d,'lstmcell.stack')['ordered_inputs'].reverse())
challenge('final cell from penultimate time step',lambda d:edge(d,'lstmcell.step2.cy','lstmcell.return').update(src='lstmcell.step1.cy'))
challenge('time step introduces independent weights',lambda d:node(d,'lstmcell.step1.x_mm').update(parameter='step1.cell.weight_ih'))
challenge('invented c-prev peephole',lambda d:d['edges'].append({'src':'lstmcell.step1.cx','dst':'lstmcell.step1.i','src_port':'out','dst_port':'peephole','role':'tensor'}))
result={'adapter_sha256':hashlib.sha256((HERE/'adapters/lstmcell.py').read_bytes()).hexdigest(),
 'source_snapshot':evidence['source_snapshot_sha256'],'status':'PASS' if all(n['status']=='REJECTED' for n in negative) else 'FAILED',
 'scope':'reviewed adapter evaluated only; upstream source never imported or executed',
 'nodes':len(ir['nodes']),'edges':len(ir['edges']),'expected_edge_binding_count':len(expected),
 'positive_model_checks':positive,'negative_cases':negative,'exact_edge_set':'PASS',
 'typed_operand_endpoints':'All 88 explicit endpoint/port/role tuples match independently reviewed source equations and time loop; no containment edges generated.'}
result['semantic_ir_sha256']=hashlib.sha256((folder/'semantic_ir.json').read_bytes()).hexdigest()
if args.out:
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'nodes':result['nodes'],'edges':result['edges'],
                  'positive_checks':len(positive),'negative_cases':len(negative)},ensure_ascii=False))
raise SystemExit(0 if result['status']=='PASS' else 1)
