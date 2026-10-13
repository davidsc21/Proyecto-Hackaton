import psycopg2
candidates = [
    "postgresql://postgres:universitariatecnologica@db.pxpjffhtwwnmjyjgeihs.supabase.co:5432/postgres",
    "postgresql://postgres:[universitariatecnologica]@db.pxpjffhtwwnmjyjgeihs.supabase.co:5432/postgres",
]
for url in candidates:
    try:
        c = psycopg2.connect(url, connect_timeout=10)
        print("OK:", url)
        with c.cursor() as cur:
            cur.execute("select current_database(), current_user")
            print(cur.fetchone())
        c.close()
    except Exception as e:
        print("FAIL:", url, "->", repr(e))
PY
# also test pooler direct host via IPv4 for comparison (already known)
print("done")
