"""
app/admin_ui.py
Hilfsfunktionen fuer die Vue-3-Admin-Oberflaeche.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def render_admin_index() -> str:
    index_path = _frontend_dist_dir() / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return _fallback_index_html()


def _frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _fallback_index_html() -> str:
    return """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KIDS_CONTROLLER Admin</title>
  <style>
    body {
      margin: 0;
      font-family: sans-serif;
      background: #f5f2eb;
      color: #18212b;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    main {
      max-width: 720px;
      background: white;
      border-radius: 20px;
      padding: 24px;
      border: 1px solid #d8ccb8;
      box-shadow: 0 18px 45px rgba(24, 33, 43, 0.08);
    }
    h1 { margin-top: 0; }
    code {
      display: inline-block;
      padding: 2px 6px;
      background: #f4efe5;
      border-radius: 6px;
    }
  </style>
</head>
<body>
  <main>
    <h1>Admin-UI wird gebaut</h1>
    <p>Die Vue-3-Oberflaeche ist noch nicht kompiliert. Bitte das Frontend bauen, damit die Admin-Oberflaeche geladen werden kann.</p>
    <p><code>cd frontend && npm install && npm run build</code></p>
  </main>
</body>
</html>
"""
