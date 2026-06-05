import sqlite3
from typing import Optional
from db.base import create_connection

def get_report_source(source_key: str) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processed_report_sources WHERE source_key = ?", (source_key,))
    row = cursor.fetchone()
    conn.close()
    return row

def mark_report_source_processed(
    source_key: str,
    *,
    source_path: str = "",
    archive_name: str = "",
    inner_name: str = "",
    file_size: int = 0,
    file_mtime: float = 0,
    neuro_id: int | None = None,
    pdf_link: str = "",
) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO processed_report_sources (
                source_key, source_path, archive_name, inner_name,
                file_size, file_mtime, neuro_id, pdf_link, processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(source_key) DO UPDATE SET
                source_path = excluded.source_path,
                archive_name = excluded.archive_name,
                inner_name = excluded.inner_name,
                file_size = excluded.file_size,
                file_mtime = excluded.file_mtime,
                neuro_id = excluded.neuro_id,
                pdf_link = excluded.pdf_link,
                processed_at = CURRENT_TIMESTAMP
        ''', (
            source_key,
            source_path,
            archive_name,
            inner_name,
            file_size,
            file_mtime,
            neuro_id,
            pdf_link,
        ))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()
