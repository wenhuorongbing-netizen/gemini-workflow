import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dev.db')

class DevHouseDB:
    @staticmethod
    def _get_conn():
        return sqlite3.connect(DB_PATH)

    @staticmethod
    def init_db():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DevHouseQueue (
                id TEXT PRIMARY KEY,
                prompt TEXT,
                target_repo TEXT,
                kb_links TEXT,
                model TEXT,
                webhook_url TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cursor.execute("ALTER TABLE DevHouseQueue ADD COLUMN agent_state TEXT DEFAULT 'PLANNING'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE DevHouseQueue ADD COLUMN accumulated_context TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE DevHouseQueue ADD COLUMN iteration INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CorporateMemory (
                id TEXT PRIMARY KEY,
                category TEXT,
                error_pattern TEXT,
                solution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DevHouseState (
                id TEXT PRIMARY KEY,
                branch TEXT,
                iteration INTEGER,
                max_iterations INTEGER,
                accumulated_context TEXT,
                status TEXT,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create User table if missing for mock-auth experience
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS User (
                id TEXT PRIMARY KEY,
                email TEXT,
                tokens_balance INTEGER,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Workspaces (
                id TEXT PRIMARY KEY,
                name TEXT,
                steps TEXT,
                results TEXT,
                watch_folder TEXT,
                webhook_url TEXT,
                cron_schedule TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Globals (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Templates (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                steps TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS AppRunHistory (
                workspace_id TEXT PRIMARY KEY,
                history_data TEXT
            )
        ''')
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_workspaces():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, steps, results, watch_folder, webhook_url, cron_schedule FROM Workspaces")
        workspaces = {}
        for row in cursor.fetchall():
            workspaces[row[0]] = {
                "name": row[1],
                "steps": json.loads(row[2]) if row[2] else [],
                "results": json.loads(row[3]) if row[3] else {}
            }
            if row[4]: workspaces[row[0]]["watch_folder"] = row[4]
            if row[5]: workspaces[row[0]]["webhook_url"] = row[5]
            if row[6]: workspaces[row[0]]["cron_schedule"] = row[6]
        conn.close()
        return workspaces

    @staticmethod
    def get_workspace(workspace_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name, steps, results, watch_folder, webhook_url, cron_schedule FROM Workspaces WHERE id = ?", (workspace_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        workspace = {
            "name": row[0],
            "steps": json.loads(row[1]) if row[1] else [],
            "results": json.loads(row[2]) if row[2] else {}
        }
        if row[3]: workspace["watch_folder"] = row[3]
        if row[4]: workspace["webhook_url"] = row[4]
        if row[5]: workspace["cron_schedule"] = row[5]
        return workspace

    @staticmethod
    def save_workspace(workspace_id, name, steps, results, watch_folder, webhook_url, cron_schedule):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO Workspaces (id, name, steps, results, watch_folder, webhook_url, cron_schedule)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (workspace_id, name, json.dumps(steps) if steps else "[]", json.dumps(results) if results else "{}", watch_folder, webhook_url, cron_schedule))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_workspace(workspace_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Workspaces WHERE id = ?", (workspace_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_globals():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM Globals")
        globals_dict = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return globals_dict

    @staticmethod
    def save_globals(data_dict):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Globals")
        for k, v in data_dict.items():
            cursor.execute("INSERT INTO Globals (key, value) VALUES (?, ?)", (k, v))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_templates():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, steps FROM Templates")
        templates = {}
        for row in cursor.fetchall():
            templates[row[0]] = {
                "name": row[1],
                "description": row[2],
                "steps": json.loads(row[3]) if row[3] else []
            }
        conn.close()
        return templates

    @staticmethod
    def save_template(template_id, name, description, steps):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO Templates (id, name, description, steps)
            VALUES (?, ?, ?, ?)
        ''', (template_id, name, description, json.dumps(steps) if steps else "[]"))
        conn.commit()
        conn.close()

    @staticmethod
    def get_workspace_history(workspace_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT history_data FROM AppRunHistory WHERE workspace_id = ?", (workspace_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return []
        return json.loads(row[0]) if row[0] else []

    @staticmethod
    def save_workspace_history(workspace_id, history_list):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO AppRunHistory (workspace_id, history_data)
            VALUES (?, ?)
        ''', (workspace_id, json.dumps(history_list)))
        conn.commit()
        conn.close()

    @staticmethod
    def get_recent_corporate_memories(limit=5):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT category, error_pattern, solution FROM CorporateMemory ORDER BY created_at DESC LIMIT ?", (limit,))
        memories = cursor.fetchall()
        conn.close()
        return memories

    @staticmethod
    def add_corporate_memory(memory_id, category, error_pattern, solution):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO CorporateMemory (id, category, error_pattern, solution) VALUES (?, ?, ?, ?)",
                       (memory_id, category, error_pattern, solution))
        conn.commit()
        conn.close()

    @staticmethod
    def update_task_agent_state(task_id, state):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE DevHouseQueue SET agent_state = ?, updated_at = datetime('now') WHERE id = ?", (state, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def save_loop_state(branch_name, iteration, max_iterations, accumulated_context, status, task_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO DevHouseState (id, branch, iteration, max_iterations, accumulated_context, status, updatedAt)
            VALUES ('active', ?, ?, ?, ?, ?, datetime('now'))
        """, (branch_name, iteration, max_iterations, accumulated_context, status))
        cursor.execute("UPDATE DevHouseQueue SET accumulated_context = ?, iteration = ? WHERE id = ?", (accumulated_context, iteration, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_task_state(task_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT agent_state, accumulated_context, iteration FROM DevHouseQueue WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    @staticmethod
    def update_task_status(task_id, status):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE DevHouseQueue SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_pending_task():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, prompt, target_repo, kb_links, model, webhook_url FROM DevHouseQueue WHERE status IN ('pending', 'running') AND agent_state NOT IN ('DEPLOYED', 'FAILED') ORDER BY created_at ASC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row

    @staticmethod
    def get_task_counts():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM DevHouseQueue WHERE status = 'completed'")
        completed_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM DevHouseQueue WHERE status = 'failed'")
        failed_count = cursor.fetchone()[0]
        conn.close()
        return completed_count, failed_count

    @staticmethod
    def get_first_webhook_url():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT webhook_url FROM DevHouseQueue WHERE webhook_url IS NOT NULL AND webhook_url != '' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    @staticmethod
    def clear_webhooks():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE DevHouseQueue SET webhook_url = NULL")
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_tasks():
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, prompt, status FROM DevHouseQueue")
        details = [{"id": r[0], "prompt": r[1], "status": r[2]} for r in cursor.fetchall()]
        conn.close()
        return details

    @staticmethod
    def insert_task(task_id, prompt, target_repo, kb_links, model, webhook_url, status='pending', created_at=None):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        if created_at:
            cursor.execute("""
                INSERT INTO DevHouseQueue (id, prompt, target_repo, kb_links, model, webhook_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (task_id, prompt, target_repo, kb_links, model, webhook_url, status, created_at))
        else:
            cursor.execute("""
                INSERT INTO DevHouseQueue (id, prompt, target_repo, kb_links, model, webhook_url, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, prompt, target_repo, kb_links, model, webhook_url, status))
        conn.commit()
        conn.close()

    @staticmethod
    def get_queue_rows():
        conn = DevHouseDB._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM DevHouseQueue ORDER BY created_at DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_run_history(run_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT logs, userId, workflowId FROM RunHistory WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    @staticmethod
    def update_run_history_status(run_id, status):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE RunHistory SET status = ? WHERE id = ?", (status, run_id))
        conn.commit()
        conn.close()

    @staticmethod
    def check_and_deduct_quota(user_id):
        conn = DevHouseDB._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO User (id, email, tokens_balance, createdAt, updatedAt) VALUES (?, ?, 5, datetime('now'), datetime('now'))", (user_id, f"{user_id}@example.com"))
        conn.commit()

        cursor.execute("SELECT tokens_balance FROM User WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return "not_found"

        quota = row[0]
        if quota <= 0:
            conn.close()
            return "exceeded"

        cursor.execute("UPDATE User SET tokens_balance = tokens_balance - 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return "ok"
