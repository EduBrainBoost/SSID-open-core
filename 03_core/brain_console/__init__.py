"""ssid-brain-console — Context assembly, memory management, and evidence logging.

Exports the 6 public classes consumed by SSID-EMS (PR #190):
  - BrainContextAssembler, BrainContext   (context.py)
  - MemoryManager, SessionMemory          (memory.py)
  - BrainEvidenceLogger, EvidenceEntry    (evidence.py)

stdlib-only — no external dependencies.
"""

from brain_console.context import BrainContext, BrainContextAssembler
from brain_console.memory import MemoryManager, SessionMemory
from brain_console.evidence import BrainEvidenceLogger, EvidenceEntry

__all__ = [
    "BrainContextAssembler",
    "BrainContext",
    "MemoryManager",
    "SessionMemory",
    "BrainEvidenceLogger",
    "EvidenceEntry",
]

__version__ = "0.1.0"
