"""
persistence/repositories.py
Repository-Implementierungen für fairness_windows und draws.
Verwendet direkte psycopg v3 AsyncConnection ohne Pool.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from uuid import UUID
from datetime import date

import psycopg
from psycopg.rows import dict_row

from core.models import Draw, FairnessWindow, PairKey
from persistence.mappers import (
    draw_to_insert_params,
    record_to_draw,
    record_to_fairness_window,
    window_to_insert_params,
    window_to_update_params,
)


class WindowRepository:
    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """
        Liefert eine direkte AsyncConnection mit aktiver Transaktion.
        """
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.transaction():
                yield conn
        finally:
            await conn.close()

    async def find_active_with_lock(
        self, conn: psycopg.AsyncConnection
    ) -> Optional[FairnessWindow]:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT *
                FROM fairness_windows
                WHERE window_status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
                """
            )
            row = await cur.fetchone()
        return record_to_fairness_window(row) if row else None

    async def find_active(self) -> Optional[FairnessWindow]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM fairness_windows
                    WHERE window_status = 'ACTIVE'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
            return record_to_fairness_window(row) if row else None
        finally:
            await conn.close()

    async def count_active_windows(self) -> int:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM fairness_windows
                    WHERE window_status = 'ACTIVE'
                    """
                )
                row = await cur.fetchone()
            return int(row["count"]) if row else 0
        finally:
            await conn.close()

    async def list_recent(self, limit: int = 20) -> list[FairnessWindow]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM fairness_windows
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cur.fetchall()
            return [record_to_fairness_window(row) for row in rows]
        finally:
            await conn.close()

    async def insert(
        self, window: FairnessWindow, conn: psycopg.AsyncConnection
    ) -> FairnessWindow:
        p = window_to_insert_params(window)
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO fairness_windows (
                    window_id, window_start_date, window_status, window_index,
                    window_size, permutation_sequence, last_full_order,
                    last_full_draw_date, last_mode, seed_material_hash,
                    shuffle_algorithm, algorithm_version,
                    created_at, updated_at
                ) VALUES (
                    %(window_id)s,
                    %(window_start_date)s,
                    %(window_status)s::window_status_enum,
                    %(window_index)s,
                    %(window_size)s,
                    %(permutation_sequence)s::jsonb,
                    %(last_full_order)s::perm_code_enum,
                    %(last_full_draw_date)s,
                    %(last_mode)s::mode_enum,
                    %(seed_material_hash)s,
                    %(shuffle_algorithm)s,
                    %(algorithm_version)s,
                    NOW(), NOW()
                )
                RETURNING *
                """,
                p,
            )
            row = await cur.fetchone()
        return record_to_fairness_window(row)

    async def update(
        self, window: FairnessWindow, conn: psycopg.AsyncConnection
    ) -> FairnessWindow:
        p = window_to_update_params(window)
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE fairness_windows
                SET window_status        = %(window_status)s::window_status_enum,
                    window_index         = %(window_index)s,
                    last_full_order      = %(last_full_order)s::perm_code_enum,
                    last_full_draw_date  = %(last_full_draw_date)s,
                    last_mode            = %(last_mode)s::mode_enum,
                    updated_at           = %(updated_at)s
                WHERE id = %(id)s
                RETURNING *
                """,
                p,
            )
            row = await cur.fetchone()
        return record_to_fairness_window(row)


class DrawRepository:
    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    async def find_by_request_id(
        self, request_id: UUID
    ) -> Optional[Draw]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM draws WHERE request_id = %s::uuid",
                    (str(request_id),),
                )
                row = await cur.fetchone()
            return record_to_draw(row) if row else None
        finally:
            await conn.close()

    async def find_latest_effective_draw(self) -> Optional[Draw]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM draws
                    WHERE is_effective = TRUE
                    ORDER BY draw_ts DESC, id DESC
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
            return record_to_draw(row) if row else None
        finally:
            await conn.close()

    async def list_recent(self, limit: int = 20) -> list[Draw]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM draws
                    ORDER BY draw_ts DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cur.fetchall()
            return [record_to_draw(row) for row in rows]
        finally:
            await conn.close()

    async def insert(
        self, draw: Draw, conn: psycopg.AsyncConnection
    ) -> Draw:
        p = draw_to_insert_params(draw)
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO draws (
                    draw_ts, draw_date, request_id, window_id, mode,
                    present_mask, window_index, active_window_index_snapshot,
                    perm_code, derived_from_last_full_order, is_effective,
                    superseded_by_draw_id, pair_key, pair_cycle_index,
                    pos1, pos2, pos3, stop_morning, stop_midday,
                    algorithm_version, seed_material_hash, replay_context_hash, note
                ) VALUES (
                    %(draw_ts)s,
                    %(draw_date)s,
                    %(request_id)s::uuid,
                    %(window_id)s,
                    %(mode)s::mode_enum,
                    %(present_mask)s,
                    %(window_index)s,
                    %(active_window_index_snapshot)s,
                    %(perm_code)s::perm_code_enum,
                    %(derived_from_last_full_order)s,
                    %(is_effective)s,
                    %(superseded_by_draw_id)s,
                    %(pair_key)s::pair_key_enum,
                    %(pair_cycle_index)s,
                    %(pos1)s,
                    %(pos2)s,
                    %(pos3)s,
                    %(stop_morning)s,
                    %(stop_midday)s,
                    %(algorithm_version)s,
                    %(seed_material_hash)s,
                    %(replay_context_hash)s,
                    %(note)s
                )
                RETURNING *
                """,
                p,
            )
            row = await cur.fetchone()
        return record_to_draw(row)

    async def find_last_pair_for_key(
        self, pair_key: PairKey, conn: psycopg.AsyncConnection
    ) -> Optional[Draw]:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT *
                FROM draws
                WHERE mode = 'PAIR'
                  AND pair_key = %s::pair_key_enum
                  AND is_effective = TRUE
                ORDER BY draw_ts DESC
                LIMIT 1
                """,
                (pair_key.value,),
            )
            row = await cur.fetchone()
        return record_to_draw(row) if row else None

    async def find_effective_by_date(
        self, draw_date: date
    ) -> Optional[Draw]:
        conn = await psycopg.AsyncConnection.connect(
            self._conninfo,
            row_factory=dict_row,
        )
        try:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM draws
                    WHERE draw_date = %s::date
                      AND is_effective = TRUE
                    ORDER BY draw_ts DESC, id DESC
                    LIMIT 1
                    """,
                    (draw_date,),
                )
                row = await cur.fetchone()
            return record_to_draw(row) if row else None
        finally:
            await conn.close()
