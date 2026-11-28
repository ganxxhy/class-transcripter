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
- Si no tienes la app de escritorio de Claude (en Linux no hay una versión oficial confirmada), puedes hacer los resúmenes con tu cuenta de ChatGPT o con una clave de API (paso «Resúmenes» del asistente). El panel «Mis clases» se conecta con las versiones de la comunidad que usen `~/.config/Claude`.

La primera vez que abras la app, un asistente te ayuda a:

1. Poner tu nombre y aceptar el aviso de permiso para grabar.
2. Añadir tus asignaturas y tu horario (a mano o leyendo una captura con Claude).
3. Elegir el micrófono y probarlo.
4. Decidir cómo hacer los resúmenes: con tu cuenta de Claude Pro o Max, con tu cuenta de ChatGPT Plus o Pro (si es compatible con el uso del plan), con una clave de API o con un modelo compatible con OpenAI (Ollama, LM Studio, Cloudflare…).

Después Estudio se queda junto al reloj y graba solo según tu horario.

## Cómo funciona

- **Transcripción en local:** el audio nunca sale de tu ordenador.
- **Resúmenes con tu cuenta de Claude:** publicas tu propio panel "Mis clases" en Claude ([instrucciones](hub/PUBLICAR.md)) y los resúmenes se hacen con tu suscripción. Ves tus clases desde el móvil o cualquier ordenador.
- **Resúmenes con tu cuenta de ChatGPT:** conecta tu cuenta en el asistente y elige un modelo. El texto se procesa con tu plan de ChatGPT al terminar la clase; los apuntes se guardan en Estudio y se consultan en el visor local «Mis clases». No requiere una clave API.
- **Resúmenes con clave de API (opcional):** si pones una clave de Claude o Gemini, o configuras un modelo compatible con OpenAI, el resumen se hace solo en tu ordenador al acabar la clase.
- **Privacidad:** el audio y la transcripción se quedan siempre en tu ordenador. Con un servicio externo (Claude, Gemini, OpenAI, Cloudflare…) el texto de la transcripción sí se envía a ese servicio para resumirlo; con un modelo local (Ollama, LM Studio…) no sale nada. Enviar el contenido de las clases a un tercero también puede estar sujeto a las normas de tu universidad.
- Tus datos se guardan en `Documentos\AgenteClases` (Windows) o en `~/.local/share/estudio`, con la configuración en `~/.config/estudio` (Linux).

## Optional Intel and AMD GPU transcription

Estudio can use `whisper.cpp` with Vulkan on Windows and Linux. The worker looks for an integrated or discrete Intel or AMD GPU with a Vulkan 1.2 or newer driver. Actual support and speed depend on the GPU, driver and available memory. Verified so far only on an Intel integrated GPU (Lunar Lake, Mesa driver, Linux); AMD and Windows have not been tested on real hardware, so treat them as experimental and report results. The standard installer and AppImage use the existing `faster-whisper` CPU and NVIDIA CUDA runtime. Vulkan requires the separately built worker, a GGML transcription model and a small voice activity model.

1. Install a Vulkan driver for your GPU. To build the worker, install CMake, a C++ toolchain and the Vulkan headers and shader compiler (`glslc`). On Windows, use a Visual Studio C++ toolchain and the Vulkan SDK.
2. From the repository root, build the optional worker.

   ```sh
   cmake -S packaging/vulkan -B build/vulkan -DCMAKE_BUILD_TYPE=Release
   cmake --build build/vulkan --config Release --parallel
   ```

3. Put `studio-whisper-vulkan` (Linux) or `studio-whisper-vulkan.exe` (Windows, typically under `build/vulkan/Release`) in the `datos/vulkan` subdirectory of Estudio's data root. The default is `~/.local/share/estudio/datos/vulkan` for the AppImage and `Documents\AgenteClases\datos\vulkan` on Windows. When running from source it is `agente/datos/vulkan`. If you set `AGENTE_CLASES_DATOS`, use its `datos/vulkan` subdirectory.
4. Download the two GGML models into that directory. The simplest way is to let Estudio do it (it verifies size and SHA-256 of what it downloads, and keeps files already present if their size matches): `python agente/app.py --descargar-modelo-vulkan` from source, or run the installed executable with the same argument. The manual alternative is:

   ```sh
   cd <datos/vulkan directory>
   curl -fLO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin   # 1624555275 bytes
   curl -fLO https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin      # 885098 bytes
   sha256sum ggml-*.bin
   ```

   Expected SHA-256: `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69` (large-v3-turbo) and `2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987` (Silero). The worker itself is not downloaded; build it as in step 2. If you explicitly set `modelo_whisper` to another model, install the matching `ggml-<model>.bin` there by hand. If a file is missing, the log names it and the folder where Estudio looks for it, then falls back to CPU.
5. Restart Estudio. In the `ajustes` object of `config.json`, `"dispositivo": "auto"` keeps CUDA first, then tries the optional Vulkan worker, then uses CPU. Set `"dispositivo": "vulkan"` to try Vulkan first with CPU fallback, or use `"cpu"` or `"cuda"` to select an existing backend directly. The same choice is available in Ajustes → «Dispositivo de transcripción»; it applies the next time Estudio starts.

The transcription log shows the active model and device, any fallback reason, and a real-time speed multiplier per chunk. To compare Vulkan with CPU, transcribe the same sample with `modelo_whisper` set to `large-v3-turbo` for both runs and compare the speed after model startup. A value above `1.0×` means the chunk was processed faster than it was recorded.

Vulkan frees the processor but is not always faster than it. On an Intel Core Ultra 7 258V (Lunar Lake) with its integrated GPU, `large-v3-turbo` measured about 3.5× (clear TV audio) to 5× (faint audio) on Vulkan against about 6.4× on CPU on the same samples; the GPU encoder takes roughly 4 s per 30 s window. Measure on your own hardware and choose "Solo CPU" if CPU is faster for you.

## Resúmenes con tu cuenta de ChatGPT

Esta opción es independiente de `openai`, el proveedor de API. Utiliza el flujo oficial [Sign in with ChatGPT para aplicaciones de código abierto](https://developers.openai.com/siwc/token-sharing-open-source), actualmente en fase de disponibilidad limitada por cuenta, modelo y políticas de OpenAI.

1. Abre Estudio y, en el paso «¿Cómo quieres los resúmenes?» (o Ajustes → Configurar proveedor de resúmenes / cuenta de ChatGPT), selecciona «Con mi cuenta de ChatGPT».
2. Pulsa «Continuar con ChatGPT». Inicia sesión en tu navegador habitual, autoriza Estudio y concede permiso para utilizar tu plan.
3. Vuelve a Estudio, selecciona un modelo del catálogo de tu cuenta y guarda los ajustes.
4. Al terminar la siguiente clase, Estudio transcribe el audio con Whisper y genera automáticamente el resumen con ChatGPT. Abre «Mis clases» para consultar los apuntes y la transcripción por asignatura.

Puedes cambiar de cuenta, volver a autorizarla o desconectarla desde los ajustes. Las grabaciones y los apuntes no se borran al cambiar de proveedor. El visor de ChatGPT es local: no crea conversaciones en tu historial de ChatGPT ni publica un artefacto de Claude. La sincronización móvil del panel de Claude sigue siendo exclusiva de ese panel. El visor local reutiliza la misma interfaz web del panel original. «Asignaturas y horario» abre el calendario semanal; para modificarlo, entra en «Ajustes → Editar asignaturas y horario», sin volver a configurar la cuenta ni el micrófono.

Las peticiones utilizan los límites de tu plan de ChatGPT, no una clave de API ni la facturación del proveedor `openai`. Revisa [el uso de ChatGPT](https://chatgpt.com/settings/usage) y desactiva los créditos adicionales si no quieres utilizarlos. Cuando se alcance un límite, Estudio pausa los resúmenes de esa cuenta; consulta los ajustes de uso y pulsa «Reanudar resúmenes» cuando vuelva a estar disponible. No se cambia automáticamente a un proveedor de pago.

El audio no se envía a OpenAI; solo se transmite el texto necesario para resumir. Los tokens OAuth se guardan fuera de los datos de las clases, protegidos con DPAPI en Windows y permisos de usuario en Linux. El flujo no lee cookies ni credenciales de tu navegador. Consulta [la documentación técnica](docs/CHATGPT.md) para conocer los límites y la validación.

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
- `tests/`: pruebas (`python tests/test_horario.py`, `python tests/test_linux.py` y `python tests/test_resumen.py` y `python tests/test_chatgpt.py`).

Desde el código: `pip install -r agente/requirements.txt` y `python agente/app.py`. En Linux, `bash packaging/linux/install.sh` crea el entorno, el lanzador del menú y descarga el modelo (necesita Python 3.10–3.13 con tkinter, PortAudio, y PyGObject con WebKitGTK: `python3-gi` y `gir1.2-webkit2-4.1` en Debian/Ubuntu, `python3-gobject` y `webkit2gtk4.1` en Fedora, `python-gobject` y `webkit2gtk-4.1` en Arch).

El instalador de Windows y el AppImage los compila GitHub Actions en cada cambio (pestaña Actions). Para publicar una versión: añade su sección `## X.Y.Z` en `CAMBIOS.md`, crea la etiqueta `vX.Y.Z` y se sube sola a Releases. Las apps ya instaladas avisarán de la actualización.
