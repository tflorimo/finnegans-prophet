# Finnegans Prophet: Pronóstico de Ocupación Horaria de Salas

> **Forecasting probabilístico de ocupación de salas de reunión** mediante análisis temporal con Facebook Prophet

## 📑 Tabla de contenidos

- [Descripción general](#descripción-general)
- [Tecnologías y stack](#tecnologías-y-stack)
- [Getting Started](#getting-started)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Enfoque técnico](#enfoque-técnico)
- [Performance y optimizaciones](#performance-y-optimizaciones)
- [CLI y parámetros](#cli-y-parámetros)
- [Despliegue](#despliegue)
- [Roadmap](#roadmap)
- [Contribución](#contribución)
- [Licencia](#licencia)

---

## Descripción general

**Finnegans Prophet** es un script que predice la ocupación futura de salas de reunión mediante análisis histórico de eventos almacenados en MySQL. Utiliza **Facebook Prophet**, un modelo bayesiano especializado en series temporales con estacionalidades múltiples (diaria y semanal).

### ¿Qué problema resuelve?

En empresas con salas de reunión compartidas, es difícil **predecir disponibilidad real** de espacios. Este script:

- 🔮 Genera predicciones probabilísticas de ocupación horaria (7-90 días adelante)
- 📊 Identifica patrones de ocupación por sala y día de semana
- 🎯 Proporciona intervalos de confianza para tomar decisiones bajo incertidumbre
- 💾 Almacena resultados en BD para consumo por frontend/API

### Casos de uso

- **Heatmap interactivo**: Mostrar disponibilidad predicha en tiempo real
- **Recomendaciones de booking**: Sugerir salas con mayor probabilidad de estar libres
- **Análisis de utilización**: Identificar horarios críticos y patrones de demanda
- **Planificación de recursos**: Optimizar asignación de espacios

### Tipo de aplicación

- **Script CLI standalone** parametrizable
- Ejecutable bajo demanda o por **scheduler** (cron, systemd timer)
- Integración directa con MySQL
- Reutilizable como módulo Python

---

## Tecnologías y stack

| Categoría | Tecnología | Versión | Descripción |
|-----------|-----------|---------|------------|
| **Lenguaje** | Python | 3.9+ | Runtime recomendado |
| **Forecasting** | Facebook Prophet | 1.1+ | Modelo bayesiano de series temporales |
| **Data Processing** | Pandas | 1.3+ | Transformación y manipulación de datos |
| **Date Handling** | python-dateutil | 2.8+ | Parsing y operaciones con fechas |
| **Base de datos** | MySQL | 5.7+ | Almacenamiento de eventos y pronósticos |
| **Conector DB** | mysql-connector-python | 8.0+ | Driver MySQL puro en Python |
| **Config** | python-dotenv | 0.19+ | Carga de variables de entorno |

---

## Getting Started

### Requisitos previos

- **Python 3.9+** (se recomienda 3.10 o superior)
- **MySQL 5.7+** accesible con privilegios SELECT/INSERT/UPDATE
- **pip** (gestor de paquetes de Python)

### Instalación

#### 1. Clonar el repositorio

```bash
git clone https://github.com/tflorimo/finnegans-prophet.git
cd finnegans-prophet
```

#### 2. Crear entorno virtual (recomendado)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

#### 4. Configurar credenciales de base de datos

### Ejecución

#### Comando básico (con valores por defecto)

```bash
python finn_prophet.py
```

**Salida esperada:**
```
[OK] Guardadas/actualizadas 280 filas de pronósticos horarios
```

#### Con parámetros personalizados

```bash
# Predecir 14 días
python finn_prophet.py --horizon 14

# Horario laboral 07:00 a 20:00
python finn_prophet.py --start-hour 7 --end-hour 20

# Requerir mínimo 30 días de historia por sala
python finn_prophet.py --min-history 30

# Combinación de parámetros
python finn_prophet.py --horizon 14 --start-hour 7 --end-hour 20 --min-history 30
```

#### Ver ayuda

```bash
python finn_prophet.py --help
```

### Parámetros CLI

| Parámetro | Tipo | Default | Rango | Descripción |
|-----------|------|---------|-------|------------|
| `--horizon` | int | 7 | 1-365 | Días futuros a predecir |
| `--start-hour` | int | 8 | 0-23 | Hora inicio jornada laboral |
| `--end-hour` | int | 18 | 0-23 | Hora fin jornada laboral |
| `--min-history` | int | 14 | 7-365 | Mínimo días históricos requeridos por sala |

### Flujo de datos

**Entrada:**
- Tabla `events` en MySQL con campos: `roomEmail`, `startTime`, `endTime`
- Rango temporal: últimos 6 meses (configurable en código)
- Filtrado automático: lunes-viernes, dentro del horario especificado

**Procesamiento:**
1. Consulta eventos históricos
2. Convierte eventos a series de ocupación horaria (0=libre, 1=ocupada)
3. Valida mínimo histórico por sala
4. Entrena modelo Prophet independiente por sala
5. Genera predicciones para N días futuros
6. Normaliza predicciones al rango [0, 1]

**Salida:**
- Tabla `room_hourly_forecasts` con campos:
  - `roomEmail`: identificador de sala
  - `date`: timestamp de predicción (formato DATETIME)
  - `occupancyPredicted`: ocupación predicha (0.0-1.0)
  - `lower`, `upper`: intervalos de confianza 95%
  - `createdAt`, `updatedAt`: timestamps de auditoría

---

## Arquitectura del proyecto

### Estructura de archivos

```
finnegans-prophet/
├── finn_prophet.py          # Script principal
├── requirements.txt         # Dependencias pip
├── README.md               # Este archivo
└── .gitignore              # Archivos a ignorar
```

### Descripción de funciones

| Función | Responsabilidad |
|---------|-----------------|
| `parse_args()` | Parse de argumentos CLI y valores por defecto |
| `connect_db()` | Conexión a MySQL con configuración desde entorno |
| `ensure_table()` | Crea tabla `room_hourly_forecasts` si no existe (idempotente) |
| `fetch_raw_events()` | Consulta eventos históricos de últimos 6 meses |
| `prepare_hourly_data()` | Convierte eventos a series horarias por sala |
| `forecast_per_room()` | Entrena Prophet y predice por sala |
| `upsert_forecasts()` | Inserta/actualiza predicciones (ON DUPLICATE KEY UPDATE) |
| `main()` | Orquesta el flujo completo |

### Flujo de ejecución

```
main()
  ├─ parse_args()                    # Leer parámetros CLI
  ├─ connect_db()                    # Conectar a MySQL
  ├─ ensure_table()                  # Crear tabla si no existe
  ├─ fetch_raw_events()              # SELECT eventos (6 meses)
  │   └─ DataFrame(roomEmail, startTime, endTime)
  ├─ prepare_hourly_data()           # Convertir a series horarias
  │   └─ DataFrame(ds, y, roomEmail) por sala
  ├─ forecast_per_room()             # Entrenar Prophet por sala
  │   ├─ Prophet.fit()
  │   ├─ Prophet.predict()
  │   └─ Clamp [0, 1]
  └─ upsert_forecasts()              # INSERT/UPDATE en DB
```

---

## Enfoque técnico

### Decisiones de diseño

#### 1. **Modelado independiente por sala**

Cada sala tiene su propio modelo Prophet. Ventajas:

- Captura patrones específicos de ocupación (ej: sala A popular lunes, sala B popular viernes)
- Evita sesgo cruzado entre espacios con demandas diferentes
- Permite ajustes granulares de hiperparámetros

#### 2. **Conversión a ocupación binaria**

Los eventos se transforman a series de 0 (libre) / 1 (ocupada) por hora:

```python
# Entrada: evento de 14:00-15:30
# Salida: hora 14 → 1, hora 15 → 1 (ocupada parcialmente es ocupada)
```

Beneficios:
- Normaliza el impacto de eventos de diferente duración
- Patrón consistente independiente del número de reuniones por hora
- Facilita visualización en heatmap

#### 3. **Uso de Facebook Prophet**

**Justificación técnica:**

| Aspecto | Razón |
|--------|-------|
| **Estacionalidad múltiple** | Detecta patrones diarios (picos 10:00-11:00) y semanales (lunes > viernes) |
| **Robustez** | Maneja datos faltantes, cambios abruptos (changepoints) sin reentrenamiento |
| **Interpretabilidad** | Descompone predicción en trend + seasonality + residual (no es "caja negra") |
| **Incertidumbre cuantificada** | Proporciona intervalos de confianza (credible intervals) 95% |
| **Eficiencia** | O(n log n) vs O(n²) de ARIMA, entrenable en <1s/sala típicamente |

#### 4. **Filtrado temporal**

- **Días**: solo lunes-viernes (`weekday < 5`), excluye fines de semana
- **Horas**: rango configurable (default 08:00-18:00)
- **Razón**: minimiza ruido de eventos atípicos fuera de horario laboral

### Buenas prácticas implementadas

#### Modularidad y separación de responsabilidades

```python
# Cada función = una responsabilidad
fetch_raw_events()      # Lectura de datos (I/O)
prepare_hourly_data()   # Transformación de datos
forecast_per_room()     # Lógica de ML
upsert_forecasts()      # Persistencia (I/O)
```

#### Manejo robusto de fechas

```python
# Conversión explícita
df_events["startTime"] = pd.to_datetime(df_events["startTime"])

# Operaciones con granularidad clara
full_range = pd.date_range(start=min_date, end=max_date, freq="h")

# Filtrado temporal preciso
future = future[(future["ds"].dt.hour >= start_hour) & ...]
```

#### Logging y observabilidad

```python
# Mensajes estructurados para debugging
[WARN] Sala {room}: poca historia (120 horas < 360), se omite.
[OK] Guardadas/actualizadas 280 filas de pronósticos horarios
[ERROR] Conexión DB: [específico error]
```

#### Seguridad

- Credenciales desde variables de entorno (no hardcoded)
- Prepared statements automáticos (mysql-connector)
- Manejo seguro de conexiones (try/finally)
- Validación implícita: Prophet rechaza datos inválidos

---

## Performance y optimizaciones

### Optimizaciones implementadas

#### 1. Per-room training (paralelizable)

Cada sala se entrena independientemente → permite paralelización futura:

```python
# O(n_salas × log(n_eventos_por_sala))
# Típicamente 30-120s para 20-50 salas
```

#### 2. Configuración optimizada de Prophet

```python
Prophet(
    weekly_seasonality=True,      # Patrón L-V vs fin de semana
    daily_seasonality=True,       # Picos horarios (10:00-12:00)
    yearly_seasonality=False,     # Datos < 2 años típicamente
    changepoint_prior_scale=0.05  # Adaptación suave a cambios
)
```

#### 3. Filtrado early de datos

- Consulta SQL: solo últimos 6 meses
- Filtrado temporal: solo L-V, horario especificado
- Validación: mínimo histórico por sala

#### 4. Normalización de predicciones

```python
fc[col] = fc[col].clip(0, 1)  # O(n), evita post-procesamiento
```

### Benchmarks típicos

| Métrica | Valor | Condiciones |
|---------|-------|------------|
| Tiempo total | 30-120s | 20-50 salas, 6 meses historia |
| Tiempo/sala | 0.5-2s | Prophet fit + predict |
| Rows generadas | 280-700 | 7 días × 10 horas/día × N salas |
| Memoria RAM | 50-200MB | Depende de volumen histórico |

### Posibles mejoras futuras

- **Paralelización**: `multiprocessing.Pool` para entrenar múltiples salas simultáneamente
- **Caching de modelos**: Serializar modelos con `pickle` para reutilizar entre ejecuciones
- **Batch insert**: Agrupar inserciones para reducir round-trips a BD
- **Modelo ensemble**: Combinar Prophet + ARIMA para robustez mejorada

---

## Despliegue

### Ejecución en producción

#### Opción 1: Cron job (Linux/macOS)

```bash
# Editar crontab
crontab -e

# Ejecutar diariamente a las 23:00
0 23 * * * cd /opt/finnegans-prophet && python finn_prophet.py >> /var/log/prophet.log 2>&1

# Ejecutar cada 6 horas
0 */6 * * * cd /opt/finnegans-prophet && python finn_prophet.py >> /var/log/prophet.log 2>&1

# Ejecutar cada día a diferentes horas
0 8,14,20 * * * cd /opt/finnegans-prophet && python finn_prophet.py --horizon 7 >> /var/log/prophet.log 2>&1
```

#### Opción 2: systemd timer (Linux)

**Crear `/etc/systemd/system/prophet.service`:**

```ini
[Unit]
Description=Finnegans Prophet Forecasting
After=network.target mysql.service

[Service]
Type=oneshot
WorkingDirectory=/opt/finnegans-prophet
ExecStart=/usr/bin/python3 finn_prophet.py
User=user
StandardOutput=journal
StandardError=journal
```

**Crear `/etc/systemd/system/prophet.timer`:**

```ini
[Unit]
Description=Finnegans Prophet Timer

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 23:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Activar:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable prophet.timer
sudo systemctl start prophet.timer
sudo systemctl status prophet.timer
```

#### Opción 3: Docker

**Dockerfile:**

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY finn_prophet.py .

CMD ["python", "finn_prophet.py"]
```

**Build y ejecución:**

```bash
docker build -t finnegans-prophet .
**Con docker-compose:**

```yaml
version: '3.8'
services:
  prophet:
    build: .
    depends_on:
      - mysql
  
  mysql:
    image: mysql:5.7
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

#### Opción 4: Invocación desde aplicación

```python
# Importar como módulo
import sys
sys.path.insert(0, '/opt/finnegans-prophet')

from finn_prophet import main, parse_args

# Override de parámetros
sys.argv = ['prog', '--horizon', '14', '--min-history', '30']

try:
    main()
except SystemExit as e:
    print(f"Exit code: {e.code}")
```

### Recomendaciones operativas

| Aspecto | Recomendación |
|--------|--------------|
| **Frecuencia** | Diaria (23:00) o cada 6 horas en sistemas de alta volatilidad |
| **Horario** | Preferentemente fuera de horario laboral (23:00-06:00) |
| **Timeout** | 10-15 minutos en job scheduler |
| **Logs** | Redirigir a syslog o archivo con rotación |
| **Alertas** | Monitorear exit codes y último timestamp de ejecución |
| **BD** | Crear índice en `(roomEmail, date)` para queries rápidas |
| **Capacidad** | Purgar predicciones antiguas (> 90 días) periódicamente |

---

## CLI y parámetros

### Uso básico

```bash
python finn_prophet.py [OPTIONS]
```

### Opciones disponibles

```
Forecast de ocupación por sala (Prophet) para heatmap

optional arguments:
  -h, --help            Show help message
  
  --horizon HORIZON     Días futuros a predecir
                        Default: 7
                        Range: 1-365 (recomendado 1-90)
  
  --start-hour START_HOUR
                        Hora inicio jornada laboral (0-23)
                        Default: 8
  
  --end-hour END_HOUR   Hora fin jornada laboral (0-23)
                        Default: 18
  
  --min-history MIN_HISTORY
                        Mínimo de días históricos para entrenar por sala
                        Default: 14
                        Range: 7-365 (recomendado 14-30)
```

### Ejemplos de uso

#### Predicción estándar (valores por defecto)

```bash
$ python finn_prophet.py
[OK] Guardadas/actualizadas 280 filas de pronósticos horarios
```

Resultado:
- 7 días de predicción
- Horario 08:00-18:00
- Mínimo 14 días de historia por sala

#### Forecast a 2 semanas

```bash
$ python finn_prophet.py --horizon 14
[OK] Guardadas/actualizadas 560 filas de pronósticos horarios
```

#### Horario extendido (07:00-20:00)

```bash
$ python finn_prophet.py --start-hour 7 --end-hour 20
[OK] Guardadas/actualizadas 390 filas de pronósticos horarios
```

#### Requerir mayor volumen histórico

```bash
$ python finn_prophet.py --min-history 45
[WARN] Sala room-101@company.com: poca historia (120 horas < 360), se omite.
[OK] Guardadas/actualizadas 168 filas de pronósticos horarios
```

#### Combinación de parámetros

```bash
$ python finn_prophet.py --horizon 30 --start-hour 6 --end-hour 22 --min-history 60
[OK] Guardadas/actualizadas 1680 filas de pronósticos horarios
```

### Códigos de salida

| Código | Significado | Acción recomendada |
|--------|------------|------------------|
| **0** | Éxito | Predicciones insertadas correctamente |
| **1** | Error de conexión DB | Verificar credenciales, host, puerto MySQL |
| **2** | Error en proceso | Revisar logs, validar datos históricos |

---

## Roadmap

### Corto plazo (v1.1)

- [ ] Paralelización con `multiprocessing.Pool` para entrenar múltiples salas
- [ ] Caching de modelos Prophet (serialización .pkl) entre ejecuciones
- [ ] Batch inserts para reducir latencia de BD
- [ ] Logging con módulo `logging` estándar de Python

### Mediano plazo (v1.5)

- [ ] Soporte para múltiples modelos: ARIMA, ExponentialSmoothing
- [ ] Cross-validation y métricas (RMSE, MAE, MAPE)
- [ ] Dashboard interactivo (Streamlit o Plotly)
- [ ] API REST (FastAPI) para predicciones en tiempo real
- [ ] Exportación de reportes (PDF, HTML)

### Largo plazo (v2.0)

- [ ] Integración con Google Calendar API / Outlook
- [ ] Detección automática de anomalías en datos históricos
- [ ] Modelos de deep learning (LSTM, Transformer)
- [ ] UI web para configuración de parámetros
- [ ] Alertas automáticas de sobrecapacidad

---

## Contribución

### Clonar y desarrollar

```bash
# Clonar repositorio
git clone https://github.com/tflorimo/finnegans-prophet.git
cd finnegans-prophet

# Crear rama de feature
git checkout -b feature/nueva-funcionalidad

# Realizar cambios
# ... editar código ...

# Commit descriptivo
git add .
git commit -m "feat: agregar paralelización con multiprocessing"

# Push y crear Pull Request
git push origin feature/nueva-funcionalidad
```

### Estándares de código

- **PEP8**: Usar `black` o `autopep8` para formateo
- **Type hints**: Recomendado en funciones nuevas
- **Docstrings**: Documentar funciones complejas
- **Logging**: Usar formato `[LEVEL] mensaje` consistente

### Versionado

- Seguir **Semantic Versioning** (v1.0.0 = MAJOR.MINOR.PATCH)
- Actualizar `requirements.txt` y `README.md` en cada release
- Crear git tags: `git tag -a v1.1.0 -m "Version 1.1.0"`

---

## Licencia

Este proyecto está licenciado bajo la **MIT License**.

Ver archivo `LICENSE` para detalles completos.

---

## Información adicional

### Recursos útiles

- [Documentación de Facebook Prophet](https://facebook.github.io/prophet/)
- [Pandas - Data Manipulation](https://pandas.pydata.org/docs/)
- [MySQL Connector Python](https://dev.mysql.com/doc/connector-python/en/)

### Estructura de tabla room_hourly_forecasts

```sql
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
```

### Contacto

- **Repositorio**: https://github.com/tflorimo/finnegans-prophet
- **Issues**: Reportar en GitHub Issues

---

**Última actualización**: Diciembre 2025  
**Versión**: 1.0.0  
**Estado**: Production-ready