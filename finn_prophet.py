import os
import sys
import argparse
import math
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from prophet import Prophet
import mysql.connector

def parse_args():
    ap = argparse.ArgumentParser(description="Forecast de ocupación por sala (Prophet) para heatmap")
    ap.add_argument("--horizon", type=int, default=7, help="Días futuros a predecir (por defecto 7).")
    ap.add_argument("--start-hour", type=int, default=8, help="Hora inicio jornada (0-23).")
    ap.add_argument("--end-hour", type=int, default=18, help="Hora fin jornada (0-23).")
    ap.add_argument("--min-history", type=int, default=14,
                    help="Mínimo de días históricos para entrenar por sala (por defecto 15).")
    return ap.parse_args()

def connect_db():
    cfg = {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASS", ""),
        "database": os.environ.get("DB_NAME", "finnegans"),
    }
    return mysql.connector.connect(**cfg)

def ensure_table(conn):
    # Tabla para pronósticos horarios
    # Incluimos updatedAt y deletedAt para compatibilidad con Sequelize (timestamps: true, paranoid: true)
    sql = """
    CREATE TABLE IF NOT EXISTS room_hourly_forecasts (
      id INT AUTO_INCREMENT PRIMARY KEY,
      roomEmail VARCHAR(255) NOT NULL,
      date DATETIME NOT NULL,
      occupancyPredicted FLOAT NOT NULL,
      lower FLOAT NULL,
      upper FLOAT NULL,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uniq_room_datetime (roomEmail, date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

# Trae eventos de los últimos 6 meses
def fetch_raw_events(conn) -> pd.DataFrame:
    cur = conn.cursor(dictionary=True)
    query = """
    SELECT roomEmail, startTime, endTime
    FROM events
    WHERE startTime >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
    AND startTime IS NOT NULL AND endTime IS NOT NULL
    ORDER BY roomEmail, startTime
    """
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows)

def prepare_hourly_data(df_events: pd.DataFrame, start_hour: int, end_hour: int) -> pd.DataFrame:
    if df_events.empty:
        return pd.DataFrame()

    df_events["startTime"] = pd.to_datetime(df_events["startTime"])
    df_events["endTime"] = pd.to_datetime(df_events["endTime"])
    
    data_frames = []
    
    max_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for room, group in df_events.groupby("roomEmail"):
        if group.empty:
            continue

        # Busca la fecha mínima de inicio de evento (min_date) y la lleva al inicio del día.
        min_date = group["startTime"].min().floor("D")
        if min_date >= max_date:
            continue

        full_range = pd.date_range(start=min_date, end=max_date, freq="h")
        
        # filtrar por horas laborales (8 a 18hs)
        full_range = full_range[(full_range.hour >= start_hour) & (full_range.hour < end_hour)]
        
        if full_range.empty:
            continue

        # serie base en 0 (libre por defecto)
        ts = pd.Series(0.0, index=full_range)
        
        # ocupación
        for _, row in group.iterrows():
            # redondeo de tiempos (hacia abajo/arriba)
            s = row["startTime"].floor("h")
            e = row["endTime"].ceil("h")
            
            # Genera rango horarios de una hora
            evt_rng = pd.date_range(s, e, freq="h", inclusive="left")
            
            # Intersección con el índice de la serie temporal (sólo 8 a 18hs)
            valid = ts.index.intersection(evt_rng)

            # Marca horas como 1.0 = ocupado
            ts.loc[valid] = 1.0

        # Construye tabla final por sala (ds: datetime, y: ocupación)  
        room_df = pd.DataFrame({"ds": ts.index, "y": ts.values})
        room_df["roomEmail"] = room
        data_frames.append(room_df)

    if not data_frames:
        return pd.DataFrame()
        
    return pd.concat(data_frames, ignore_index=True)

# entrenamiento y forecast (preddicion)
def forecast_per_room(df_usage: pd.DataFrame, horizon_days: int, start_hour: int, end_hour: int, min_history: int) -> pd.DataFrame:
    results = []

    for room, g in df_usage.groupby("roomEmail"):
        g = g.sort_values("ds")
        
        # puntos necesarios (días * horas_por_dia)
        points_needed = min_history * (end_hour - start_hour)
        if len(g) < points_needed:
            print(f"[WARN] Sala {room}: poca historia ({len(g)} horas < {points_needed}), se omite.", file=sys.stderr)
            continue

        # aprende patrones por hora, día y semana. No mira patrones anuales 
        # y controla qué tan sensible es a cambios bruscos en la tendencia
        m = Prophet(
            weekly_seasonality=True,
            daily_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        m.fit(g)

        # futuro: horizon_days * 24 horas (luego filtramos)
        future = m.make_future_dataframe(periods=horizon_days * 24, freq="h", include_history=False)
        
        # filtrar futuro por horas laborales y dias de semana (L-V)
        future = future[
            (future["ds"].dt.hour >= start_hour) & 
            (future["ds"].dt.hour < end_hour) & 
            (future["ds"].dt.weekday < 5)
        ]
        
        if future.empty:
            continue

        fc = m.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]

        # clamp por las dudas (dejarlos entre 0 y 1)
        for col in ["yhat", "yhat_lower", "yhat_upper"]:
            fc[col] = fc[col].clip(0, 1)

        fc.insert(0, "roomEmail", room)
        results.append(fc)

    if not results:
        return pd.DataFrame(columns=["roomEmail", "ds", "yhat", "yhat_lower", "yhat_upper"])

    out = pd.concat(results, ignore_index=True)
    return out

# upsert el resultado del pronostico en la db
def upsert_forecasts(conn, df_fc: pd.DataFrame):
    if df_fc.empty:
        return 0

    # df_fc tiene 'ds' que es datetime
    rows = list(
        df_fc[["roomEmail", "ds", "yhat", "yhat_lower", "yhat_upper"]]
        .itertuples(index=False, name=None)
    )

    # Si no existe, inserta. Si existe, actualiza.
    sql = """
    INSERT INTO room_hourly_forecasts (roomEmail, date, occupancyPredicted, lower, upper, createdAt, updatedAt)
    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
      occupancyPredicted = VALUES(occupancyPredicted),
      lower = VALUES(lower),
      upper = VALUES(upper),
      updatedAt = NOW()
    """
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    affected = cur.rowcount
    cur.close()
    return affected

def main():
    args = parse_args()

    try:
        conn = connect_db()
    except Exception as e:
        print(f"[ERROR] Conexión DB: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        ensure_table(conn)

        raw_events = fetch_raw_events(conn)
        usage = prepare_hourly_data(raw_events, args.start_hour, args.end_hour)
        
        if usage.empty:
            print("[INFO] No hay eventos para procesar.")
            sys.exit(0)

        fc = forecast_per_room(
            usage,
            horizon_days=args.horizon,
            start_hour=args.start_hour,
            end_hour=args.end_hour,
            min_history=args.min_history,
        )

        affected = upsert_forecasts(conn, fc)
        print(f"[OK] Guardadas/actualizadas {affected} filas de pronósticos horarios")

    except Exception as e:
        print(f"[ERROR] Proceso: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
