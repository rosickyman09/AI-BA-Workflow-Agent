"""
template_db.py
==============
模板資料庫管理器：
- 上傳時預解析模板結構並儲存到 SQLite（可換成 PostgreSQL）
- 避免每次使用時重新解析
- 支援多個模板管理
"""

import sqlite3
import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from template_engine.template_parser import TemplateParser


class TemplateDatabase:
    def __init__(self, db_path: str = "templates.db", storage_dir: str = "template_files"):
        self.db_path = db_path
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化資料庫"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    file_path   TEXT NOT NULL,
                    file_hash   TEXT NOT NULL,
                    structure   TEXT NOT NULL,
                    mode        TEXT,
                    created_at  TEXT,
                    updated_at  TEXT
                )
            """)
            conn.commit()

    # ──────────────────────────────────────────────────────────────
    # 上傳模板（預解析）
    # ──────────────────────────────────────────────────────────────
    def upload_template(self, file_path: str, name: str = None) -> dict:
        """
        上傳並解析模板
        返回：模板資訊 dict（含 id）
        """
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"模板不存在：{file_path}")

        # 計算文件 hash（用作 ID）
        file_hash = self._file_hash(src)
        template_id = file_hash[:16]

        # 複製到儲存目錄
        dest = self.storage_dir / f"{template_id}.docx"
        shutil.copy2(src, dest)

        # 解析模板結構
        print(f"  解析模板結構：{src.name}...")
        parser = TemplateParser(str(dest))
        structure = parser.parse()

        # 儲存到資料庫
        template_name = name or src.stem
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO templates
                (id, name, file_path, file_hash, structure, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                template_name,
                str(dest),
                file_hash,
                json.dumps(structure, ensure_ascii=False),
                structure.get("mode"),
                now,
                now
            ))
            conn.commit()

        print(f"  ✓ 模板已儲存，ID：{template_id}")
        print(f"  ✓ 模式：{structure.get('mode')}")
        print(f"  ✓ Placeholder 數量：{len(structure.get('placeholders', []))}")
        print(f"  ✓ 表格數量：{len(structure.get('tables', []))}")

        return {
            "id": template_id,
            "name": template_name,
            "mode": structure.get("mode"),
            "structure": structure
        }

    # ──────────────────────────────────────────────────────────────
    # 讀取模板
    # ──────────────────────────────────────────────────────────────
    def get_template(self, template_id: str) -> dict:
        """根據 ID 讀取模板資訊"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, name, file_path, structure, mode FROM templates WHERE id = ?",
                (template_id,)
            ).fetchone()

        if not row:
            raise ValueError(f"找不到模板：{template_id}")

        return {
            "id": row[0],
            "name": row[1],
            "file_path": row[2],
            "structure": json.loads(row[3]),
            "mode": row[4]
        }

    def list_templates(self) -> list:
        """列出所有模板"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, mode, created_at FROM templates ORDER BY created_at DESC"
            ).fetchall()
        return [{"id": r[0], "name": r[1], "mode": r[2], "created_at": r[3]} for r in rows]

    def delete_template(self, template_id: str):
        """刪除模板"""
        info = self.get_template(template_id)
        Path(info["file_path"]).unlink(missing_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            conn.commit()

    # ──────────────────────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────────────────────
    def _file_hash(self, path: Path) -> str:
        """計算文件 MD5 hash"""
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
