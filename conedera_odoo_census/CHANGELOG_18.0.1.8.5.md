# Changelog 18.0.1.8.5

- Mantiene la arquitectura funcional de 18.0.1.8.4.
- Reafirma el inicializador raíz canónico: `from . import models`.
- Añade un bootstrap de compatibilidad `crm_team.py` para instalaciones antiguas cuyo `__init__.py` fue aplanado accidentalmente.
- Añade validación explícita de estructura de paquete e imports relativos.
- No introduce cambios destructivos de base de datos.
