import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='rawivision_db', user='shahd', password='password')
cur = conn.cursor()
cur.execute("SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name = 'video_appearances';")
print(cur.fetchall())
