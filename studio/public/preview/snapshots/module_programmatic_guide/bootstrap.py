"""Use the verified sibling prototype's static drawing/evidence engine."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
SHARED=HERE.parent/'model_zoo_programmatic_guide'
if not (SHARED/'layout.py').is_file():raise RuntimeError('Missing shared drawing prototype: '+str(SHARED))
if str(SHARED) not in sys.path:sys.path.insert(0,str(SHARED))
