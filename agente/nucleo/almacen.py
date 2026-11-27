"""Legacy module alias for the JSON store (preserves mutable path settings)."""
import sys
from infrastructure import json_store
sys.modules[__name__] = json_store
