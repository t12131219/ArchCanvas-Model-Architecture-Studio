#!/usr/bin/env python3
"""Summarize local M4 study records without counting automation as researchers.

Self-reported completion remains provisional until a reviewer has checked the
saved canvas, export and screenshots. No people are recruited or messaged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path


def timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Task timestamp must be ISO text.')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Task timestamps must include a timezone.')
    return parsed


def object_value(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f'{label}: expected an object.')
    return value


def finite_number(value: object, label: str) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{label}: expected a nonnegative finite number.')
    return value


def validate_task(receipt: dict, name: str) -> float:
    if receipt.get('outcome') not in ('completed', 'abandoned') or not receipt.get('finishedAt'):
        raise ValueError(f'{name}: unfinished record must be finalized before summarizing.')
    started, finished = timestamp(receipt.get('startedAt')), timestamp(receipt['finishedAt'])
    if started.utcoffset() != finished.utcoffset():
        raise ValueError(f'{name}: task timestamps must use a consistent timezone.')
    duration_ms = finite_number((finished - started).total_seconds() * 1000, f'{name}: task duration')
    checkpoints = receipt.get('checkpoints')
    if not isinstance(checkpoints, list) or len(checkpoints) > 5:
        raise ValueError(f'{name}: invalid checkpoints.')
    completed = receipt['outcome'] == 'completed'
    if completed and len(checkpoints) != 5:
        raise ValueError(f'{name}: completed record requires all five checkpoints.')
    previous_ms, previous_at, binding = 0, None, None
    for index, value in enumerate(checkpoints):
        checkpoint = object_value(value, f'{name}: checkpoint {index + 1}')
        observation = object_value(checkpoint.get('observation'), f'{name}: scene observation')
        if type(checkpoint.get('task')) is not int or checkpoint['task'] != index + 1 or checkpoint.get('selfReportedComplete') is not True:
            raise ValueError(f'{name}: checkpoints must record sequential self reports.')
        elapsed = finite_number(checkpoint.get('elapsedMs'), f'{name}: checkpoint time')
        if elapsed < previous_ms or elapsed > duration_ms + 2 or (completed and index > 0 and elapsed <= previous_ms):
            raise ValueError(f'{name}: invalid checkpoint time; completed checkpoints must strictly increase.')
        digests = (observation.get('sourceDigest'), observation.get('irDigest'))
        if any(not isinstance(value, str) or re.fullmatch(r'[0-9a-fA-F]{64}', value) is None for value in digests):
            raise ValueError(f'{name}: invalid source-bound scene digest.')
        current_binding = tuple(value.lower() for value in digests)
        if binding is not None and current_binding != binding:
            raise ValueError(f'{name}: source/IR binding changed during the task.')
        binding = current_binding
        visible = observation.get('visibleNodes')
        if type(visible) is not int or visible < 0:
            raise ValueError(f'{name}: visible node count must be a nonnegative integer.')
        revision = observation.get('visualRevision')
        if not isinstance(revision, str) or re.fullmatch(r'[0-9]+', revision) is None:
            raise ValueError(f'{name}: invalid visual revision.')
        observed_at = timestamp(observation.get('at'))
        if observed_at.utcoffset() != started.utcoffset():
            raise ValueError(f'{name}: task timestamps must use a consistent timezone.')
        if not started <= observed_at <= finished or (previous_at is not None and observed_at < previous_at):
            raise ValueError(f'{name}: scene observation time is outside the sequential task.')
        for field in ('expandedNodes', 'exportLinks'):
            entries = observation.get(field)
            if not isinstance(entries, list) or any(not isinstance(item, str) for item in entries):
                raise ValueError(f'{name}: {field} must contain text entries.')
        previous_ms, previous_at = elapsed, observed_at
    if not isinstance(receipt.get('notes', ''), str):
        raise ValueError(f'{name}: notes must be text.')
    if 'environment' in receipt:
        environment = object_value(receipt['environment'], f'{name}: environment')
        if 'viewport' in environment:
            object_value(environment['viewport'], f'{name}: viewport')
    return duration_ms


def summarize(paths: list[Path]) -> dict:
    participants, excluded, identities = [], [], set()
    for path in paths:
        raw = path.read_bytes()
        receipt = object_value(json.loads(raw), path.name)
        if type(receipt.get('schemaVersion')) is not int or receipt['schemaVersion'] != 1 or receipt.get('protocol') != 'archcanvas-m4-research-task/1':
            raise ValueError(f'{path.name}: unsupported study protocol.')
        code = receipt.get('participantCode')
        if not isinstance(code, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,40}', code.strip()) is None:
            raise ValueError(f'{path.name}: invalid participant code.')
        code = code.strip()
        if code in identities:
            raise ValueError(f'{path.name}: duplicate participant code.')
        identities.add(code)
        kind = receipt.get('participantKind')
        if kind not in ('researcher', 'automation'):
            raise ValueError(f'{path.name}: invalid participant type.')
        duration_ms = validate_task(receipt, path.name)
        if kind == 'automation':
            excluded.append({'participantCode': code, 'reason': 'automation-is-not-a-researcher', 'receipt': str(path.resolve())})
            continue
        completed = receipt['outcome'] == 'completed'
        participants.append({'participantCode': code, 'outcome': receipt['outcome'], 'durationMs': round(duration_ms),
            'selfReportedWithin3Minutes': completed and duration_ms <= 180_000, 'notes': receipt.get('notes', ''),
            'receipt': str(path.resolve()), 'receiptDigest': hashlib.sha256(raw).hexdigest()})
    successes = sum(item['selfReportedWithin3Minutes'] for item in participants)
    count = len(participants)
    return {'schemaVersion': 1, 'protocol': 'archcanvas-m4-research-task/1', 'researchGate': 'awaiting-independent-review' if count else 'not_run',
        'researcherCount': count, 'within3MinutesCount': successes, 'selfReportedCompletionRate': successes / count if count else None,
        'sampleSizeTargetMet': 3 <= count <= 5, 'selfReportedRateTargetMet': bool(count and successes / count >= .8),
        'participants': participants, 'excluded': excluded,
        'limitations': ['Self reports and timestamps alone do not establish successful figure editing/export.',
            'A reviewer must inspect saved canvas, exported figure and screenshot artifacts before certifying the researcher gate.',
            'Task duration is distinct from browser input-to-paint performance.']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts', type=Path, nargs='+')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        text = json.dumps(summarize(args.receipts), ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.write_text(text, encoding='utf-8')
        else:
            print(text, end='')
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
