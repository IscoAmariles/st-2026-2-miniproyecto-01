# Datos

La serie del grupo está en esta carpeta, en CSV.

| Campo | Valor |
|---|---|
| Archivo | `debito_islandia.csv` |
| Qué mide | Uso mensual de tarjetas débito en el comercio minorista de Islandia: valor total de las compras hechas con tarjeta débito en el mes, en millones de coronas islandesas (ISK) a precios corrientes, según la documentación de la fuente |
| Fuente | Statistics Iceland (Hagstofa Íslands), <https://statice.is>. Se tomó de la copia que distribuye el paquete de R `fpp2` (Hyndman, *Forecasting: Principles and Practice*, 2.ª ed., conjunto `debitcards`), publicada en CSV por el repositorio Rdatasets: <https://github.com/vincentarelbundock/Rdatasets/blob/master/csv/fpp2/debitcards.csv> |
| Licencia | Datos de Statistics Iceland: Creative Commons Atribución 4.0 Internacional (CC BY 4.0), con crédito a Statistics Iceland (<https://statice.is/publications/open-data-access>). Las copias de `fpp2` y Rdatasets se distribuyen con licencia GPL-3 |
| Frecuencia | mensual |
| Periodo | 2000-01 a 2013-08 (164 observaciones) |
| Columna de fecha | `fecha` (primer día del mes, formato `AAAA-MM-DD`) |
| Columna que se pronostica | `uso_debito` (millones de ISK) |

## Cómo se construyó el CSV

El archivo original de Rdatasets tiene las columnas `rownames`, `time` (año
decimal: 2000, 2000.083, …) y `value`. Se convirtió `time` a la fecha del
primer día de cada mes, empezando en enero de 2000, y `value` se renombró
`uso_debito`. No se cambió ningún valor.

## Huecos y datos atípicos

- **Huecos:** ninguno; los 164 meses tienen dato. `preparar` en
  `miniproyecto.py` de todas formas interpola linealmente cualquier mes vacío.
- **Atípicos:** el guion marca 10 meses cuyo residuo de la STL robusta supera
  3 desviaciones robustas (3 × 1.4826 × MAD), concentrados en 2008, el año de
  la crisis bancaria islandesa. Se conservan sin cambios porque son meses
  reales, no errores de captura. La lista queda en `resultados/atipicos.csv`.

## Escala

Los valores van de 7.2 a 26.7, una escala cómoda para estimar los modelos,
así que no se reescalaron.
