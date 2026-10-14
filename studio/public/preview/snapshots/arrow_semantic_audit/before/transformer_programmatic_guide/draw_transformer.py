#!/usr/bin/env python3
"""Source-grounded Transformer diagrams; Python 3 standard library only.

This is a hand-written semantic adapter for the supplied educational implementation,
not a general Python/model reverse compiler. Source is ast.parse'd and never imported.
The three views share semantic_ir.json. Font sizing is conservative estimation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
from pathlib import Path
import zipfile


HERE = Path(__file__).resolve().parent
COLORS = dict(embedding="#f8d4e1", ffn="#c8ebfb", attention="#ffddb3",
              norm="#fff6bd", linear="#dfdff8", softmax="#c9f1cd",
              tensor="#cdeaf8", encoder="#e7f5fe", decoder="#fff0f5",
              control="#f3f5f7", text="#172336", line="#263348")
FONT = "DejaVu Sans, Arial, sans-serif"
ARROW_LENGTH = 9
MIN_TERMINAL = 18
ROUTE_INSET = 18


def read_source(args):
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            names = [n for n in archive.namelist() if n.endswith("/transformer.py")]
            if len(names) != 1:
                raise ValueError("Archive must contain exactly one transformer.py")
            return archive.read(names[0]).decode("utf-8"), str(Path(args.archive).resolve()) + "!" + names[0]
    path = Path(args.source).resolve()
    return path.read_text(encoding="utf-8"), str(path)


def extract_evidence(source, origin):
    tree = ast.parse(source, filename=origin)
    lines = source.splitlines()
    evidence = {}
    for item in tree.body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            evidence[item.name] = dict(symbol=item.name, start=item.lineno, end=item.end_lineno)
            if isinstance(item, ast.ClassDef):
                for member in item.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = item.name + "." + member.name
                        evidence[key] = dict(symbol=key, start=member.lineno, end=member.end_lineno)
    required = ["MultiHeadAttention", "MultiHeadAttention._split_heads", "MultiHeadAttention._combine_heads",
                "MultiHeadAttention.forward", "scaled_dot_product_attention", "PositionwiseFeedForward.forward",
                "PositionalEncoding.forward", "TokenEmbedding.forward", "EncoderLayer.forward",
                "DecoderLayer.forward", "Encoder.forward", "Decoder.forward", "Transformer.forward", "clones"]
    missing = [s for s in required if s not in evidence]
    if missing:
        raise ValueError("Unsupported adapter input: missing " + ", ".join(missing))
    # Guards are evidence checks, not a claim of full semantic verification.
    guards = ["self.norm1(x + self.dropout1(attn_out))", "self.w_q(query)", "key=memory",
              "return self.generator(decoder_out)", "self.activation = nn.ReLU()", "copy.deepcopy(module)"]
    for snippet in guards:
        if snippet not in source:
            raise ValueError("Unsupported adapter input; expected source fragment: " + snippet)
    for value in evidence.values():
        value["source"] = origin
        value["snippet"] = "\n".join(lines[value["start"] - 1:value["end"]])
    return dict(origin=origin, sha256=hashlib.sha256(source.encode()).hexdigest(),
                parser="ast.parse; no source imports or execution", symbols=evidence)


def make_ir(evidence):
    nodes, edges = [], []
    def node(id, kind, parent=None, rank=0, source=None, param_identity=None, **extra):
        ports = extra.pop("ports", ["in", "out"])
        n = dict(id=id, kind=kind, parent=parent, rank=rank, children=[],
                 ports=ports, source_evidence=source or [], param_identity=param_identity, **extra)
        nodes.append(n)
        return n
    def edge(src, dst, sp="out", dp="in", kind="tensor", **extra):
        edges.append(dict(id=f"{src}:{sp}->{dst}:{dp}", src=src, dst=dst,
                          src_port=sp, dst_port=dp, kind=kind, **extra))
    node("model", "model", source=["Transformer.forward"])
    for side in ("src", "tgt"):
        node(side + "_tokens", "input", "model", source=["Transformer.forward"])
        node(side + "_embed", "embedding", "model", source=["TokenEmbedding.forward"],
             param_identity=f"model.{side}_embedding.embedding.weight", scale="sqrt(D)")
        node(side + "_pe", "sinusoidal_pe", "model", source=["PositionalEncoding.forward"],
             buffer_identity="model.position.pe", dropout="folded")
        edge(side + "_tokens", side + "_embed")
        edge(side + "_embed", side + "_pe")
    for side, count in (("enc", 2), ("dec", 3)):
        cname = "Encoder" if side == "enc" else "Decoder"
        node(side, "serial_repeat", "model", source=[cname + ".forward", "clones"],
             count="N_encoder" if side == "enc" else "N_decoder", independent_parameters=True)
        node(side + ".layer_i", "layer", side, source=[cname + "Layer.forward"],
             param_identity=f"model.{'encoder' if side == 'enc' else 'decoder'}.layers[i]")
        operations = ["self", "ffn"] if side == "enc" else ["self", "cross", "ffn"]
        previous = "src_pe" if side == "enc" else "tgt_pe"
        for rank, op in enumerate(operations):
            id = side + "." + op
            symbol = "PositionwiseFeedForward.forward" if op == "ffn" else "MultiHeadAttention.forward"
            root_param = f"model.{'encoder' if side == 'enc' else 'decoder'}.layers[i].{'ffn' if op == 'ffn' else op + '_attn'}"
            node(id, "ffn" if op == "ffn" else "attention", side + ".layer_i", rank * 2,
                 [symbol, cname + "Layer.forward"], root_param,
                 attention_role=op if op != "ffn" else None,
                 ports=["in", "out", "memory"] if op == "cross" else ["in", "out"])
            edge(previous, id)
            if op == "ffn":
                children = [("linear1", "linear"), ("relu", "relu"), ("dropout", "dropout"), ("linear2", "linear")]
                for j, (name, kind) in enumerate(children):
                    node(id + "." + name, kind, id, j, [symbol], root_param + "." + name if kind == "linear" else None)
                for a, b in zip(children, children[1:]):
                    edge(id + "." + a[0], id + "." + b[0])
                edge(id, id + ".linear1", sp="in", kind="interface_binding")
                edge(id + ".linear2", id, dp="out", kind="interface_binding")
            else:
                for j, role in enumerate("qkv"):
                    node(id + "." + role, "linear_projection", id, 0, ["MultiHeadAttention.__init__", symbol],
                         root_param + ".w_" + role, input_identity="memory" if op == "cross" and role != "q" else previous,
                         parallel_group=id + ".qkv", output_shape="[B,Lq,D]" if role == "q" else "[B,Lk,D]")
                    edge(id, id + "." + role,
                         sp="memory" if op == "cross" and role != "q" else "in", kind="interface_binding")
                for j, (name, kind, sym) in enumerate([
                        ("split", "reshape_transpose", "MultiHeadAttention._split_heads"),
                        ("sdpa", "attention_math", "scaled_dot_product_attention"),
                        ("merge", "transpose_reshape", "MultiHeadAttention._combine_heads"),
                        ("wo", "linear", symbol)], start=1):
                    ports = ["q_in","k_in","v_in","q_out","k_out","v_out"] if name == "split" else ["q","k","v","out"] if name == "sdpa" else ["in","out"]
                    node(id + "." + name, kind, id, j, [sym], root_param + ".w_o" if name == "wo" else None,ports=ports)
                for role in "qkv":
                    edge(id + "." + role, id + ".split", dp=role+"_in")
                    edge(id + ".split", id + ".sdpa",sp=role+"_out",dp=role)
                edge(id + ".sdpa", id + ".merge")
                edge(id + ".merge", id + ".wo")
                seq = ["qkt", "scale", "mask", "softmax", "nan_guard", "attn_dropout", "av"]
                for j, name in enumerate(seq):
                    node(id + ".sdpa." + name, name, id + ".sdpa", j,
                         ["scaled_dot_product_attention"], conditional=name == "mask",
                         mask_semantics="boolean True => -inf; causal only when supplied" if name == "mask" else None,
                         mask_inputs=(["source_padding"] if side=="enc" or op=="cross" else ["caller_tgt_mask","target_padding"]) if name=="mask" else None,
                         ports=["q","k","out"] if name=="qkt" else ["a","v","out"] if name=="av" else ["in","out"])
                for a, b in zip(seq, seq[1:]):
                    edge(id + ".sdpa." + a, id + ".sdpa." + b,dp="a" if b=="av" else "in")
                for role in "qk":
                    edge(id + ".sdpa", id + ".sdpa.qkt",sp=role,dp=role,kind="interface_binding")
                edge(id + ".sdpa", id + ".sdpa.av",sp="v",dp="v",kind="interface_binding")
                edge(id + ".sdpa.av", id + ".sdpa",dp="out",kind="interface_binding")
                edge(id + ".wo", id, dp="out", kind="interface_binding")
            norm = side + ".norm" + str(rank + 1)
            node(norm, "postnorm", side + ".layer_i", rank * 2 + 1,
                 [cname + "Layer.forward"], f"model.{'encoder' if side == 'enc' else 'decoder'}.layers[i].norm{rank + 1}",
                 ports=["in", "skip", "out"], formula="LayerNorm(x + Dropout(sublayer(x)))")
            node(norm+".branch_dropout","dropout",norm,0,[cname+"Layer.forward"])
            node(norm+".add","add",norm,1,[cname+"Layer.forward"],ports=["x","f","out"])
            node(norm+".layernorm","layernorm",norm,2,[cname+"Layer.forward"],f"model.{'encoder' if side=='enc' else 'decoder'}.layers[i].norm{rank+1}")
            edge(norm,norm+".branch_dropout",sp="in",kind="interface_binding")
            edge(norm+".branch_dropout",norm+".add",dp="f")
            edge(norm,norm+".add",sp="skip",dp="x",kind="interface_binding")
            edge(norm+".add",norm+".layernorm")
            edge(norm+".layernorm",norm,dp="out",kind="interface_binding")
            edge(id, norm)
            edge(previous, norm, dp="skip", kind="residual")
            previous = norm
        node(side + ".output", "stack_output", side, source=[cname + ".forward"])
        edge(previous, side + ".output", kind="repeat_output", repeated_over="N independent layers")
    edge("enc.output", "dec.cross", dp="memory", kind="memory", shape="[B,S,D]")
    node("generator", "linear", "model", source=["Transformer.__init__", "Transformer.forward"],
         param_identity="model.generator.weight", optional_alias="model.tgt_embedding.embedding.weight when tie flag is true")
    node("logits", "output", "model", source=["Transformer.forward"], shape="[B,T,V]")
    node("probabilities", "explanatory_softmax", "model", source=[], executed_in_forward=False)
    edge("dec.output", "generator")
    edge("generator", "logits")
    edge("logits", "probabilities", kind="explanatory", style="dashed")
    index = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["parent"]:
            index[n["parent"]]["children"].append(n["id"])
    # Explicit ports for child fan-in are a compact multi-edge interface.
    return dict(adapter="supplied educational pytorch_transformer_original; manual semantic adapter",
                source_sha256=evidence["sha256"], dimension_symbols=dict(B="batch", S="source length", T="target length", D="d_model", H="heads", Dh="D/H", V="target vocabulary"),
                conventions=dict(dropout="retained in IR, folded in views", nan_guard="retained in IR, folded in views",
                                 repeats="serial independent copies; representative layer i", shape_glyphs="symbolic, not true matrix dimensions",
                                 causal_mask="caller must supply tgt_mask; greedy_decode constructs it"), nodes=nodes, edges=edges)


class Scene:
    def __init__(self, width, height, view, ir):
        self.width, self.height, self.view, self.ir = width, height, view, ir
        self.semantic_index = {n["id"]: n for n in ir["nodes"]}
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                    '<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#263348"/></marker></defs>',
                    '<rect width="100%" height="100%" fill="white"/>']
        self.boxes, self.routes, self.ports, self.border_rects = [], [], {}, []
    def text(self, x, y, text, size=20, weight="normal", anchor="middle", color=None):
        lines = text.split("\n")
        color = color or COLORS["text"]
        self.svg.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">')
        for i, line in enumerate(lines):
            self.svg.append(f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.18}">{html.escape(line)}</tspan>')
        self.svg.append('</text>')
    def rect(self, x, y, w, h, fill, id=None, parent=None, radius=10, stroke=2, record=True):
        extra = f' data-node-id="{html.escape(id)}"' if id else ""
        node = self.semantic_index.get(id, {})
        tooltip = html.escape(" | ".join([id or "", "source: " + ", ".join(node.get("source_evidence", [])), "parameter: " + str(node.get("param_identity"))]))
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{COLORS.get(fill, fill)}" stroke="{COLORS["line"]}" stroke-width="{stroke}"{extra}><title>{tooltip}</title></rect>')
        # Include presentation-only frames in border routing checks as well.
        self.border_rects.append(dict(id=id or f"frame-{len(self.border_rects)+1:03d}",
                                      bbox=[x,y,w,h],radius=radius))
        if id and record:
            self.boxes.append(dict(id=id, parent=parent, bbox=[x, y, w, h]))
    def box(self, x, y, w, h, text, fill="control", size=20, **kw):
        self.rect(x, y, w, h, fill, **kw)
        n = len(text.split("\n"))
        self.text(x + w / 2, y + h / 2 - (n - 1) * size * .59 + size * .35, text, size)
    def line(self, points, dashed=False, arrow=True, width=2.2, id=None, src=None, dst=None):
        # Keep actual drawn paths in the layout, including local/anonymous edges.
        # Remove redundant vertices so the last segment means the true approach.
        clean = []
        for point in points:
            point = tuple(point)
            if clean and point == clean[-1]:
                continue
            if len(clean) >= 2:
                a, b = clean[-2:]
                u = (b[0]-a[0], b[1]-a[1])
                v = (point[0]-b[0], point[1]-b[1])
                if abs(u[0]*v[1]-u[1]*v[0]) < 1e-8 and u[0]*v[0]+u[1]*v[1] > 0:
                    clean.pop()
            clean.append(point)
        points = clean
        id = id or f"local-route-{len(self.routes)+1:03d}"
        d = "M " + " L ".join(f"{x},{y}" for x, y in points)
        self.svg.append(f'<path data-route-id="{html.escape(id)}" d="{d}" fill="none" stroke="{COLORS["line"]}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"' + (' stroke-dasharray="7 5"' if dashed else '') + (' marker-end="url(#arrow)"' if arrow else '') + '/>')
        self.routes.append(dict(id=id, points=points, src=src, dst=dst, dashed=dashed, arrow=arrow, width=width))
    def tensor(self, x, y, role, shape, color, width=62, shape_side=False):
        rows, cols, h = 3, 6, 30
        for r in range(rows):
            for c in range(cols):
                self.svg.append(f'<rect x="{x+c*width/cols}" y="{y+r*h/rows}" width="{width/cols}" height="{h/rows}" fill="{color}" stroke="#4d5d6b" stroke-width="0.65"/>')
        if role:
            self.text(x - 9, y + 20, role, 19, "bold", anchor="end")
        if shape_side:
            self.text(x+width+10,y+20,shape,14,anchor="start")
        else:
            self.text(x + width / 2, y + h + 20, shape, 16)
    def write(self, path):
        path.write_text("\n".join(self.svg + ["</svg>"]), encoding="utf-8")
    def layout(self):
        return dict(view=self.view, canvas=[self.width, self.height],
                    measurement="rule-based intrinsic heights and conservative text allowance; no pixel font measurement",
                    routing=dict(marker_units="userSpaceOnUse",arrow_length=ARROW_LENGTH,
                                 minimum_terminal=MIN_TERMINAL,inner_inset=ROUTE_INSET,
                                 computation_direction="bottom-to-top",
                                 downward_exceptions=["encoder-memory-to-cross"]),
                    boxes=self.boxes, border_rects=self.border_rects,
                    ports=self.ports, routes=self.routes)


def norm(scene, id, x, y, w, h, detailed, parent):
    scene.rect(x,y,w,h,"norm",id=id,parent=parent)
    cx=x+w/2
    if detailed:
        scene.text(x+22,y+27,"Add & Norm · Post-LN",20,"bold",anchor="start")
        plus_y=y+112
        scene.svg.append(f'<circle cx="{cx}" cy="{plus_y}" r="14" fill="white" stroke="{COLORS["line"]}" stroke-width="2" data-node-id="{id}.add"/>')
        scene.boxes.append(dict(id=id+".add",parent=id,bbox=[cx-14,plus_y-14,28,28]))
        scene.ports[id+".add"]={"x":(cx-14,plus_y),"f":(cx,plus_y+14),"out":(cx,plus_y-14)}
        scene.ports[id+".layernorm"]={"in":(cx,y+74),"out":(cx,y+42)}
        scene.text(cx,plus_y+7,"+",25,"bold")
        scene.text(x+48,plus_y-9,"x (skip)",16,anchor="start")
        scene.line([(x,plus_y),(cx-14,plus_y)])
        scene.line([(cx,y+h),(cx,plus_y+14)],id=id+"-branch-input",dst=id+".add:f")
        scene.box(cx-100,y+42,200,32,"LayerNorm","control",19,id=id+".layernorm",parent=id)
        scene.line([(cx,plus_y-14),(cx,y+74)],id=id+"-add-to-ln",src=id+".add:out",dst=id+".layernorm:in")
        scene.line([(cx,y+42),(cx,y)],id=id+"-output",src=id+".layernorm:out",dst=id+":out")
    else:
        scene.text(cx,y+h/2+7,"Add & Norm  (residual → LayerNorm)",19,"bold")
    return dict(in_=(cx,y+h),out=(cx,y),skip=(x,y+112 if detailed else y+h/2))


def attention(scene,id,x,y,w,h,view,parent,cross=False,causal=False):
    scene.rect(x,y,w,h,"attention",id=id,parent=parent)
    title=("Encoder–decoder\ncross-attention" if cross else
           "Decoder masked\nself-attention" if causal else "Encoder\nself-attention")
    scene.text(x+22,y+26,title,20,"bold",anchor="start")
    subtitle=("Q ← H [B,T,D]\nK,V ← M [B,S,D]" if cross else
              "Q,K,V ← X\n[B,T,D]" if causal else "Q,K,V ← X\n[B,S,D]")
    scene.text(x+w-22,y+26,subtitle,16,anchor="end")
    cx=x+w/2
    ports=dict(in_=(cx,y+h),out=(cx,y),memory=(x,y+72))
    if view=="overview":
        scene.text(cx,y+83,"causal + padding mask supplied by caller" if causal else "padding mask optional",16)
        return ports
    if view=="modules":
        labels=["Combine heads  →  output projection Wᴼ",
                "Scaled dot-product attention"+(" + causal mask" if causal else ""),
                "Q / K / V projections  →  split heads"]
        for i,text in enumerate(labels):
            scene.box(x+24,y+75+i*58,w-48,34,text,size=18)
        for start,end in ((y+h,y+225),(y+191,y+167),(y+133,y+109),(y+75,y)):
            scene.line([(cx,start),(cx,end)])
        if cross:
            ports["memory"]=(x,y+208)
            scene.line([ports["memory"],(x+24,y+208)],id=id+"-memory-to-projections",src=id+":memory")
        scene.text(x+w-22,y+h-9,"dropout folded",13,anchor="end")
        return ports

    # Every computational dependency is monotone upward. Parallel projections
    # keep separate columns. Cross uses K,V | Q so memory never crosses Q's input.
    inner_x,inner_w=x+42,w-84
    cw=(inner_w-36)/3
    centers=[inner_x+cw/2+j*(cw+18) for j in range(3)]
    order="KVQ" if cross else "QKV"
    role_x=dict(zip(order,centers))
    wo_y,merge_y,core_y=y+80,y+138,y+194
    core_h=42 if cross else 288
    split_y=core_y+core_h+24
    tensor_y=split_y+38+24
    projection_y=tensor_y+30+24
    bus_y=projection_y+34+24
    if cross:
        scene.rect(inner_x-6,projection_y-12,2*cw+30,62,"#fffaf6",record=False,radius=7,stroke=1.2)
        scene.rect(centers[2]-cw/2-6,projection_y-12,cw+12,62,"#fffaf6",record=False,radius=7,stroke=1.2)
        ports["memory"]=(x,bus_y)
        scene.line([ports["memory"],(role_x["V"],bus_y)],arrow=False)
        for role in "KV":
            scene.line([(role_x[role],bus_y),(role_x[role],projection_y+34)])
        q_bus=bus_y+10
        scene.line([ports["in_"],(cx,q_bus),(role_x["Q"],q_bus),
                    (role_x["Q"],projection_y+34)],id=id+"-query-input",dst=id+".q:in")
    else:
        scene.line([ports["in_"],(cx,bus_y)],arrow=False)
        scene.line([(centers[0],bus_y),(centers[2],bus_y)],arrow=False)
        for role in "QKV":
            scene.line([(role_x[role],bus_y),(role_x[role],projection_y+34)])
    for role in order:
        px=role_x[role]
        scene.box(px-56,projection_y,112,34,"Linear W"+role,"linear",16,
                  id=id+"."+role.lower(),parent=id)
        scene.ports[id+"."+role.lower()]={"in":(px,projection_y+34),"out":(px,projection_y)}
        shape="[B,T,D]" if causal or (cross and role=="Q") else "[B,S,D]"
        scene.tensor(px-25,tensor_y,role,shape,{"Q":"#a9d9f4","K":"#bce5b6","V":"#efb6d0"}[role],50,shape_side=True)
        scene.line([(px,projection_y),(px,tensor_y+30)],id=id+"-project-"+role.lower(),src=id+"."+role.lower()+":out")
        scene.line([(px,tensor_y),(px,split_y+38)],id=id+"-tensor-"+role.lower()+"-to-split",dst=id+".split:"+role.lower()+"_in")
    scene.box(inner_x,split_y,inner_w,38,"Split heads: Q / K / V → [B,H,L,Dh]","control",17,id=id+".split",parent=id)
    split_ports={role.lower()+"_in":(role_x[role],split_y+38) for role in order}
    if cross:
        split_ports.update({role.lower()+"_out":(role_x[role],split_y) for role in order})
        scene.box(inner_x,core_y,inner_w,core_h,"Scaled dot-product attention · per head","#f7eaf3",18,id=id+".sdpa",parent=id)
        scene.ports[id+".sdpa"]={**{role.lower():(role_x[role],core_y+core_h) for role in order},"out":(cx,core_y)}
        for role in order:
            scene.line([(role_x[role],split_y),(role_x[role],core_y+core_h)],
                       id=id+"-split-"+role.lower(),src=id+".split:"+role.lower()+"_out",dst=id+".sdpa:"+role.lower())
        scene.line([(cx,core_y),(cx,merge_y+32)],id=id+"-sdpa-to-merge",src=id+".sdpa:out",dst=id+".merge:in")
    else:
        scene.rect(inner_x,core_y,inner_w,core_h,"#fffaf6",id=id+".sdpa",parent=id)
        # The short header leaves the center output corridor free.
        scene.text(inner_x+14,core_y+24,"SDPA · per head",17,"bold",anchor="start")
        stages=[("av","A @ V","control"),("softmax","Softmax","softmax"),
                ("mask","causal + padding mask" if causal else "padding mask (optional)","control"),
                ("scale","÷ √Dh","control"),("qkt","Q @ Kᵀ","control")]
        stage_y={}
        for i,(name,label,fill) in enumerate(stages):
            yy=core_y+42+i*50
            stage_y[name]=yy
            scene.box(cx-100,yy,200,32,label,fill,16 if name=="mask" else 19,
                      id=id+".sdpa."+name,parent=id+".sdpa")
            scene.ports[id+".sdpa."+name]={"in":(cx,yy+32),"out":(cx,yy)}
        for lower,upper in (("qkt","scale"),("scale","mask"),("mask","softmax"),("softmax","av")):
            scene.line([(cx,stage_y[lower]),(cx,stage_y[upper]+32)],
                       id=id+"-"+lower+"-to-"+upper,src=id+".sdpa."+lower+":out",
                       dst=id+".sdpa."+upper+(":a" if upper=="av" else ":in"))
        operands={"q":cx-40,"k":cx+40,"v":role_x["V"]}
        split_ports.update({role+"_out":(px,split_y) for role,px in operands.items()})
        scene.ports[id+".sdpa.qkt"]={"q":(cx-40,stage_y["qkt"]+32),"k":(cx+40,stage_y["qkt"]+32),"out":(cx,stage_y["qkt"])}
        scene.ports[id+".sdpa.av"]={"a":(cx,stage_y["av"]+32),"v":(cx+100,stage_y["av"]+16),"out":(cx,stage_y["av"])}
        scene.ports[id+".sdpa"]={**{role:(px,core_y+core_h) for role,px in operands.items()},"out":(cx,core_y)}
        for role in "qk":
            px=operands[role]
            scene.line([(px,split_y),(px,stage_y["qkt"]+32)],
                       id=id+"-split-"+role,src=id+".split:"+role+"_out",dst=id+".sdpa.qkt:"+role)
            scene.text(px+(-7 if role=="q" else 7),split_y-8,role.upper()+"h",13,
                       anchor="end" if role=="q" else "start")
        vx=operands["v"]
        scene.line([(vx,split_y),(vx,stage_y["av"]+16),(cx+100,stage_y["av"]+16)],
                   id=id+"-split-v",src=id+".split:v_out",dst=id+".sdpa.av:v")
        scene.text(vx+8,split_y-8,"Vh",13,anchor="start")
        scene.text(inner_x+14,core_y+119,"A\n[B,H,Lq,Lk]",15,anchor="start")
        scene.text(inner_x+14,core_y+192,"mask before\nSoftmax",15,anchor="start")
        scene.line([(cx,stage_y["av"]),(cx,merge_y+32)],
                   id=id+"-av-to-merge",src=id+".sdpa.av:out",dst=id+".merge:in")
    scene.ports[id+".split"]=split_ports
    scene.box(inner_x,merge_y,inner_w,32,"Combine heads: [B,H,Lq,Dh] → [B,Lq,D]","control",17,id=id+".merge",parent=id)
    scene.ports[id+".merge"]={"in":(cx,merge_y+32),"out":(cx,merge_y)}
    scene.line([(cx,merge_y),(cx,wo_y+34)],id=id+"-merge-to-wo",src=id+".merge:out",dst=id+".wo:in")
    scene.box(cx-110,wo_y,220,34,"Linear Wᴼ (D → D)","linear",18,id=id+".wo",parent=id)
    scene.ports[id+".wo"]={"in":(cx,wo_y+34),"out":(cx,wo_y)}
    scene.line([(cx,wo_y),ports["out"]],id=id+"-output",src=id+".wo:out",dst=id+":out")
    return ports


def ffn(scene,id,x,y,w,h,view,parent):
    scene.rect(x,y,w,h,"ffn",id=id,parent=parent)
    cx=x+w/2
    ports=dict(in_=(cx,y+h),out=(cx,y))
    if view=="overview":
        scene.text(cx,y+28,"Position-wise feed-forward network",20,"bold")
        scene.text(cx,y+54,"same shared transform at each token",17)
        return ports
    scene.text(x+22,y+26,"Position-wise\nfeed-forward network",20,"bold",anchor="start")
    if view=="detailed":
        locations={"linear2":y+110,"relu":y+166,"linear1":y+222}
        scene.tensor(cx-25,y+56,"Z","[B,L,D]","#f2b5ce",50,shape_side=True)
        scene.tensor(cx-25,y+278,"X","[B,L,D]","#9ed5f2",50,shape_side=True)
        for name,label in (("linear2","Linear Dff → D"),("relu","ReLU"),("linear1","Linear D → Dff")):
            yy=locations[name]
            scene.box(cx-110,yy,220,32,label,"control" if name=="relu" else "linear",18,id=id+"."+name,parent=id)
            scene.ports[id+"."+name]={"in":(cx,yy+32),"out":(cx,yy)}
        scene.line([ports["in_"],(cx,y+308)],id=id+"-input")
        scene.line([(cx,y+278),(cx,y+254)],dst=id+".linear1:in")
        for lower,upper in (("linear1","relu"),("relu","linear2")):
            scene.line([(cx,locations[lower]),(cx,locations[upper]+32)],
                       id=id+"-"+lower+"-to-"+upper,src=id+"."+lower+":out",dst=id+"."+upper+":in")
        scene.line([(cx,y+110),(cx,y+86)],src=id+".linear2:out")
        scene.line([(cx,y+56),ports["out"]],id=id+"-output",dst=id+":out")
        scene.tensor(x+80,y+167,"","[B,L,Dff]","#b6e5b8",50)
        scene.text(x+105,y+154,"hidden",16,"bold")
        scene.line([(cx-110,y+182),(x+130,y+182)],dashed=True,arrow=False)
    else:
        names=["linear2","relu","linear1"]
        labels=["Linear Dff → D","ReLU","Linear D → Dff"]
        for i,(name,label) in enumerate(zip(names,labels)):
            yy=y+75+i*58
            scene.box(cx-130,yy,260,34,label,"control" if name=="relu" else "linear",18,id=id+"."+name,parent=id)
            scene.ports[id+"."+name]={"in":(cx,yy+34),"out":(cx,yy)}
        for start,end in ((y+h,y+225),(y+191,y+167),(y+133,y+109),(y+75,y)):
            scene.line([(cx,start),(cx,end)])
        scene.text(x+w-22,y+h-9,"dropout folded",13,anchor="end")
    return ports


def measure_stack(side,view,ir):
    # Intrinsic sizes depend on the amount of visible semantic detail.
    nh={"overview":50,"modules":56,"detailed":150}[view]
    fh={"overview":76,"modules":254,"detailed":332}[view]
    ah={"overview":102,"modules":254,"detailed":704}[view]
    # Semantic rank/hierarchy determine order; this view controls only visible detail.
    children=sorted([n for n in ir["nodes"] if n["parent"]==side+".layer_i" and n["kind"] in ("attention","ffn")],key=lambda n:n["rank"])
    ops=[(n["id"].split(".")[-1],fh if n["kind"]=="ffn" else
          468 if view=="detailed" and n["attention_role"]=="cross" else ah) for n in children]
    gap,padding=24,22
    height=sum(h+nh for _,h in ops)+gap*(len(ops)*2-1)+2*padding
    return dict(ops=ops,norm_h=nh,gap=gap,padding=padding,height=height)


def render(view,ir,out):
    width,stack_w=1600,660
    enc_x,dec_x,top=42,898,286
    measures={s:measure_stack(s,view,ir) for s in ("enc","dec")}
    maximum=max(m["height"] for m in measures.values())
    embed_y=top+maximum+88
    footer_y=embed_y+152
    height=footer_y+98
    s=Scene(width,height,view,ir)
    name={"overview":"1 · Architecture overview","modules":"2 · Module operations","detailed":"3 · Source-grounded detailed view"}[view]
    s.text(width/2,38,name,26,"bold")
    s.text(width/2,69,"Same semantic IR · Post-LayerNorm · independent layer parameters",19)
    s.text(width/2,94,"Solid: model forward · dashed: explanation · cross-attention SDPA is folded",17)
    # Generator and explanatory probability conversion above the decoder stack.
    center=dec_x+38+(stack_w-56)/2
    s.box(center-240,110,480,58,"Softmax → probabilities [B,T,V]\nExplanation only; outside Transformer.forward","softmax",17,id="probabilities",parent=None)
    s.box(center-190,188,380,48,"Generator Linear D → vocabulary V","linear",18,id="generator",parent=None)
    s.line([(center,188),(center,168)],dashed=True,id="logits-to-probabilities",src="logits",dst="probabilities")
    s.text(center+218,216,"logits",18,anchor="start")
    s.ports["generator"]={"in":(center,236),"out":(center,188)}
    s.ports["logits"]={"out":(center,188)}
    s.ports["probabilities"]={"in":(center,168)}
    positions={}
    for side,xx in (("enc",enc_x),("dec",dec_x)):
        m=measures[side]
        parent=side+".layer_i"
        stack_h=m["height"]
        s.rect(xx,top,stack_w,stack_h,"encoder" if side=="enc" else "decoder",id=parent,parent=None,radius=19,stroke=2.5)
        heading="Encoder × N_encoder" if side=="enc" else "Decoder × N_decoder"
        s.text(xx+20,top-20,heading,23,"bold",anchor="start")
        panel_x,panel_w=xx+38,stack_w-56
        yy=top+m["padding"]
        # Top-down placement reverses the forward operation order.
        ops=list(reversed(m["ops"]))
        for reverse_index,(op,op_h) in enumerate(ops):
            original_index=len(ops)-1-reverse_index
            nid=side+".norm"+str(original_index+1)
            np=norm(s,nid,panel_x,yy,panel_w,m["norm_h"],view=="detailed",parent)
            positions[nid]=np
            yy+=m["norm_h"]+m["gap"]
            oid=side+"."+op
            if op=="ffn":
                p=ffn(s,oid,panel_x,yy,panel_w,op_h,view,parent)
            else:
                p=attention(s,oid,panel_x,yy,panel_w,op_h,view,parent,cross=op=="cross",causal=side=="dec" and op=="self")
            positions[oid]=p
            s.line([p["out"],np["in_"]],id=oid+"-to-norm",src=oid,dst=nid)
            lane=xx+14
            # Branch below the panel, on the incoming tensor, not on its border.
            branch=(p["in_"][0],p["in_"][1]+m["gap"]/2)
            p["input_tap"]=branch
            s.line([branch,(lane,branch[1]),(lane,np["skip"][1]),np["skip"]],
                   id=oid+"-residual",src=oid+":input_tap",dst=nid+":skip")
            s.svg.append(f'<circle cx="{branch[0]}" cy="{branch[1]}" r="2.5" fill="{COLORS["line"]}"/>')
            if reverse_index>0:
                # The lower norm output is consumed by the previously placed upper sublayer.
                upper_op=ops[reverse_index-1][0]
                s.line([np["out"],positions[side+"."+upper_op]["in_"]],id=nid+"-to-next",src=nid,dst=side+"."+upper_op)
            yy+=op_h+m["gap"]
        topnorm=side+".norm"+str(len(ops))
        positions[side+".output"]={"out":positions[topnorm]["out"]}
        source_y=embed_y
        embed_id="src_embed" if side=="enc" else "tgt_embed"
        embed_text="Source token embedding × √D" if side=="enc" else "Target token embedding × √D"
        s.box(panel_x+55,source_y,panel_w-110,62,embed_text,"embedding",19,id=embed_id,parent=None)
        pe_y=source_y-42
        s.line([(center if side=="dec" else panel_x+panel_w/2,source_y), (panel_x+panel_w/2,pe_y+15)])
        cx=panel_x+panel_w/2
        s.svg.append(f'<circle cx="{cx}" cy="{pe_y}" r="15" fill="white" stroke="{COLORS["line"]}" stroke-width="2"/>')
        s.text(cx,pe_y+7,"+",25,"bold")
        pe_x=cx-190
        s.box(pe_x-112,pe_y-23,210,46,"Fixed sinusoidal PE","control",17,id="src_pe" if side=="enc" else "tgt_pe",parent=None)
        s.line([(pe_x+98,pe_y),(cx-15,pe_y)])
        s.line([(cx,pe_y-15),positions[side+".self"]["in_"]],id=side+"-input",src="src_pe" if side=="enc" else "tgt_pe",dst=side+".self")
        s.ports["src_pe" if side=="enc" else "tgt_pe"]={"out":(cx,pe_y-15)}
        s.text(cx,source_y+91,"src [B,S]" if side=="enc" else "tgt [B,T] · shifted-right by caller",19,"bold")
        s.line([(cx,source_y+81),(cx,source_y+62)])
        s.text(cx,source_y+118,"Embedding output [B,L,D] · PE dropout folded",17)
    # Memory leaves the encoder's FINAL top output, above its stack, never the input of MHA.
    start=positions["enc.output"]["out"]
    target=positions["dec.cross"]["memory"]
    lane=(enc_x+stack_w+dec_x)/2
    memory_points=[start,(start[0],top-67),(lane,top-67),(lane,target[1]),target]
    s.line(memory_points,id="encoder-memory-to-cross",src="enc.output:out",dst="dec.cross:memory",width=2.8)
    s.box(lane-80,top+32,160,104,"Memory M\n[B,S,D]\nfinal Encoder\noutput","control",16,record=False)
    dec_out=positions["dec.output"]["out"]
    s.line([dec_out,(center,236)],id="decoder-to-generator",src="dec.output:out",dst="generator:in")
    s.text(width/2,footer_y,"Tensor glyphs: Q blue · K green · V pink. Same type ≠ shared parameters. Module computation flow ↑.",17)
    s.text(width/2,footer_y+27,"Masks act before Softmax; causal mask is supplied by caller. ReLU · fixed sinusoidal PE · no generation loop shown.",17)
    s.text(width/2,footer_y+54,"Dropout / NaN guard are folded in the view and retained in semantic_ir.json. Matrix grids are symbolic.",17)
    base={"overview":"figure1_overview","modules":"figure2_modules","detailed":"figure3_detailed"}[view]
    s.write(out/(base+".svg"))
    s.ports.update({id:{("in" if name=="in_" else name):point for name,point in ports.items()} for id,ports in positions.items()})
    layout=s.layout()
    (out/("layout_"+view+".json")).write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding="utf-8")
    return layout


def checks(layout,ir):
    boxes=layout["boxes"]
    index={b["id"]:b for b in boxes}
    errors=[]
    for b in boxes:
        x,y,w,h=b["bbox"]
        if min(x,y)<0 or x+w>layout["canvas"][0] or y+h>layout["canvas"][1]:
            errors.append("outside canvas: "+b["id"])
        if b["parent"] in index:
            px,py,pw,ph=index[b["parent"]]["bbox"]
            if not(px<=x and py<=y and x+w<=px+pw and y+h<=py+ph):
                errors.append("containment: "+b["id"])
    siblings={}
    for b in boxes:
        if b["parent"] is not None:
            siblings.setdefault(b["parent"],[]).append(b)
    for group in siblings.values():
        for i,a in enumerate(group):
            ax,ay,aw,ah=a["bbox"]
            for b in group[i+1:]:
                bx,by,bw,bh=b["bbox"]
                if max(ax,bx)<min(ax+aw,bx+bw)-.01 and max(ay,by)<min(ay+ah,by+bh)-.01:
                    errors.append("sibling overlap: "+a["id"]+" / "+b["id"])
    semantic_index={n["id"]:n for n in ir["nodes"]}
    for e in ir["edges"]:
        for end in ("src","dst"):
            if e[end] not in semantic_index or e[end+"_port"] not in semantic_index[e[end]]["ports"]:
                errors.append("illegal semantic endpoint: "+e["id"])
    # These are the same normalized polylines emitted by Scene.line(), not a
    # second routing model. Normal perpendicular crossings at ports are allowed;
    # a parallel run on a frame's straight border is not.
    short_terminals, border_runs, endpoint_errors, downward_segments = [], [], [], []
    for route in layout["routes"]:
        points=route["points"]
        if route["id"] not in layout["routing"]["downward_exceptions"]:
            for a,b in zip(points,points[1:]):
                if b[1]>a[1]+1e-6:
                    downward_segments.append(route["id"])
                    errors.append("dependency segment goes downward: "+route["id"])
        if route["arrow"]:
            a,b=points[-2:]
            terminal=((b[0]-a[0])**2+(b[1]-a[1])**2)**.5
            if terminal < MIN_TERMINAL-1e-6:
                short_terminals.append(route["id"])
                errors.append(f"arrow terminal below {MIN_TERMINAL}px: {route['id']}")
        for endpoint,point in (("src",points[0]),("dst",points[-1])):
            ref=route.get(endpoint)
            if not ref:
                continue  # Local drawing edges need not claim a semantic port.
            name,sep,port=ref.partition(":")
            port={"input":"in","in_":"in"}.get(port,port) if sep else ("out" if endpoint=="src" else "in")
            expected=layout["ports"].get(name,{}).get(port)
            if expected is None or any(abs(a-b)>1e-6 for a,b in zip(point,expected)):
                endpoint_errors.append(route["id"]+":"+endpoint)
                errors.append("drawn endpoint missing or mismatched: "+route["id"]+" / "+ref)
        for a,b in zip(points,points[1:]):
            for frame in layout["border_rects"]:
                x,y,w,h=frame["bbox"]
                radius=min(frame["radius"],w/2,h/2)
                overlap=0
                if abs(a[1]-b[1])<1e-6 and (abs(a[1]-y)<1e-6 or abs(a[1]-y-h)<1e-6):
                    overlap=min(max(a[0],b[0]),x+w-radius)-max(min(a[0],b[0]),x+radius)
                elif abs(a[0]-b[0])<1e-6 and (abs(a[0]-x)<1e-6 or abs(a[0]-x-w)<1e-6):
                    overlap=min(max(a[1],b[1]),y+h-radius)-max(min(a[1],b[1]),y+radius)
                if overlap>1e-6:
                    border_runs.append(route["id"]+" / "+frame["id"])
                    errors.append("route runs along border: "+route["id"]+" / "+frame["id"])
    memory=next(r for r in layout["routes"] if r["id"]=="encoder-memory-to-cross")
    if (memory["src"],memory["dst"]) != ("enc.output:out","dec.cross:memory"):
        errors.append("incorrect memory endpoints")
    # An axis-aligned memory segment must not enter any operation panel's interior.
    for a,b in zip(memory["points"],memory["points"][1:]):
        for box in boxes:
            if box["parent"] not in ("enc.layer_i","dec.layer_i"):
                continue
            x,y,w,h=box["bbox"]
            if a[0]==b[0]:
                hit=x<a[0]<x+w and max(min(a[1],b[1]),y)<min(max(a[1],b[1]),y+h)
            else:
                hit=y<a[1]<y+h and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w)
            if hit:
                errors.append("memory crosses operation: "+box["id"])
    return dict(view=layout["view"],passed=not errors,errors=errors,box_count=len(boxes),
                route_count=len(layout["routes"]),
                routing_metrics=dict(short_terminals=len(short_terminals),border_collinear_runs=len(border_runs),
                                     endpoint_errors=len(endpoint_errors),downward_dependency_segments=len(downward_segments)),
                checks=["canvas bounds","child containment","sibling non-overlap","semantic edge src/dst ports",
                        "memory source and target","memory avoids operation interiors",
                        "arrow terminal at least 18px","no collinear runs on frame borders",
                        "drawn endpoints match registered view ports",
                        "all dependency segments run bottom-to-top; cross-lane memory transfer is exempt"],
                limitations=["text glyph extents require visual QA","all route/label collisions are not proven absent","manual adapter guards are not full semantic equivalence proof"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",default=str(HERE/"sources/pytorch_transformer_original/transformer.py"))
    parser.add_argument("--archive",help="Read transformer.py directly from supplied zip; no extraction or execution")
    parser.add_argument("--out",default=str(HERE/"generated"))
    args=parser.parse_args()
    source,origin=read_source(args)
    evidence=extract_evidence(source,origin)
    ir=make_ir(evidence)
    out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    for name,data in (("source_evidence",evidence),("semantic_ir",ir)):
        (out/(name+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    results=[]
    for view in ("overview","modules","detailed"):
        results.append(checks(render(view,ir,out),ir))
    (out/"layout_checks.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    sections="".join(f'<section><h2>{title}</h2><object data="{base}.svg" type="image/svg+xml"></object><p><a href="{base}.svg">SVG</a></p></section>' for title,base in [("Overview","figure1_overview"),("Modules","figure2_modules"),("Detailed","figure3_detailed")])
    (out/"index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Transformer: three views</title><style>body{font-family:system-ui;margin:24px;background:#edf0f5}section{background:white;padding:20px;margin-bottom:28px}object{width:100%;height:auto;min-height:800px}a{color:#2458b0}</style><h1>One source, three semantic views</h1><p>Hand-written semantic adapter; source AST only. See JSON evidence and layout checks.</p>'+sections+'</html>',encoding="utf-8")
    print(json.dumps(dict(output=str(out),views=results),ensure_ascii=False,indent=2))
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__=="__main__":
    main()
