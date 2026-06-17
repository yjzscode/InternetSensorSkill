"""Test package bootstrap.

The retrieval modules are standalone scripts (not an installed package), so we put
the `retrieval/` directory on sys.path here. Then tests can `import _common`,
`import engagement`, `import tavily`, `import retrieve`, etc. as top-level modules,
exactly as retrieve.py does when run as a script.
"""

import os
import sys

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)
