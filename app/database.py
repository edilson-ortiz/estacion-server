import psycopg2

def get_connection():
    conn = psycopg2.connect(
        database="db_estacion",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432"
    )
    
    # Configurar la zona horaria de la sesión a Bolivia
    with conn.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'America/La_Paz';")
    
    return conn