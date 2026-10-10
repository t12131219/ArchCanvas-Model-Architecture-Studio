"""Activate a verified Skill copy and retain the replaced bytes for recovery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--archive', type=Path, required=True)
args = parser.parse_args()
project = Path(__file__).resolve().parents[3]

def verify(path):
    output = subprocess.check_output([sys.executable, str(project / 'scripts/m5_host_install.py'), 'verify', '--skill-directory', str(path)])
    result = json.loads(output)
    if result['status'] != 'passed':
        raise RuntimeError(result)
    return result

def inventory(path):
    return {str(item.relative_to(path)): ('link:' + os.readlink(item) if item.is_symlink() else hashlib.sha256(item.read_bytes()).hexdigest())
            for item in path.rglob('*') if item.is_file() or item.is_symlink()}

source = args.source.resolve(strict=True)
target = args.target.absolute()
archive = args.archive.absolute()
if target.is_symlink() or not target.is_dir() or target.parent.is_symlink() or archive.exists():
    raise ValueError('Target must be an existing real directory; archive must be new.')
verify(source)
archive.parent.mkdir(parents=True, exist_ok=True)
before = inventory(target)
stage = Path(tempfile.mkdtemp(prefix='.archcanvas-stage-', dir=target.parent))
replacement, previous = stage / 'replacement', stage / 'previous'
try:
    shutil.copytree(source, replacement, symlinks=True)
    verify(replacement)
    # Same-parent renames make activation reversible even across /tmp mounts.
    target.rename(previous)
    try:
        replacement.rename(target)
        receipt = verify(target)
    except BaseException:
        if target.exists():
            target.rename(replacement)
        previous.rename(target)
        raise
    shutil.move(str(previous), str(archive))
    if inventory(archive) != before:
        raise RuntimeError('Recovery archive does not match the replaced Skill.')
    print(json.dumps({'status': 'passed', 'target': str(target), 'archive': str(archive), 'archivedFileCount': len(before), 'verification': receipt}, indent=2))
finally:
    # Never remove populated recovery directories on failure.
    try:
        stage.rmdir()
    except OSError:
        pass
