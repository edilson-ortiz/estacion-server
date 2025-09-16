from app.database import get_connection;

kmilimetro = 10

def get_latest_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM datos_sensores ORDER BY fecha DESC")
    rows = cursor.fetchall()
    conn.close()

    if rows:
        historial = []
        for row in rows:
            historial.append({
                "id": row[0],
                "sensor_id": row[1],
                "temperatura": row[2],
                "humedad": row[3],
                "lluvia": row[4],
                "fecha": row[5]
            })
        return historial
    
    return {"message": "No hay datos aún"}

def get_all_by_sensor(sensor_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    # Buscamos solo los registros del sensor_id dado
    cursor.execute("SELECT * FROM datos_sensores WHERE sensor_id = %s ORDER BY fecha DESC", (sensor_id,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        historial = []
        for row in rows:
            historial.append({
                "id": row[0],
                "sensor_id": row[1],
                "temperatura": row[2],
                "humedad": row[3],
                "lluvia": row[4],
                "fecha": row[5]
            })
        return historial
    
    return {"message": f"No hay datos para el sensor {sensor_id}"}



def get_daily_summary(sensor_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    # Consulta SQL para resumir por día los últimos 10 días
    cursor.execute("""
        SELECT 
            DATE(fecha) AS dia,
            SUM(lluvia) AS total_lluvia,
            MIN(temperatura) AS temp_min,
            MAX(temperatura) AS temp_max,
            MAX(humedad) AS humedad
        FROM datos_sensores
        WHERE sensor_id = %s
          AND fecha >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(fecha)
        ORDER BY dia DESC
    """, (sensor_id,))

    rows = cursor.fetchall()
    conn.close()

    if rows:
        resumen = []
        for row in rows:
            resumen.append({
                "dia": row[0].isoformat(),  # para que sea JSON serializable
                "total_lluvia": float(row[1])/kmilimetro,
                "temp_min": float(row[2]),
                "temp_max": float(row[3]),
                "humedad": float(row[4])
            })
        return resumen
    
    return {"message": f"No hay datos de los últimos 30 días para el sensor {sensor_id}"}

def get_latest_record(sensor_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM datos_sensores
        WHERE sensor_id = %s
        ORDER BY fecha DESC
        LIMIT 1
    """, (sensor_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        # Ajusta los índices según el orden de tus columnas en la tabla
        record = {
            "id": row[0],
            "sensor_id": row[1],          
            "temperatura": float(row[2]),
            "humedad": float(row[3]),
            "lluvia": float(row[4])/kmilimetro,
            "fecha": row[5].isoformat(sep=' '), # fecha y hora como 'YYYY-MM-DD HH:MM:SS'
            "estado":estado_sensor( row[1],10)
        }
        return record
    
    return {"message": f"No hay registros para el sensor {sensor_id}"}

def estado_sensor(sensor_id: str, minutos: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM datos_sensores d
            WHERE d.sensor_id = %s
              AND d.fecha > NOW() - make_interval(mins := %s)
        )
    """, (sensor_id, minutos))

    existe = cursor.fetchone()[0]  # devuelve True o False
    conn.close()

    return existe
