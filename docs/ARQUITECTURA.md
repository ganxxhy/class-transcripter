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

Esta es una migración incremental, no una arquitectura hexagonal completa. La configuración y el estado del agente siguen usando archivos locales. No se incorpora SQLite, sincronización ni una nueva interfaz gráfica. El almacén JSON usa un bloqueo de archivo entre procesos para serializar las transacciones de clases y destacados. No coordina versiones antiguas del agente que no utilicen este bloqueo, ni garantiza coordinación en sistemas de archivos remotos.

## Domain and composition

`domain/models.py` defines typed persisted records; `domain/ports.py` defines contracts. `infrastructure/audio.py` implements audio input, `infrastructure/repository.py` exposes the JSON adapter, and `bootstrap.py` wires the desktop and MCP entry points. Legacy names remain available for compatibility. The recording loop lives in `application/recording.py`.

## Application boundary

`application/classes.py` and `application/summaries.py` contain use cases with injected dependencies. `infrastructure/status.py` reads agent and panel state. Legacy `nucleo` facades preserve the existing public API. Import-boundary tests prevent domain and application packages from importing concrete adapters. Recording orchestration lives in `application/recording.py`, provider and Whisper implementations in `infrastructure/providers.py` and `infrastructure/whisper.py`. Recording output files are handled by `infrastructure/recording_files.py`. Legacy modules retain compatibility exports. The JSON repository delegates to `infrastructure/json_store.py`; persisted keys and public legacy method names are unchanged.

## Final audit hardening

Capture owns the transcription end marker. Storage errors are logged and incomplete classes are marked as errors. Class IDs are allocated under the storage lock. Local summary jobs claim the generating state atomically; interrupted jobs require resetting that state before retrying. External MCP summary writers still use the legacy protocol. Regression tests cover these changes. Existing Spanish identifiers and wire keys remain for compatibility.
