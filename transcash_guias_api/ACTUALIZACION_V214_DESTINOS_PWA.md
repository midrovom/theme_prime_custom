# Transcash Guías API v2.14 — destinos homologados en PWA

## Hallazgo

El nombre mostrado en `transcash.guia.destino_id.name` **no es** el código del catálogo.
La hoja de ruta selecciona `transcash.hoja.ruta.destino_id`, que puede ser un
registro diferente. v2.13 ya ignoraba espacios/guiones entre códigos iguales;
por ello, si el selector sigue indicando «Destino diferente», debe comprobarse
el código real de **ambas** fichas, no solo su nombre visible.

## Cambio

1. Se normaliza el código con Unicode NFKD, eliminando espacios (incluidos
   no separables), puntos, guiones, guiones bajos y caracteres invisibles.
   `NAJ`, ` -NAJ`, `N A J`, y `NAJ\u00a0` equivalen a `NAJ`.
2. Si dos fichas tienen códigos normalizados iguales y pertenecen a la misma
   compañía, la guía resulta compatible sin crear otra ficha ni reimportarla.
3. Si los códigos son realmente diferentes, el jefe de Logística dispone de:
   **Logística Transcash → Equivalencias de destinos ERP**. Puede introducir el
   **código del catálogo relacionado a la guía** y el destino verdadero de
   la ruta. La equivalencia queda controlada por compañía y código único.
4. La PWA muestra en el diagnóstico por número de guía los dos códigos reales,
   sus versiones normalizadas y los códigos aceptados por la ruta.
5. Solo se normalizan relaciones de guías al guardar una selección que supere
   también el filtro de chofer, transportista, compañía y disponibilidad.

## Para el caso de la guía 32799 / TR-53965

- Abra la ruta del chofer y busque `32799` en **Agregar guías**.
- Lea `Normalizado guía`, `Código ERP guía`, `Código ruta` y `Aceptados`.
- Si guía y ruta son `NAJ` tras normalizar, no requiere ninguna equivalencia.
- Si son diferentes, y tras validar documentalmente que son el **mismo** destino,
  configure una equivalencia: `Código recibido del ERP` = código del catálogo
  de la guía; `Destino de Logística` = ficha seleccionada en la hoja de ruta.
  Si el código de la guía proviene de un catálogo antiguo, homologar el código
  **de ese catálogo** (no adivinar por el nombre `NAJ`).
- Recargue la PWA. No es necesario volver a sincronizar la API ni cambiar el
  estado de la guía, y nunca se reasignan guías de otros conductores.

## Seguridad

Las equivalencias solo las pueden editar el jefe de Logística y el
administrador técnico. No hay coincidencia difusa por nombres de ciudad; no
se mezclan destinos de distintas compañías. Las guías que tengan códigos
contradictorios entre el maestro vinculado y el campo ERP siguen bloqueadas.

## Instalación

Actualizar únicamente `transcash_guias_api` desde v2.13 a v2.14.
Mantener `logistica_transcash` sin modificar.
Antes de actualizar, respaldar la base de datos y los addons.
