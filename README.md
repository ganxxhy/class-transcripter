# Agente de clases

Aplicación de escritorio para Windows que graba tus clases, las transcribe en tu propio ordenador (Whisper) y genera un resumen por asignatura: primero la clase entera en orden y por temas, y aparte los exámenes, trabajos y fechas importantes.

## Descargar

Ve a [Releases](../../releases), descarga `AgenteClases-…-instalador.exe` y ábrelo. Funciona en Windows 10 y 11 de 64 bits, no pide permisos de administrador y no necesitas instalar nada más.

La primera vez que abras la app, un asistente te ayuda a:

1. Poner tu nombre y aceptar el aviso de permiso para grabar.
2. Añadir tus asignaturas y tu horario (a mano o leyendo una captura con Claude).
3. Elegir el micrófono y probarlo.
4. Decidir cómo hacer los resúmenes: con tu cuenta de Claude Pro o Max (recomendado) o con una clave de API de Claude o Gemini.

Después el agente se queda junto al reloj y graba solo según tu horario.

## Cómo funciona

- **Transcripción en local:** el audio nunca sale de tu ordenador.
- **Resúmenes con tu cuenta de Claude:** publicas tu propio panel "Mis clases" en Claude ([instrucciones](hub/PUBLICAR.md)) y los resúmenes se hacen con tu suscripción. Ves tus clases desde el móvil o cualquier ordenador.
- **Resúmenes con clave de API (opcional):** si pones una clave de Claude o Gemini, el resumen se hace solo en tu ordenador al acabar la clase.
- Tus datos se guardan en `Documentos\AgenteClases`.

## Aviso legal

Antes de grabar una clase, asegúrate de tener permiso del profesorado y de cumplir las normas de tu universidad. Tú eres responsable del uso que hagas de las grabaciones.

## Para desarrollar

- `agente/`: la aplicación (grabación, transcripción con faster-whisper, resúmenes, asistente y servidor MCP para el panel). `config.ejemplo.json` es una plantilla; tu `config.json` real nunca se sube.
- `hub/`: el panel "Mis clases".
- `packaging/`: icono, imágenes y script del instalador (Inno Setup).
- `CAMBIOS.md`: novedades de cada versión (salen en Releases y en el aviso de actualización).
- `tests/`: pruebas (`python tests/test_horario.py`).

Desde el código: `pip install -r agente/requirements.txt` y `python agente/app.py`.

El instalador lo compila GitHub Actions en cada cambio (pestaña Actions). Para publicar una versión: añade su sección `## X.Y.Z` en `CAMBIOS.md`, crea la etiqueta `vX.Y.Z` y se sube sola a Releases. Las apps ya instaladas avisarán de la actualización.
