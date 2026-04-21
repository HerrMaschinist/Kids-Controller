"""
app/admin_routes.py
Einfache Admin-Oberflaeche fuer Betrieb und manuelle Aktionen.
"""
from __future__ import annotations

from html import escape
from secrets import compare_digest
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.dependencies import get_admin_service
from app.admin_ui import render_admin_index
from config.settings import get_settings
from core.admin_service import AdminActionResult, AdminService
from core.models import Draw, FairnessWindow

security = HTTPBasic()

router = APIRouter(prefix="/admin", tags=["admin"])
api_router = APIRouter(prefix="/admin/api/v1", tags=["admin-api"])


def require_admin_auth(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    settings = get_settings()
    if not settings.admin_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin UI deaktiviert")
    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin-Zugangsdaten sind nicht konfiguriert",
        )
    username_ok = compare_digest(credentials.username, settings.admin_username)
    password_ok = compare_digest(credentials.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungueltige Zugangsdaten",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> HTMLResponse:
    return HTMLResponse(render_admin_index())


@router.get("/draws", response_class=HTMLResponse)
async def admin_draws(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> HTMLResponse:
    return HTMLResponse(render_admin_index())


@router.get("/windows", response_class=HTMLResponse)
async def admin_windows(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> HTMLResponse:
    return HTMLResponse(render_admin_index())


@router.get("/config", response_class=HTMLResponse)
async def admin_config(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> HTMLResponse:
    return HTMLResponse(render_admin_index())


@router.post("/actions/draw")
async def admin_action_draw(
    request: Request,
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> RedirectResponse:
    form = await request.form()
    result, _draw = await admin_service.trigger_draw(
        leon_present=_checkbox_value(form.get("leon_present")),
        emmi_present=_checkbox_value(form.get("emmi_present")),
        elsa_present=_checkbox_value(form.get("elsa_present")),
    )
    return _redirect_with_message("/", result)


@router.post("/actions/router-probe")
async def admin_action_router_probe(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> RedirectResponse:
    result, _probe = await admin_service.probe_router()
    return _redirect_with_message("/", result)


@router.post("/actions/backup")
async def admin_action_backup(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> RedirectResponse:
    result = await admin_service.create_backup()
    return _redirect_with_message("/", result)


@api_router.get("/overview")
async def admin_api_overview(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    overview = await admin_service.overview()
    status = overview["status"]
    recent_draws = overview["recent_draws"]
    recent_windows = overview["recent_windows"]
    payload = {
        "status": status.model_dump(mode="json"),
        "recent_draws": [_draw_payload(draw) for draw in recent_draws],
        "recent_windows": [_window_payload(window) for window in recent_windows],
        "config": overview["config"],
    }
    return JSONResponse(payload)


@api_router.post("/actions/draw")
async def admin_api_action_draw(
    request: Request,
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    body = await request.json()
    result, draw = await admin_service.trigger_draw(
        leon_present=bool(body.get("leon_present")),
        emmi_present=bool(body.get("emmi_present")),
        elsa_present=bool(body.get("elsa_present")),
    )
    return JSONResponse({"result": result.__dict__, "draw": _draw_payload(draw)})


@api_router.post("/actions/router-probe")
async def admin_api_action_router_probe(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    result, probe = await admin_service.probe_router()
    return JSONResponse({"result": result.__dict__, "probe": probe.model_dump(mode="json")})


@api_router.post("/actions/backup")
async def admin_api_action_backup(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    result = await admin_service.create_backup()
    return JSONResponse({"result": result.__dict__})


@api_router.get("/draws")
async def admin_api_draws(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    draws = await admin_service.recent_draws(limit=50)
    return JSONResponse({"draws": [_draw_payload(draw) for draw in draws]})


@api_router.get("/windows")
async def admin_api_windows(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    windows = await admin_service.recent_windows(limit=50)
    return JSONResponse({"windows": [_window_payload(window) for window in windows]})


@api_router.get("/config")
async def admin_api_config(
    _: str = Depends(require_admin_auth),
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    return JSONResponse({"config": admin_service.config_snapshot()})


def _redirect_with_message(target: str, result: AdminActionResult) -> RedirectResponse:
    query = urlencode(
        {
            "message": f"{result.title}: {result.detail}",
            "kind": "success" if result.ok else "error",
        }
    )
    return RedirectResponse(
        url=f"/admin{target}?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _checkbox_value(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "on", "yes"}


def _draw_payload(draw: Draw) -> dict[str, Any]:
    return {
        "id": draw.id,
        "draw_date": draw.draw_date.isoformat(),
        "draw_ts": draw.draw_ts.isoformat(),
        "mode": draw.mode.value,
        "window_id": draw.window_id,
        "window_index": draw.window_index,
        "pair_key": draw.pair_key.value if draw.pair_key else None,
        "pair_cycle_index": draw.pair_cycle_index,
        "pos1": draw.pos1,
        "pos2": draw.pos2,
        "pos3": draw.pos3,
        "stop_morning": draw.stop_morning,
        "stop_midday": draw.stop_midday,
        "is_effective": draw.is_effective,
    }


def _window_payload(window: FairnessWindow) -> dict[str, Any]:
    return {
        "id": window.id,
        "window_id": window.window_id,
        "window_start_date": window.window_start_date.isoformat(),
        "window_status": window.window_status.value,
        "window_index": window.window_index,
        "window_size": window.window_size,
        "last_full_order": window.last_full_order.value if window.last_full_order else None,
        "last_full_draw_date": (
            window.last_full_draw_date.isoformat() if window.last_full_draw_date else None
        ),
        "last_mode": window.last_mode.value if window.last_mode else None,
        "created_at": window.created_at.isoformat(),
        "updated_at": window.updated_at.isoformat(),
    }


def _render_page(*, title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KIDS_CONTROLLER Admin - {escape(title)}</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --card: #fffdfa;
      --line: #d9cfbf;
      --ink: #1f2933;
      --muted: #5d6b78;
      --accent: #1d6f5f;
      --warn: #9b5c00;
      --error: #a33636;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(29,111,95,0.08), transparent 30%),
        linear-gradient(180deg, #f6f3ed, var(--bg));
    }}
    header {{
      padding: 24px 20px 12px;
      border-bottom: 1px solid var(--line);
    }}
    header h1 {{
      margin: 0;
      font-size: 1.8rem;
      letter-spacing: 0.02em;
    }}
    header p {{
      margin: 6px 0 0;
      color: var(--muted);
    }}
    nav {{
      display: flex;
      gap: 12px;
      padding: 12px 20px 0;
      flex-wrap: wrap;
    }}
    nav a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }}
    main {{
      padding: 20px;
      display: grid;
      gap: 16px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 25px rgba(31,41,51,0.05);
    }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    h2, h3 {{ margin-top: 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.06em; }}
    .pill {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(29,111,95,0.10);
      color: var(--accent);
      font-weight: 700;
      font-size: 0.84rem;
    }}
    .pill.warn {{ background: rgba(155,92,0,0.12); color: var(--warn); }}
    .pill.error {{ background: rgba(163,54,54,0.12); color: var(--error); }}
    .flash {{
      padding: 12px 14px;
      border-radius: 12px;
      margin-bottom: 12px;
      font-weight: 700;
    }}
    .flash.success {{ background: rgba(29,111,95,0.10); color: var(--accent); }}
    .flash.error {{ background: rgba(163,54,54,0.12); color: var(--error); }}
    form.inline {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    label.check {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      font-weight: 700;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>KIDS_CONTROLLER Admin</h1>
    <p>Betrieb, Fairnesszustand und manuelle Aktionen ohne Terminal.</p>
  </header>
  <nav>
    <a href="/admin">Dashboard</a>
    <a href="/admin/draws">Draws</a>
    <a href="/admin/windows">Fenster</a>
    <a href="/admin/config">Konfiguration</a>
  </nav>
  <main>
    {content}
  </main>
</body>
</html>"""


def _render_dashboard(
    overview: dict[str, object],
    message: str | None,
    message_kind: str,
) -> str:
    status = overview["status"]
    recent_draws = overview["recent_draws"]
    recent_windows = overview["recent_windows"]
    config = overview["config"]
    flash = ""
    if message:
        kind = "error" if message_kind == "error" else "success"
        flash = f'<div class="flash {kind}">{escape(message)}</div>'
    return f"""
    {flash}
    <section class="grid">
      <div class="card">
        <h2>Betriebsstatus</h2>
        <p><span class="pill">{escape(status.status)}</span></p>
        <p><strong>Letzter erfolgreicher Draw:</strong> {escape(str(status.last_successful_draw_id))}</p>
        <p><strong>Datum:</strong> {escape(str(status.last_successful_draw_date))}</p>
        <p><strong>Modus:</strong> {escape(str(status.last_successful_draw_mode))}</p>
        <p><strong>Letzter Lauf:</strong> {escape(str(status.last_run_at))}</p>
        <p><strong>Letzter Fehler:</strong> {escape(str(status.last_error_message or '-'))}</p>
      </div>
      <div class="card">
        <h2>Router</h2>
        <p><strong>Aktiviert:</strong> {escape(str(status.router.enabled))}</p>
        <p><strong>Verfuegbar:</strong> {escape(str(status.router.available))}</p>
        <p><strong>Letzte Probe:</strong> {escape(str(status.router.last_checked_at))}</p>
        <p><strong>Bewertung:</strong> {escape(str(status.router.last_assessment_status or '-'))}</p>
        <p class="meta">{escape(str(status.router.last_probe_message or status.router.last_assessment_message or '-'))}</p>
      </div>
      <div class="card">
        <h2>Invarianten</h2>
        <p><strong>Genau ein aktives Fenster:</strong> {escape(str(status.invariants.exactly_one_active_window))}</p>
        <p><strong>Aktives Fenster vorhanden:</strong> {escape(str(status.invariants.active_window_present))}</p>
        <p><strong>Letzter effektiver Draw vorhanden:</strong> {escape(str(status.invariants.latest_effective_draw_present))}</p>
        <p><strong>Fehler im Speicherstatus:</strong> {escape(str(status.invariants.last_error_present))}</p>
      </div>
    </section>
    <section class="grid">
      <div class="card">
        <h2>Manuelle Aktionen</h2>
        <h3>Draw ausloesen</h3>
        <form class="inline" method="post" action="/admin/actions/draw">
          <label class="check"><input type="checkbox" name="leon_present"> Leon</label>
          <label class="check"><input type="checkbox" name="emmi_present"> Emmi</label>
          <label class="check"><input type="checkbox" name="elsa_present"> Elsa</label>
          <button type="submit">Draw starten</button>
        </form>
        <h3>Router pruefen</h3>
        <form method="post" action="/admin/actions/router-probe">
          <button type="submit">Router-Probe starten</button>
        </form>
        <h3>Backup</h3>
        <form method="post" action="/admin/actions/backup">
          <button type="submit">App-Backup erstellen</button>
        </form>
      </div>
      <div class="card">
        <h2>Sichtbare Konfiguration</h2>
        {_render_config_table(config)}
      </div>
    </section>
    <section class="grid">
      <div class="card">
        <h2>Letzte Draws</h2>
        {_render_draws_table(recent_draws[:10])}
      </div>
      <div class="card">
        <h2>Letzte Fenster</h2>
        {_render_windows_table(recent_windows[:10])}
      </div>
    </section>
    """


def _render_draws(draws: list[Draw]) -> str:
    return f'<section class="card"><h2>Letzte Draws</h2>{_render_draws_table(draws)}</section>'


def _render_windows(windows: list[FairnessWindow]) -> str:
    return f'<section class="card"><h2>Letzte Fenster</h2>{_render_windows_table(windows)}</section>'


def _render_config(config: list[dict[str, object]]) -> str:
    return f'<section class="card"><h2>Konfiguration</h2>{_render_config_table(config)}</section>'


def _render_draws_table(draws: list[Draw]) -> str:
    rows = "".join(
        f"""
        <tr>
          <td>{draw.id}</td>
          <td>{escape(draw.draw_date.isoformat())}</td>
          <td><span class="pill">{escape(draw.mode.value)}</span></td>
          <td>{escape(str(draw.window_id or '-'))}</td>
          <td>{escape(_positions(draw))}</td>
          <td>{escape(str(draw.stop_morning))} / {escape(str(draw.stop_midday))}</td>
          <td>{escape(str(draw.is_effective))}</td>
        </tr>
        """
        for draw in draws
    )
    return (
        "<table><thead><tr><th>ID</th><th>Datum</th><th>Modus</th><th>Fenster</th>"
        "<th>Positionen</th><th>Stops</th><th>Effektiv</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=\"7\">Keine Draws vorhanden.</td></tr>'}</tbody></table>"
    )


def _render_windows_table(windows: list[FairnessWindow]) -> str:
    rows = "".join(
        f"""
        <tr>
          <td>{window.id}</td>
          <td>{escape(window.window_id)}</td>
          <td><span class="pill{' warn' if window.window_status.value != 'ACTIVE' else ''}">{escape(window.window_status.value)}</span></td>
          <td>{window.window_index}</td>
          <td>{escape(str(window.last_full_order.value if window.last_full_order else '-'))}</td>
          <td>{escape(str(window.last_mode.value if window.last_mode else '-'))}</td>
          <td>{escape(window.window_start_date.isoformat())}</td>
        </tr>
        """
        for window in windows
    )
    return (
        "<table><thead><tr><th>ID</th><th>Window ID</th><th>Status</th><th>Index</th>"
        "<th>Letzte Vollordnung</th><th>Letzter Modus</th><th>Start</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=\"7\">Keine Fenster vorhanden.</td></tr>'}</tbody></table>"
    )


def _render_config_table(config: list[dict[str, object]]) -> str:
    rows = "".join(
        f"""
        <tr>
          <td>{escape(str(item['key']))}</td>
          <td>{escape(str(item['value']))}</td>
          <td>{'nein' if not item['editable'] else 'ja'}</td>
        </tr>
        """
        for item in config
    )
    return (
        "<table><thead><tr><th>Schluessel</th><th>Wert</th><th>Editierbar</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _positions(draw: Draw) -> str:
    return " / ".join(str(value) for value in (draw.pos1, draw.pos2, draw.pos3) if value is not None) or "-"
