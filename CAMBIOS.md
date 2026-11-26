# Cambios

Cada versión publicada en Releases toma sus notas de aquí (la sección `## X.Y.Z`). La app las enseña al avisar de una actualización y después de actualizar.

Si cambia el panel `hub/mis-clases.html`, sube su `VERSION_PANEL` y cuenta lo nuevo en una sección `### Panel`: los paneles con una versión más vieja avisan y lo enseñan.

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
