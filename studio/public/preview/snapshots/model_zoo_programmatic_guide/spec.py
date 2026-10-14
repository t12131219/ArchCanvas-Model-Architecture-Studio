"""Small explicit model-adapter contract. No user model is imported or run."""
from __future__ import annotations


def ref(path, symbol):
    return path + "::" + symbol


def op(id, label, kind, source, shape="", detail=None, **kw):
    return dict(id=id, label=label, kind=kind, source=source if isinstance(source, list) else [source],
                shape=shape, detail=detail or [], **kw)


def chain(id, label, items, source, shape="", detail=None, expand=1, **kw):
    return dict(op(id, label, "group", source, shape, detail, **kw),
                mode="chain", items=items, expand=expand)


def parallel(id, label, items, source, shape="", detail=None, expand=1, **kw):
    """Explicit branches; operand_bundle adds typed projections, never implicit sum."""
    return dict(op(id, label, "group", source, shape, detail, **kw),
                mode="parallel", items=items, expand=expand)


def graph(id, label, items, source, shape="", detail=None, expand=1,
          ranks=None, rank_gap=72, column_gap=48, **kw):
    """Explicit DAG display scope; ranks go bottom to top and create no edges.

    Each immediate child appears in exactly one rank. Dependencies, including
    container boundaries, must be supplied as reviewed ``extra_edges``.
    """
    if ranks is None:
        raise ValueError("graph requires explicit bottom-to-top ranks")
    identifiers = [child["id"] for child in items]
    ordered = [identity for row in ranks for identity in row]
    if len(ordered) != len(set(ordered)) or set(ordered) != set(identifiers):
        raise ValueError("graph ranks must contain each immediate child exactly once")
    if rank_gap < 48 or column_gap < 48:
        raise ValueError("graph gaps must leave two 24px terminal corridors")
    align_x = kw.get("align_x", {})
    if any(a not in identifiers or b not in identifiers for a,b in align_x.items()):
        raise ValueError("graph align_x references must name immediate children")
    for start in align_x:
        seen=set();current=start
        while current in align_x:
            if current in seen:raise ValueError("cyclic graph align_x")
            seen.add(current);current=align_x[current]
    return dict(op(id, label, "group", source, shape, detail, **kw),
                mode="graph", items=items, expand=expand,
                ranks=ranks, rank_gap=rank_gap, column_gap=column_gap)
