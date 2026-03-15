import sys

with open('app.py', 'r') as f:
    content = f.read()

replacement = '''    user_id = data.get('user_id', 'user1')

    # --- SAAS QUOTA CHECK ---
    if user_id:
        import sqlite3
        import os
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Auto-create user for seamless mock-auth experience
            cursor.execute("INSERT OR IGNORE INTO User (id, email, tokens_balance, createdAt, updatedAt) VALUES (?, ?, 5, datetime('now'), datetime('now'))", (user_id, f"{user_id}@example.com"))
            conn.commit()

            cursor.execute("SELECT tokens_balance FROM User WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                quota = row[0]
                if quota <= 0:
                    conn.close()
                    return JSONResponse({"error": "[SYSTEM_ERROR] 免费额度已耗尽 (Quota Exceeded). 请充值获取更多额度。"}, status_code=403)
                else:
                    cursor.execute("UPDATE User SET tokens_balance = tokens_balance - 1 WHERE id = ?", (user_id,))
                    conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Quota check failed: {e}")
    # ------------------------'''

target = '''    # --- SAAS QUOTA CHECK ---
    if workspace_id and workspace_id != "temp":
        import sqlite3
        import os
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'dev.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT quota FROM Workspace WHERE id = ?", (workspace_id,))
            row = cursor.fetchone()
            if row:
                quota = row[0]
                if quota <= 0:
                    conn.close()
                    # We return a specific error structure to feed the SSE or prompt directly.
                    # Since this is before task start, we just return a 403 or 400.
                    return JSONResponse({"error": "[SYSTEM_ERROR] 免费额度已耗尽 (Quota Exceeded). 请充值获取更多额度。"}, status_code=403)
                else:
                    cursor.execute("UPDATE Workspace SET quota = quota - 1 WHERE id = ?", (workspace_id,))
                    conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Quota check failed: {e}")
    # ------------------------'''

content = content.replace(target, replacement)

with open('app.py', 'w') as f:
    f.write(content)
