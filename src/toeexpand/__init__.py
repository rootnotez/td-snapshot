"""Host-shell parser/encoder for toeexpand-produced `.dir/` + `.toc` trees.

Reads and writes the on-disk format documented in `toeexpand/FORMAT.md`,
independent of a running TouchDesigner process. Goal: bit-exact round-trip
(parse → emit → diff = 0 bytes). Where bit-exact is not achievable, the
deviation is recorded in `toeexpand/DEVIATIONS.md`.

Typical entry point:

    from toeexpand import Project
    p = Project.from_dir("path/to/foo.tox.dir")
    p.to_dir("path/to/copy.tox.dir")

Out of scope (lives in `src/core.py`, runs inside TouchDesigner):
    - Anything that needs `op()`, `me`, `parent()`, or `td` module access.
"""

from .build import Build
from .chop import Chop
from .cparm import Cparm
from .data import Data
from .fifo import Fifo
from .hold import Hold
from .joystick import Joystick
from .lod import Lod
from .logic import Logic
from .midiin import Midiin
from .mousein import Mousein
from .n import N
from .network import Network
from .panel import Panel
from .parm import Parm
from .project import Project
from .renderpick import Renderpick
from .script import Script
from .table import Table
from .text import Text
from .timestamp import Timestamp
from .toc import Toc
from .ts import Ts

__all__ = [
    "Build",
    "Chop",
    "Cparm",
    "Data",
    "Fifo",
    "Hold",
    "Joystick",
    "Lod",
    "Logic",
    "Midiin",
    "Mousein",
    "N",
    "Network",
    "Panel",
    "Parm",
    "Project",
    "Renderpick",
    "Script",
    "Table",
    "Text",
    "Timestamp",
    "Toc",
    "Ts",
]
