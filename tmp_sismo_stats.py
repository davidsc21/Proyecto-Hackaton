import psycopg2
# try pooler first (current)
from src.database import get_connection
c = get_connection()
with c.cursor() as cur:
    cur.execute("select min(fecha_hora_utc), max(fecha_hora_utc), count(*), min(magnitud), max(magnitud) from public.sismo")
    print("sismo stats:", cur.fetchone())
    cur.execute("select count(*) from public.sismo where latitud is null or longitud is null or magnitud is null or fecha_hora_utc is null")
    print("nulls:", cur.fetchone()[0])
    cur.execute("select t.nombre, count(*) from public.sismo s join public.tipo_magnitud t on s.id_tipo_magnitud=t.id_tipo_magnitud group by t.nombre order by count desc")
    print("mag types:", cur.fetchall())
    cur.execute("select r.nombre, count(*) from public.sismo s join public.region r on s.id_region=r.id_region group by r.nombre")
    print("regions:", cur.fetchall())
c.close()
