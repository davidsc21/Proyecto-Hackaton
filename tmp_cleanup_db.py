from src.database import get_connection

c = get_connection()
try:
    with c.cursor() as cur:
        cur.execute("drop table if exists public.earthquakes cascade")
        cur.execute("truncate table public.risk_zones, public.model_runs, public.predictions restart identity")
    c.commit()
    print("cleaned")
finally:
    c.close()
