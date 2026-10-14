"""Transformer-paper styling reused across reviewed architecture batches."""
NAME='transformer-paper-model-zoo'
VERSION=1
FONT='DejaVu Sans, Arial, sans-serif'
INK='#263348'
TEXT='#172336'
SECONDARY='#344155'
PALETTE=dict(root='#ffffff',group='#ffffff',inner='#fffaf6',layer='#ffffff',
             encoder='#e7f5fe',decoder='#fff0f5',embedding='#f8d4e1',
             input='#f8d4e1',output='#dfdff8',attention='#ffddb3',
             ffn='#c8ebfb',mixing='#c8ebfb',conv='#c8ebfb',pool='#d6f0df',
             norm='#fff6bd',concat='#fff6bd',linear='#dfdff8',softmax='#c9f1cd',
             sampling='#c9f1cd',recurrent='#ffddb3',decomposition='#d6f0df',
             tensor='#cdeaf8',activation='#f3f5f7',control='#f3f5f7')
TYPE=dict(title=30,subtitle=16,module=22,inner=20,operator=20,
          shape=16,detail=14,evidence=12,footer=14,line_height=1.18)
ROLES={}
FILL_WIDTH=set()


def configure(model):
    ROLES.clear();ROLES.update(model.get('visual_roles',{}))
    FILL_WIDTH.clear();FILL_WIDTH.update(model.get('fill_width',[]))


def node_style(node,expanded=False):
    role=ROLES.get(node['id'],node.get('kind','group'))
    fill_role=role
    if role in ('attention_residual','ffn_residual','conv_residual'):
        fill_role='group' if expanded else {'attention_residual':'attention',
                  'ffn_residual':'ffn','conv_residual':'conv'}[role]
    if role=='layer' and not expanded:fill_role='encoder'
    outer=role in ('root','encoder','decoder')
    title_size=22 if role=='root' else 24 if outer else TYPE['inner'] if role=='inner' else TYPE['module']
    return dict(role=role,fill_role=fill_role,fill=PALETTE.get(fill_role,PALETTE['control']),
                stroke=INK,stroke_width=2.5 if outer else 1.6 if role=='inner' else 2,
                radius=18 if outer else 8 if role=='inner' else 10,title_size=title_size)


def manifest():
    return dict(name=NAME,version=VERSION,font=FONT,text=TEXT,line=INK,palette=PALETTE,
                typography=TYPE,fill_width_nodes=sorted(FILL_WIDTH),
                visual_roles=dict(sorted(ROLES.items())),
                semantics='presentation aliases only; color does not imply mathematical equivalence or parameter sharing')
