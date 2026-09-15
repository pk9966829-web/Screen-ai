import sqlite3
from pathlib import Path
from datetime import datetime


DATABASE_PATH = Path("screen_ai.db")


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            status TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def save_observation(observation):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO observations
        (timestamp, filename, file_size, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            observation.get(
                "timestamp",
                datetime.now().isoformat()
            ),
            observation["filename"],
            observation["file_size"],
            observation["status"]
        )
    )

    connection.commit()
    connection.close()


def get_recent_observations(limit=5):
    connection = get_connection()

    cursor = connection.execute(
        """
        SELECT id, timestamp, filename, file_size, status
        FROM observations
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "id": row[0],
            "timestamp": row[1],
            "filename": row[2],
            "file_size": row[3],
            "status": row[4]
        }
        for row in rows
    ]