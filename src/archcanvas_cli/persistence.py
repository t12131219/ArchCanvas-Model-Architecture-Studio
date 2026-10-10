"""Deduplicate immutable source facts in bounded canvas-history envelopes."""
from copy import deepcopy

ARCHITECTURE_REF = {"archcanvasSharedArchitecture": 1}


def _transform(value: dict, encode: bool) -> dict:
    result = deepcopy(value)
    if not isinstance(result, dict): return result
    document = result.get('document')
    architecture = document.get('architecture') if isinstance(document, dict) else None
    history = result.get('history')
    if not isinstance(architecture, dict) or architecture == ARCHITECTURE_REF or not isinstance(history, dict): return result
    def snapshot(item):
        if not isinstance(item, dict): return item
        matches = item.get('architecture') == (architecture if encode else ARCHITECTURE_REF)
        return {**item, 'architecture': dict(ARCHITECTURE_REF) if encode else deepcopy(architecture)} if matches else item
    # Replace snapshots, not aliased dictionaries: history.document can be the
    # very same Python object as the envelope's current document.
    result['history'] = {**history, 'document': snapshot(history.get('document')),
                         **{key:[snapshot(item) for item in history[key]] for key in ('past','future') if isinstance(history.get(key),list)}}
    return result


def encode_envelope(value: dict) -> dict:
    return _transform(value, True)


def decode_envelope(value: dict) -> dict:
    return _transform(value, False)
