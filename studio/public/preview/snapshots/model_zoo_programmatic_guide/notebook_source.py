"""Deterministic cell extraction. Preserves Python percent-format continuation."""
import re


def extract(notebook):
    lines=[];mapping=[]
    for index,cell in enumerate(notebook['cells']):
        if cell['cell_type']!='code':continue
        source=cell['source'];source=''.join(source) if isinstance(source,list) else source
        lines.append(f'# %% Notebook cell {index}\n')
        for cell_line,line in enumerate(source.splitlines(),1):
            mapping.append(dict(derived_line=len(lines)+1,cell_index=index,cell_line=cell_line))
            magic=bool(re.match(r'^\s*(?:%{1,2}[A-Za-z_]\w*\b|![A-Za-z_])',line))
            lines.append(('# NOTEBOOK_MAGIC '+line if magic else line)+'\n')
        lines.append('\n')
    return ''.join(lines),mapping
