"""Presentation-only roles and typography, matched to the Transformer prototype.

These aliases never change an adapter's operator kind, parameter identity or IR.
Unlisted groups remain neutral rather than guessing semantics from their labels.
"""

NAME = 'transformer-paper'
VERSION = 1
FONT = 'DejaVu Sans, Arial, sans-serif'
INK = '#263348'
TEXT = '#172336'
SECONDARY = '#344155'
PALETTE = dict(
    root='#ffffff', group='#ffffff', inner='#fffaf6', layer='#ffffff',
    encoder='#e7f5fe', decoder='#fff0f5', season='#e7f5fe', trend='#fff0f5',
    embedding='#f8d4e1', input='#f8d4e1', output='#dfdff8',
    attention='#ffddb3', ffn='#c8ebfb', mixing='#c8ebfb',
    norm='#fff6bd', linear='#dfdff8', softmax='#c9f1cd',
    decomposition='#d6f0df', tensor='#cdeaf8',
    activation='#f3f5f7', control='#f3f5f7',
)
TYPE = dict(title=30, subtitle=16, module=22, inner=20, operator=20,
            shape=16, detail=14, evidence=12, footer=14, line_height=1.18)

ROLES = {}
# Main components in one layer share a frame width, like the reference's
# Attention / FFN / Add & Norm panels. Their internal operators stay centered.
FILL_WIDTH = set()


def assign(role, *identities):
    ROLES.update({identity: role for identity in identities})


# Autoformer: progressive decomposition is distinct from normalization.
assign('root', 'af_model')
assign('encoder', 'af_encoder')
assign('layer', 'af_enc_layer')
assign('decoder', 'af_decoder_init', 'af_dec_layer')
assign('group', 'af_prepare', 'af_init_states', 'af_final_parts', 'af_seasonal_seed')
assign('embedding', 'af_enc_embedding', 'af_dec_embedding')
assign('inner', 'af_enc_embedding_terms', 'af_dec_embedding_terms')
assign('ffn', 'af_enc_ffn', 'af_dec_ffn')
assign('decomposition', 'af_enc_decomp1', 'af_enc_decomp2',
       'af_dec_decomp1', 'af_dec_decomp2', 'af_dec_decomp3')
assign('norm', 'af_memory', 'af_dec_norm', 'af_enc_embedding_sum', 'af_dec_embedding_sum',
       'af_enc_ac_add', 'af_enc_ffn_add', 'af_dec_self_add', 'af_dec_cross_add',
       'af_dec_ffn_add', 'af_sum')
assign('linear', 'af_seasonal_output')
assign('decomposition', 'af_trend_update', 'af_trend_init', 'af_trend_output')
FILL_WIDTH.update(('af_enc_ac_residual', 'af_enc_decomp1', 'af_enc_ffn', 'af_enc_decomp2',
                   'af_dec_self_residual', 'af_dec_decomp1', 'af_dec_cross_residual',
                   'af_dec_decomp2', 'af_dec_ffn', 'af_dec_decomp3'))
for prefix in ('af_enc_ac', 'af_dec_self', 'af_dec_cross'):
    assign('attention', prefix)
    assign('attention_residual', prefix + '_residual')
    assign('inner', prefix + '_operands', prefix + '_corr')

# iTransformer: operation family colors, independent of layer/parameter identity.
assign('root', 'it.model')
assign('encoder', 'it.encoder')
assign('embedding', 'it.embedding', 'it.marks')
assign('linear', 'it.head')
for number in (1, 2):
    prefix = f'it.enc{number}'
    assign('layer', prefix)
    assign('attention_residual', prefix + '.attention_residual')
    assign('ffn_residual', prefix + '.ffn_residual')
    assign('attention', prefix + '.attention')
    assign('ffn', prefix + '.ffn')
    assign('norm', prefix + '.add1', prefix + '.add2')
    assign('softmax', prefix + '.attention.softmax')
    FILL_WIDTH.update(prefix + suffix for suffix in ('.attention_residual', '.norm1',
                                                    '.ffn_residual', '.norm2', '.attention', '.ffn'))
    for suffix in ('operands', 'weights', 'qk', 'q', 'k', 'v'):
        assign('inner', prefix + '.attention.' + suffix)

# PatchTST: BatchNorm, RevIN and feature residual Add share the yellow family.
assign('root', 'patchtst')
assign('tensor', 'patch_patching')
assign('embedding', 'patch_embedding')
assign('encoder', 'patch_encoder')
assign('linear', 'patch_head')
for number in (1, 2):
    prefix = f'patch_layer{number}'
    assign('layer', prefix)
    assign('attention_residual', prefix + '_attn_res')
    assign('ffn_residual', prefix + '_ffn_res')
    assign('attention', prefix + '_attention')
    assign('inner', prefix + '_sdpa', prefix + '_sdpa_operands',
           prefix + '_weights', prefix + '_qkv')
    assign('ffn', prefix + '_ffn')
    assign('norm', prefix + '_attnadd', prefix + '_ffnadd')
    assign('softmax', prefix + '_softmax')
    FILL_WIDTH.update(prefix + suffix for suffix in ('_attn_res', '_bn1', '_ffn_res', '_bn2',
                                                    '_attention', '_ffn'))

# TimeMixer: time MLPs are blue; season/trend path panels are blue/pink.
# AvgPool builds a scale pyramid and is not a series decomposition operation.
assign('root', 'tm.model')
assign('tensor', 'tm.pyramid', 'tm.pool1', 'tm.pool2', 'tm.pool3')
assign('embedding', 'tm.embedding')
assign('encoder', 'tm.pdm')
assign('linear', 'tm.fmm')
assign('norm', 'tm.forecast_sum')
for scale in range(4):
    assign('group', f'tm.input_scale{scale}', f'tm.predict{scale}')
for block in (1, 2):
    prefix = f'tm.pdm{block}'
    assign('layer', prefix)
    assign('group', prefix + '.mix')
    assign('ffn', prefix + '.out_cross')
    assign('norm', prefix + '.sum', prefix + '.add')
    FILL_WIDTH.update(prefix + suffix for suffix in ('.decomp', '.sum', '.out_cross', '.add'))
    for component in ('season', 'trend'):
        assign(component, prefix + '.' + component)
        for step in range(3):
            identity = prefix + f'.{component}.step{step}'
            assign('ffn', identity)
            assign('norm', identity + '.add')


def node_style(node, expanded=False):
    role = ROLES.get(node['id'], node.get('kind', 'group'))
    fill_role = role
    if role in ('attention_residual', 'ffn_residual'):
        fill_role = 'group' if expanded else ('attention' if role == 'attention_residual' else 'ffn')
    if role == 'layer' and not expanded:
        fill_role = 'encoder'
    # The orange frame identifies Attention; its individual arithmetic steps
    # use neutral operator boxes, as in the reference Transformer's SDPA.
    if not node.get('mode') and role == 'attention':
        fill_role = 'control'
    outer = role in ('root', 'encoder', 'decoder', 'season', 'trend')
    title_size = 22 if role == 'root' else 24 if outer else TYPE['inner'] if role == 'inner' else TYPE['module']
    return dict(role=role, fill_role=fill_role, fill=PALETTE.get(fill_role, PALETTE['control']),
                stroke=INK, stroke_width=2.5 if outer else 1.6 if role == 'inner' else 2,
                radius=18 if outer else 8 if role == 'inner' else 10,
                title_size=title_size)


def manifest():
    return dict(name=NAME, version=VERSION, font=FONT, text=TEXT, line=INK,
                palette=PALETTE, typography=TYPE,
                fill_width_nodes=sorted(FILL_WIDTH),
                semantics='presentation-only role aliases; IR kinds and parameter identities are unchanged')
