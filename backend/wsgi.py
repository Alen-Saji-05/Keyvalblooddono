"""WSGI entry point.

``flask run`` and any production WSGI server both import ``app`` from here, so the two
paths construct the application identically.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
