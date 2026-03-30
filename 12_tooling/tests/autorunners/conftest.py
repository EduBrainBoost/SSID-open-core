import sys
from pathlib import Path
# 12_tooling/tests/autorunners/conftest.py → parent.parent.parent = 12_tooling
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
