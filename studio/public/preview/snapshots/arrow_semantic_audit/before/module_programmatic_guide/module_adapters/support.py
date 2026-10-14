"""Common declaration defaults; no semantic graph inferred here."""
from spec import chain,op,graph,parallel,ref

def finish(model):
    model['artifact_scope']='module'
    model['view_titles']=['Module overview','Module decomposition','Operators & tensor flow']
    model.setdefault('aux_inputs',[]);model.setdefault('extra_edges',[])
    model.setdefault('view_overrides',{})
    model['profile']['model_executed']=False
    model['profile']['artifact_scope']='module'
    return model
