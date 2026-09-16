import sqlite3

conn = sqlite3.connect("data/videogen.db")
conn.execute("UPDATE projects SET status='rendered', updated_at=datetime('now') WHERE id='b3a9c9fa'")
conn.execute("""INSERT OR REPLACE INTO job_history (id, project_id, action, status, details, finished_at) 
VALUES ('render_01', 'b3a9c9fa', 'render', 'completed', 'Rendered 16:9 Full HD & 9:16 Vertical with burned-in animated captions', datetime('now'))""")
conn.commit()
print("Updated project status:", conn.execute("SELECT id, name, status FROM projects WHERE id='b3a9c9fa'").fetchone())
print("Job history count:", len(conn.execute("SELECT * FROM job_history").fetchall()))
