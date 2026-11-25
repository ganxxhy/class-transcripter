# Publicar tu panel "Mis clases"

El panel "Mis clases" es un artefacto de Claude. Cada persona publica **su propia copia** en su cuenta (Claude Pro o Max): así los resúmenes se hacen con tu suscripción y tus clases solo las ves tú.

La forma fácil: en el asistente de Agente de clases pulsa **Crear mi panel en Claude**. Se abre Claude con la petición ya escrita.

## Instrucciones para Claude

Publica como artefacto el archivo [`mis-clases.html`](mis-clases.html) **tal cual**, sin cambiar el código, con el título "Mis clases" y estas capacidades:

| Capacidad | Para qué |
|---|---|
| `db` | Guardar las clases, sus resúmenes y lo marcado como hecho, para verlo desde cualquier sitio. |
| `sample` | Hacer los resúmenes con la cuenta de Claude de quien lo usa. |
| `mcp`, con el servidor local `agente_clases` | Leer las clases del ordenador cuando el panel se abre en la app de escritorio de Claude. |
| `desktop` | Plan B: si el servidor local no responde, el panel se instala como app y lee la carpeta `Documentos\AgenteClases`. |

Cuando esté publicado, recomienda abrirlo en la app de escritorio de Claude: el panel ofrece instalarse como app de escritorio con un clic. Da también el enlace del artefacto: la persona lo pega en el asistente (paso "Resúmenes") para que el botón "Abrir Mis clases" lleve a su panel.

## Si algo no funciona

- **"Sin sincronizar"**: abre el panel dentro de la app de escritorio de Claude (no en el navegador) y comprueba que la app se reinició después de instalar Agente de clases.
- **No encuentra el agente**: los datos están en `Documentos\AgenteClases` (o `OneDrive\Documentos\AgenteClases`).
