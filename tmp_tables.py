from src.database import get_connection

c = get_connection()
with c.cursor() as cur:
    cur.execute("select tablename from pg_tables where schemaname='public' order by tablename")
    print([r[0] for r in cur.fetchall()])
c.close()
