# v2.43 - Corrección de instalación de borrado de evidencias

Se corrige `views/evidence_delete_v242.xml` / `tc_pwa_evidence_delete_styles_v242`, que heredaba `logistica_transcash.mobile_head` con un XPath `//head` no presente en el template de Odoo 18. El CSS se inserta después de `//link[@rel='manifest']`, nodo existente en la plantilla principal de Logística Transcash v5.32.

No se modifica la lógica de eliminación de evidencias v2.42 ni las reglas de seguridad, estados, liquidaciones, rutas o embarques.

Instalar reemplazando solo el addon `transcash_guias_api`, reiniciar Odoo y actualizar el addon. Ejecutar primero en respaldo/staging.
