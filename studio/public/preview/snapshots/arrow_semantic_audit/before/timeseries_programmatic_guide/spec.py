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
    """A tuple/list fork-join, not an implicit sum or parameter sharing."""
    return dict(op(id, label, "group", source, shape, detail, **kw),
                mode="parallel", items=items, expand=expand)
