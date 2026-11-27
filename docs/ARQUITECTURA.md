# Arquitectura modular de Estudio

El núcleo define contratos estructurales mediante `typing.Protocol` en `agente/nucleo/interfaces.py`.

- `ITranscriber`: carga, transcripción y adaptación de carga. El motor usa faster-whisper por defecto.
- `IAIProvider`: generación de resúmenes; los adaptadores Claude, Gemini y OpenAI están en `proveedores.py`.
- `IClassRepository`: operaciones de clases. El módulo `almacen.py` sigue siendo la implementación JSON por defecto.
- `ServicioClases`: casos de uso de consulta, paginación, estado, resúmenes, movimiento y borrado. MCP delega en este servicio; el futuro Hub podrá reutilizarlo.

No cambia el formato de datos, la ubicación de archivos ni el protocolo MCP. El motor y el servicio de resumen admiten dependencias inyectadas. Los adaptadores conservan las peticiones y el tratamiento de errores anteriores.

## Validación

Ejecutar desde la raíz `python tests/test_interfaces.py` y `python tests/test_resumen.py`. El workflow ejecuta ambas pruebas en Windows y Linux, además de las pruebas existentes y las comprobaciones de los paquetes.

## Límites

Esta es una migración incremental, no una arquitectura hexagonal completa. La configuración y el estado del agente siguen usando archivos locales. No se incorpora SQLite, sincronización ni una nueva interfaz gráfica. Antes de introducir múltiples procesos escritores se debe resolver la coordinación de escrituras: el bloqueo del almacén JSON es local al proceso.
