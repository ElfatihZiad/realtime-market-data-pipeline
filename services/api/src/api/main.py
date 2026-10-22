"""FastAPI app: REST for history, WebSocket for live push.

The old dashboard was a Bokeh server polling Cassandra every 600ms from the
browser. Here the server pushes.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mdp_core import configure_logging, get_settings

from api import store

log = structlog.get_logger("api")
STATIC_DIR = Path(__file__).parent / "static"


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    log.info("api_started")
    yield


app = FastAPI(title="Market Data Pipeline", version="0.2.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        client = store.get_client()
        client.query("SELECT 1")
        return {"status": "ok", "clickhouse": "reachable"}
    except Exception as exc:  # noqa: BLE001 - health must report, not raise
        return {"status": "degraded", "clickhouse": str(exc)}


@app.get("/api/instruments")
def get_instruments() -> list[str]:
    return store.instruments(store.get_client())


@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return store.pipeline_stats(store.get_client())


@app.get("/api/bars")
def get_bars(
    instrument_id: str = Query(min_length=1, max_length=32),
    minutes: int = Query(default=120, ge=1, le=10_080),
) -> list[dict[str, Any]]:
    bars = store.bars_1m(store.get_client(), instrument_id, minutes)
    if not bars:
        raise HTTPException(
            404,
            f"no closed bars for {instrument_id} in the last {minutes}m — "
            "is the Flink job running? (just stream)",
        )
    return bars


@app.get("/api/signals")
def get_signals(
    instrument_id: str = Query(min_length=1, max_length=32),
    minutes: int = Query(default=240, ge=1, le=10_080),
) -> list[dict[str, Any]]:
    return store.signals(store.get_client(), instrument_id, minutes)


@app.get("/api/ticks")
def get_ticks(
    instrument_id: str = Query(min_length=1, max_length=32),
    limit: int = Query(default=200, ge=1, le=5_000),
) -> list[dict[str, Any]]:
    return store.recent_ticks(store.get_client(), instrument_id, None, limit)


@app.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket, instrument_id: str = "BTC-USD") -> None:
    """Push new trades as they land.

    Phase 1 tails ClickHouse once a second. Phase 2 subscribes to the
    Flink-produced bars topic directly, which removes this poll.
    """
    await websocket.accept()
    client = store.get_client()
    cursor: str | None = None
    try:
        seed = store.recent_ticks(client, instrument_id, None, 200)
        if seed:
            cursor = seed[-1]["event_time"]
            await websocket.send_json({"type": "snapshot", "ticks": seed})

        while True:
            await asyncio.sleep(1.0)
            fresh = store.recent_ticks(client, instrument_id, cursor, 500)
            if fresh:
                cursor = fresh[-1]["event_time"]
                await websocket.send_json({"type": "ticks", "ticks": fresh})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("ws_closed", error=str(exc))
        with contextlib.suppress(Exception):
            await websocket.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
