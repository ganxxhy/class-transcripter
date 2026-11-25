# Cambios

Cada versión publicada en Releases toma sus notas de aquí (la sección `## X.Y.Z`). La app las enseña al avisar de una actualización y después de actualizar.

Si cambia el panel `hub/mis-clases.html`, sube su `VERSION_PANEL` y cuenta lo nuevo en una sección `### Panel`: los paneles con una versión más vieja avisan y lo enseñan.

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
