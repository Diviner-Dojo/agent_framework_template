"""SQLite database layer for the Todo API."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "todo.db"


class TodoDatabase:
    """Simple SQLite-based storage for todo items."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open database connection and create table if needed."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT,
                completed   BOOLEAN NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    def create_todo(self, title: str, description: str | None = None) -> dict:
        """Create a new todo and return it."""
        now = datetime.now(UTC).isoformat()
        cursor = self.conn.execute(
            "INSERT INTO todos (title, description, completed, created_at) VALUES (?, ?, 0, ?)",
            (title, description, now),
        )
        self.conn.commit()
        return self.get_todo(cursor.lastrowid)

    def get_todo(self, todo_id: int) -> dict | None:
        """Get a single todo by ID."""
        row = self.conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_todos(self, completed: bool | None = None) -> list[dict]:
        """List all todos, optionally filtered by completion status."""
        if completed is not None:
            rows = self.conn.execute(
                "SELECT * FROM todos WHERE completed = ? ORDER BY id",
                (int(completed),),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def update_todo(
        self,
        todo_id: int,
        title: str | None = None,
        description: str | None = None,
        completed: bool | None = None,
    ) -> dict | None:
        """Update a todo. Only provided fields are changed."""
        existing = self.get_todo(todo_id)
        if existing is None:
            return None

        new_title = title if title is not None else existing["title"]
        new_desc = description if description is not None else existing["description"]
        new_completed = completed if completed is not None else existing["completed"]

        self.conn.execute(
            "UPDATE todos SET title = ?, description = ?, completed = ? WHERE id = ?",
            (new_title, new_desc, int(new_completed), todo_id),
        )
        self.conn.commit()
        return self.get_todo(todo_id)

    def delete_todo(self, todo_id: int) -> bool:
        """Delete a todo. Returns True if it existed."""
        cursor = self.conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self.conn.commit()
        return cursor.rowcount > 0
