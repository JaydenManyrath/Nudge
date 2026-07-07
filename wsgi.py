"""
wsgi.py
Owner: shared (added to unblock Docker/Render deployment)

Standard WSGI entrypoint for gunicorn. app.py defines create_app() as a
factory (correct pattern -- keeps app creation testable and avoids
import-time side effects), but gunicorn's `app:app` / `wsgi:app` target
needs an actual module-level WSGI-callable object to import, not a
factory function. This file is that one, tiny bridge -- it should not
grow any real logic of its own.

Local dev still uses `python app.py` (or `flask run`), which hits the
`if __name__ == "__main__":` block in app.py directly. This file is
only for gunicorn/production.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
