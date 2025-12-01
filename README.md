# Pronóstico de Ocupación Horaria (Prophet)

Script en **Python** que predice la ocupación futura de salas de reunión usando **Facebook Prophet**.  
Toma los eventos históricos desde MySQL, calcula ocupación por hora (L–V, horario laboral) y guarda las predicciones en la tabla `room_hourly_forecasts`.

---
# Pasos internos del script

1. Lee eventos históricos desde la base.
2. Convierte cada evento en ocupación por hora.
3. Entrena un modelo Prophet por sala.
4. Predice la ocupación de los próximos días .
5. Guarda los resultados en MySQL para que el frontend lo use

---

## Requisitos de instalación
Antes de ejecutar el script de Python es necesario ejecutar PiP para instalar los siguientes paquetes, que también se encuentran en el requirements.txt

```bash
pip install pandas prophet mysql-connector-python python-dotenv python-dateutil