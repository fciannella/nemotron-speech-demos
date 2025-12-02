"""Compatibility shim.

Some environments may still reference `./rbc-fees-agent/fees_agent.py:agent`.
This file re-exports the ReAct agent defined in `react_agent.py`.
"""

try:
    from .react_agent import agent  # noqa: F401
except ImportError:
    import os as _os
    import sys as _sys
    _sys.path.append(_os.path.dirname(__file__))
    from react_agent import agent  # type: ignore  # noqa: F401


