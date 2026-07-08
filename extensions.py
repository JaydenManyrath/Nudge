"""Shared extension singletons.

Defining ``socketio`` here (rather than in app.py) guarantees exactly one
SocketIO instance regardless of how the process is started. When the app is
launched with ``python app.py``, app.py runs as ``__main__``; any later
``from app import socketio`` re-imports app.py a second time as module ``app``
and would create a *distinct* SocketIO instance whose ``.server`` is never
initialized — making every emit-bearing route crash. Importing the singleton
from this neutral module avoids that dual-import trap.
"""

from flask_socketio import SocketIO

socketio = SocketIO()
