# Cambios

Cada versión publicada en Releases toma sus notas de aquí (la sección `## X.Y.Z`). La app las enseña al avisar de una actualización y después de actualizar.

Si cambia el panel `hub/mis-clases.html`, sube su `VERSION_PANEL` y cuenta lo nuevo en una sección `### Panel`: los paneles con una versión más vieja avisan y lo enseñan.

## Sin publicar

### Web
- Mejora del contraste del texto sobre el cielo dinámico durante el amanecer, el atardecer y la noche.

### Transcripción
- Transcripción opcional con Vulkan (whisper.cpp) en GPU Intel y AMD, con vuelta automática a CPU. Los modelos se bajan con `--descargar-modelo-vulkan`; si falta algún archivo, el registro dice cuál y en qué carpeta. Ajustes permite elegir el dispositivo de transcripción (automático, CPU, CUDA, OpenVINO o Vulkan).
- Transcripción opcional con OpenVINO en GPU Intel (paquete `openvino-genai` y modelo `large-v3` int8 que se baja con `--descargar-modelo-openvino`). En automático va antes que Vulkan y vuelve a CPU si falla.

## 1.3.0

### Panel
- Estados de cola y reintento de resúmenes locales.
- Recuperación de resúmenes interrumpidos y coordinación de trabajos locales entre Estudio y Hub mediante bloqueos liberados al cerrar el proceso.

### Estudio Hub
- Aplicación local de consulta y gestión de clases, tareas y calendario, con acceso directo e icono propios en Windows y Linux.
- El Hub comparte SQLite y la configuración de Estudio, sin depender de Claude ni del proveedor de resúmenes para consultar los datos.
- El artefacto de Claude y MCP siguen disponibles como integración opcional.

### Integración de ChatGPT
- Coordinación de peticiones y cierre de sesión entre procesos locales.
- Inicio de sesión con ChatGPT y selección de cuenta y modelo, sujeto a disponibilidad del plan.
- Visor local de clases y horario conectado a SQLite.


- Migración SQLite: detección de cambios en los JSON durante la importación y conservación separada de archivos antiguos que reaparezcan después de activar SQLite.

- Actualizador de Windows: aislamiento del entorno de PyInstaller al lanzar el instalador, registro de instalación y detección de fallos inmediatos con instrucciones de instalación manual.

### Novedades
- SQLite pasa a ser el almacenamiento obligatorio de clases y transcripciones. La primera apertura migra y verifica los datos anteriores; los JSON se conservan en `datos/clases-json-backup`.
- Si falla la migración, Estudio no vuelve silenciosamente al almacenamiento anterior.

### Compatibilidad y validación
- El artefacto opcional de Claude requiere una versión compatible con SQLite y acceso mediante MCP. El Hub local no requiere Claude.
- Generación con ChatGPT y recuperación de resúmenes interrumpidos verificadas manualmente en Windows. Las pruebas automatizadas de Windows y Linux han pasado; quedan pendientes las pruebas manuales de migración en Linux y del actualizador en condiciones reales.

### Arreglos
- Mejoras en el cierre de las grabaciones para procesar los fragmentos pendientes antes de finalizar la transcripción.
- Mejor gestión de errores de transcripción y almacenamiento, evitando generar automáticamente resúmenes locales de clases detectadas como incompletas.
- Se evitan colisiones de identificadores al crear clases en el mismo segundo.
- Bloqueo de escrituras de clases entre procesos y protección frente a generaciones simultáneas de resúmenes locales.

### Cambios internos
- Nueva arquitectura modular que separa dominio, aplicación e infraestructura, conservando los formatos de datos y las interfaces del Hub y MCP existentes.
- Separación de los adaptadores de audio, transcripción, almacenamiento y proveedores de IA para facilitar futuras mejoras y la migración a SQLite.
- Nuevas pruebas de regresión y documentación de arquitectura.
- Las pull requests cancelan automáticamente sus compilaciones obsoletas al recibir nuevos commits, sin afectar a las releases ni a las ejecuciones manuales.
- Se evitan las compilaciones redundantes tras fusionar cambios en `main`: solo se ejecutan las pruebas automatizadas.
- Las pull requests y las releases mantienen las compilaciones completas de Windows y Linux, sin modificar el sistema de publicación y recuperación.

## 1.2.2

### Novedades
- El paquete de Linux reduce su tamaño aproximadamente un 65 %.
- Las ventanas del asistente y de actualizaciones usan WebKitGTK del sistema en lugar de Qt WebEngine.
- Nuevo modo `--comprobar` para verificar las dependencias del AppImage.
- Si falta WebKitGTK, se muestran instrucciones de instalación; los avisos de actualización pueden abrir la página de la release en el navegador.

### Arreglos
- El AppImage utiliza las bibliotecas libstdc++ y libgcc del sistema para mejorar la compatibilidad con distribuciones modernas.
- Optimización de las dependencias incluidas en el AppImage, conservando las necesarias para el audio.
- Corrección del backend del icono de la bandeja del sistema.
- Mejoras de compatibilidad con Debian, Ubuntu, Fedora y Arch Linux.
- Nuevas comprobaciones automatizadas de las dependencias del AppImage.

Gracias a @KoyFC por las contribuciones y las pruebas de compatibilidad.

## 1.2.1

### Novedades
- Estudio busca actualizaciones mediante un manifiesto público, sin depender de la cuota de la API REST de GitHub cuando la release incluye el manifiesto.
- Se conserva la consulta anterior como respaldo para versiones antiguas.
- Las consultas se guardan temporalmente en memoria para evitar peticiones repetidas.
- Los instaladores del nuevo sistema se comprueban mediante SHA-256 y tamaño antes de instalarse.
- Los mensajes de error explican cuándo GitHub limita las consultas y se guarda un registro de diagnóstico.

### Arreglos
- Descarga más robusta y verificada de AppImageTool durante la compilación de Linux.
- Publicación automática de los instaladores de Windows y Linux, sus checksums y el manifiesto de actualización.
- Posibilidad de recuperar releases existentes sin cambiar su etiqueta.
- Nuevas pruebas automatizadas del actualizador.

## 1.2.0

### Novedades
- Estudio funciona en **Linux**: AppImage de 64 bits, con lanzador en el menú y arranque con la sesión.
- En Linux los datos van en `~/.local/share/estudio` y la configuración en `~/.config/estudio`.
- El micrófono por defecto es PipeWire, después PulseAudio y solo al final ALSA directo.
- La app se actualiza sola también en Linux.
- Resúmenes con cualquier modelo compatible con OpenAI: ChatGPT, Ollama, LM Studio, llama.cpp o Gemma 4 en Cloudflare Workers AI. Se configura en el asistente, con ayuda para cada servicio.
- Con modelos en tu ordenador no hace falta clave.
- Si el modelo devuelve el resumen incompleto, se le pide otra vez; si sigue mal, verás el motivo.
- El asistente avisa de que, con un servicio externo, el texto de las clases sale del ordenador (el audio no).
- Al leer el horario de una captura puedes copiar el mensaje y pegarlo en la IA que prefieras, no solo en Claude.

### Panel
- Encuentra la configuración aunque no esté junto a los datos (Linux).

## 1.1.0

### Novedades
- La app pasa a llamarse **Estudio** y estrena el diseño "Jornada": un cielo que sigue la hora del día, tarjetas blancas y el día dibujado como un arco con el sol.
- Ventana de grabación, asistente de primera vez, aviso de actualización e instalador con el diseño nuevo.
- Web nueva: https://ganxxhy.github.io/class-transcripter/
- Tus clases, ajustes y la carpeta `Documentos\AgenteClases` siguen donde estaban.

### Panel
- Diseño nuevo con secciones: Hoy, Asignaturas, Tareas, Calendario y Estadísticas.
- Hoy enseña tu día como un arco con el sol en la hora actual, las clases de hoy y lo pendiente.
- Tareas reúne los exámenes, entregas y avisos que se dicen en clase; márcalos al terminar.
- Calendario con tu horario de la semana y las fechas que han salido en clase.
- Estadísticas con las horas de clase grabadas por día y por asignatura.
- Los resúmenes se hacen igual que antes.

## 1.0.0

### Novedades
- Instalador para Windows que no pide permisos de administrador ni necesita instalar nada más.
- Asistente de primera vez: tus asignaturas y tu horario (también leyéndolo de una captura con Claude), el micrófono con medidor de nivel y cómo quieres los resúmenes.
- Resúmenes con tu cuenta de Claude desde el panel "Mis clases", o con una clave de API de Claude o de Gemini.
- El panel "Mis clases" se puede instalar como app de escritorio nada más crearlo.
- La app avisa cuando hay una versión nueva, enseña qué ha cambiado y se actualiza sola si quieres.
- Si ya está instalado, el instalador solo actualiza.
- El panel "Mis clases" avisa cuando hay una versión nueva suya y se actualiza con un clic, sin perder tus clases.

### Arreglos
- El panel encuentra la carpeta del agente aunque Documentos esté en OneDrive.
