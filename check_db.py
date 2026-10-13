from src.database import get_connection
c = get_connection()
with c.cursor() as cur:
    cur.execute("select schemaname, tablename, rowsecurity from pg_tables where schemaname='public' order by tablename")
    for r in cur.fetchall():
        print(r)
    cur.execute("select tablename, policyname, cmd from pg_policies where schemaname='public'")
    print("policies:", cur.fetchall())
c.close()
