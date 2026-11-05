"""Apply a .sql file to ClickHouse, one statement at a time.

ClickHouse's HTTP endpoint takes a single statement per request, and the
`multiquery` setting was removed in recent versions. clickhouse-client can do
it but is not installed in CI, whereas clickhouse-connect already is.

Usage:
    uv run python infra/clickhouse/apply_schema.py infra/clickhouse/init/01-tables.sql
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import clickhouse_connect


def statements(sql: str) -> list[str]:
    """Strip `--` line comments, then split on semicolons.

    Comments are removed FIRST. Splitting first and then discarding chunks that
    begin with `--` silently drops every statement that happens to be preceded
    by a comment, which here is most of them.

    Splitting on `;` is naive but correct for these files: they contain no
    semicolons inside string literals. If that changes this needs a real
    parser, and the failure will be loud rather than silent.
    """
    without_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in without_comments.split(";") if s.strip()]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: apply_schema.py <file.sql> [...]", file=sys.stderr)
        return 2

    client = clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
    )

    total = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        stmts = statements(path.read_text())
        for stmt in stmts:
            client.command(stmt)
        total += len(stmts)
        print(f"{path}: {len(stmts)} statements applied")
    print(f"done: {total} statements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
