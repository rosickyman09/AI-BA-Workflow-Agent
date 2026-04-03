from sqlalchemy import text
from app.services.db_service import get_db
db = next(get_db())
projs = db.execute(text("SELECT project_id, name FROM projects WHERE status='active' LIMIT 3")).fetchall()
for p in projs:
    pid = str(p[0])
    rag_ids = [str(r[0]) for r in db.execute(text("SELECT doc_id FROM rag_documents WHERE project_id=:pid"), {"pid": pid}).fetchall()]
    doc_ids = [str(d[0]) for d in db.execute(text("SELECT doc_id FROM documents WHERE project_id=:pid AND status='approved'"), {"pid": pid}).fetchall()]
    print("PROJ", pid[:8], p[1])
    print("  RAG:", rag_ids)
    print("  DOCS:", doc_ids)
    same = set(rag_ids) & set(doc_ids)
    only_docs = set(doc_ids) - set(rag_ids)
    print("  IN BOTH:", list(same))
    print("  ONLY IN DOCS (not in RAG):", list(only_docs))
    print()
