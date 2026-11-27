# Estudio

(Antes "Agente de clases".) Aplicación de escritorio para Windows y Linux que graba tus clases, las transcribe en tu propio ordenador (Whisper) y genera un resumen por asignatura: primero la clase entera en orden y por temas, y aparte los exámenes, trabajos y fechas importantes.

**Web:** https://ganxxhy.github.io/class-transcripter/

## Descargar

Ve a [Releases](../../releases), descarga `Estudio-…-instalador.exe` y ábrelo. Funciona en Windows 10 y 11 de 64 bits, no pide permisos de administrador y no necesitas instalar nada más.

### Linux

Descarga `Estudio-…-x86_64.AppImage`, hazlo ejecutable (`chmod +x Estudio-*.AppImage`) y ábrelo. Hace falta una distribución de 64 bits con PipeWire o PulseAudio (la de casi cualquier escritorio actual); la app usa PipeWire, luego PulseAudio y solo al final ALSA directo.

- Al acabar el asistente crea su lanzador en el menú y arranca con tu sesión. Si mueves el AppImage, se corrige solo al abrirlo.
- Hace falta WebKitGTK (casi todos los escritorios ya lo tienen). Si falta, Estudio te dice qué instalar: `gir1.2-webkit2-4.1` (Debian/Ubuntu), `webkit2gtk4.1` (Fedora), `webkit2gtk-4.1` y `gobject-introspection-runtime` (Arch).
- En GNOME hace falta la extensión AppIndicator para ver el icono junto al reloj; si no, la ventana se minimiza.
- Si no tienes la app de escritorio de Claude (en Linux no hay una versión oficial confirmada), lo más sencillo es hacer los resúmenes con una clave de API de Claude o Gemini (paso «Resúmenes» del asistente). El panel «Mis clases» se conecta con las versiones de la comunidad que usen `~/.config/Claude`.

La primera vez que abras la app, un asistente te ayuda a:

1. Poner tu nombre y aceptar el aviso de permiso para grabar.
2. Añadir tus asignaturas y tu horario (a mano o leyendo una captura con Claude).
3. Elegir el micrófono y probarlo.
4. Decidir cómo hacer los resúmenes: con tu cuenta de Claude Pro o Max (recomendado) o con una clave de API de Claude o Gemini, o con cualquier modelo compatible con OpenAI (ChatGPT, Ollama, LM Studio, Cloudflare…).

Después Estudio se queda junto al reloj y graba solo según tu horario.

## Cómo funciona

- **Transcripción en local:** el audio nunca sale de tu ordenador.
- **Resúmenes con tu cuenta de Claude:** publicas tu propio panel "Mis clases" en Claude ([instrucciones](hub/PUBLICAR.md)) y los resúmenes se hacen con tu suscripción. Ves tus clases desde el móvil o cualquier ordenador.
- **Resúmenes con clave de API (opcional):** si pones una clave de Claude o Gemini, o configuras un modelo compatible con OpenAI, el resumen se hace solo en tu ordenador al acabar la clase.
- **Privacidad:** el audio y la transcripción se quedan siempre en tu ordenador. Con un servicio externo (Claude, Gemini, OpenAI, Cloudflare…) el texto de la transcripción sí se envía a ese servicio para resumirlo; con un modelo local (Ollama, LM Studio…) no sale nada. Enviar el contenido de las clases a un tercero también puede estar sujeto a las normas de tu universidad.
- Tus datos se guardan en `Documentos\AgenteClases` (Windows) o en `~/.local/share/estudio`, con la configuración en `~/.config/estudio` (Linux).

## Resúmenes con otros modelos

En el asistente (o en `config.json`, dentro de `ajustes`; en Linux está en `~/.config/estudio`) elige el proveedor `openai`: sirve cualquier servicio con endpoint `/chat/completions` al estilo de OpenAI.

| Servicio | `openai_base_url` | `modelo_openai` (ejemplo) | Clave |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | el que quieras | Sí |
| Ollama | `http://localhost:11434/v1` | el que hayas descargado | No |
| LM Studio | `http://localhost:1234/v1` | el que hayas cargado | No |
| llama.cpp | `http://localhost:8080/v1` | el que sirvas | No |
| Cloudflare Workers AI | `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1` | `@cf/google/gemma-4-26b-a4b-it` | Token con permisos Workers AI (Read y Edit) |

```json
"ajustes": {
  "proveedor": "openai",
  "openai_base_url": "http://localhost:11434/v1",
  "modelo_openai": "el-modelo-que-sea",
  "openai_api_key": ""
}
```

- La clave también puede ir en la variable de entorno `OPENAI_API_KEY`. Con modelos locales puede quedar vacía.
- Los modelos pequeños no siempre devuelven JSON válido: Estudio lo pide en las instrucciones, comprueba que estén todos los campos y, si no, pide la respuesta otra vez una vez. Si sigue mal, la clase queda con el error y se reintenta más tarde (la transcripción no se pierde).
- Los servidores locales suelen recortar el contexto sin avisar: sube `num_ctx` en Ollama o "Context Length" en LM Studio, porque una clase son muchos tokens.
- Cloudflare, cómo conseguir los datos (el panel puede cambiar de nombres):
  1. Crea una cuenta gratuita en [dash.cloudflare.com](https://dash.cloudflare.com).
  2. **ID de cuenta:** en *Workers & Pages* aparece como *Account ID*; también está en la dirección del panel (`dash.cloudflare.com/<ID>/…`). Sustituye `{ACCOUNT_ID}` en la dirección del servidor por ese ID.
  3. **Clave:** en [Mi perfil → API Tokens](https://dash.cloudflare.com/profile/api-tokens) pulsa *Create Token*, usa la plantilla *Workers AI* (o un token personalizado con los permisos de cuenta *Workers AI: Read* y *Edit*) y copia el token al crearlo: no se vuelve a mostrar. Ese token es la clave.
- Cloudflare: el plan gratuito da 10.000 neurons al día, que se reinician a las 00:00 UTC. Si se agotan, el mensaje de error muestra lo que responde el servicio.

## Aviso legal

Antes de grabar una clase, asegúrate de tener permiso del profesorado y de cumplir las normas de tu universidad. Tú eres responsable del uso que hagas de las grabaciones.

## Para desarrollar

- `agente/`: la aplicación (grabación, transcripción con faster-whisper, resúmenes, asistente y servidor MCP para el panel). `config.ejemplo.json` es una plantilla; tu `config.json` real nunca se sube.
- `hub/`: el panel "Mis clases".
- `docs/`: la web de la app (GitHub Pages), con la guía de diseño "Jornada" en `docs/DISENO.md`.
- `packaging/`: icono, imágenes y script del instalador (Inno Setup), y `linux/install.sh` para instalar desde el código en Linux.
- `CAMBIOS.md`: novedades de cada versión (salen en Releases y en el aviso de actualización).
- `tests/`: pruebas (`python tests/test_horario.py`, `python tests/test_linux.py` y `python tests/test_resumen.py`).

Desde el código: `pip install -r agente/requirements.txt` y `python agente/app.py`. En Linux, `bash packaging/linux/install.sh` crea el entorno, el lanzador del menú y descarga el modelo (necesita Python 3.10–3.13 con tkinter, PortAudio, y PyGObject con WebKitGTK: `python3-gi` y `gir1.2-webkit2-4.1` en Debian/Ubuntu, `python3-gobject` y `webkit2gtk4.1` en Fedora, `python-gobject` y `webkit2gtk-4.1` en Arch).

El instalador de Windows y el AppImage los compila GitHub Actions en cada cambio (pestaña Actions). Para publicar una versión: añade su sección `## X.Y.Z` en `CAMBIOS.md`, crea la etiqueta `vX.Y.Z` y se sube sola a Releases. Las apps ya instaladas avisarán de la actualización.
