# Corrección de fechas getdatosdespachos · versión 1.8.1

La versión 1.8 solo admitía fechas ISO o valores de fecha ya nativos. Se reprodujo el mensaje `FechaFactura debe ser una fecha ISO YYYY-MM-DD válida` con `05/01/2026 0:00:00` y con un objeto DateTime serializado por PHP. No se ha consultado el endpoint real; la reproducción es local con esos formatos.

## Formatos admitidos por el conector GET

| Entrada | Resultado en zona America/Guayaquil |
| --- | --- |
| `2026-01-05` | `2026-01-05` |
| `2026-01-05 00:00:00.0000000` | `2026-01-05` |
| `05/01/2026` | `2026-01-05` |
| `05/01/2026 0:00:00` | `2026-01-05` |
| `5/1/2026 09:13:24` | `2026-01-05` |
| `05-01-2026 09:13:24.1234567` | `2026-01-05` |
| `2026-01-05T02:00:00Z` | `2026-01-04`, al convertir UTC a Ecuador |
| `null`, `false`, texto vacío o solo espacios | Fecha ausente; no se inventa una fecha |

También se admite un objeto JSON como el siguiente:

```json
{
  "date": "2026-01-05 00:00:00.000000",
  "timezone_type": 3,
  "timezone": "America/Guayaquil"
}
```

Se usa el valor explícito `date`. La zona puede ser un nombre válido o un desplazamiento como `-05:00`; si falta, el timestamp sin zona se considera local. Un timestamp con zona explícita conserva esa zona y se convierte a la de operación. Una fecha sin hora se conserva como fecha de calendario.

Se aplica a **FechaFactura, UltimoDespacho y fecha_corte/cutoff_date**. Los nombres en minúsculas, como `fechafactura` y `ultimodespacho`, siguen siendo reconocidos. La API puede continuar entregando los campos con los mismos nombres.

El orden regional es siempre **día/mes/año**. `05/01/2026` es 5 de enero, no 1 de mayo. Fechas imposibles como `31/02/2026`, horas inválidas y objetos sin campo date se rechazan. El error identifica el campo y la línea del JSON, sin imprimir la respuesta completa.

Los datos se convierten a ISO antes de agrupar las facturas y calcular la huella. Cambiar solo la representación de una fecha válida no genera otro corte para el mismo contenido y fecha de extracción. El mecanismo vigente de empresa + TipoFactura + NumeroFactura, ciudades automáticas y cron de dos horas se conserva.

## Aplicación de la corrección

1. Reemplazar la carpeta `transcash_dispatch_analysis` por la del ZIP 1.8.1.
2. Reiniciar Odoo y actualizar **Transcash · Análisis de despachos** desde Aplicaciones.
3. Ejecutar **Sincronizar API → Sincronizar ahora**. El error de conversión sucede antes de crear la nueva importación, por lo que normalmente basta con repetir la consulta tras actualizar.

No se necesita volver a cargar el Excel ni modificar las credenciales. Se conserva el corte anterior mientras la nueva carga se valida y termina. La recepción alternativa por XML-RPC conserva su contrato ISO; la ampliación de formatos se aplica al conector GET.

Validación local: 203 pruebas autónomas aprobadas, incluyendo la respuesta en minúsculas con fecha regional, formatos SQL/PHP y equivalencia de huellas. Pruebas nativas incluidas para ejecutar en la base de prueba Odoo; no se afirma una instalación ni sincronización remota.
