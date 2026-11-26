> Guía del diseño "Jornada" que usan la web (`docs/`), el panel (`hub/mis-clases.html`), el asistente y la ventana de la app. El nombre de la app es **Estudio** y los enlaces reales están en la web.

# Estudio · Guía de diseño ("Jornada")

Esta guía describe el sistema visual de la web de presentación (`index.html`) y de la app (`app.html`). Úsala para construir bloques nuevos que parezcan parte del mismo producto.

## 1. Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | Web de presentación del repositorio (landing). |
| `app.html` | Prototipo navegable de la app ("hub"): Hoy, Asignaturas, Tareas, Calendario, Estadísticas. |
| `sky.js` | Motor del cielo, compartido por las dos páginas. Debe ir junto a ellas. |
| `DESIGN.md` | Esta guía. |

Las páginas son HTML, CSS y JS sin dependencias ni compilación. Solo cargan tipografías de Google Fonts.

### Antes de desplegar
- **Enlaces de GitHub:** todos apuntan a `https://github.com`. Cámbialos por la URL del repositorio, y el botón de descarga de Windows por la página de la última versión (`/releases/latest`).
- **Ejemplo de `git clone`:** sustituye `TU-USUARIO`.
- **Pendiente de decidir:** el pie dice "Licencia por definir"; actualízalo cuando exista una licencia. El nombre "estudio" es provisional.
- **Contenido:** todos los datos de la app (asignaturas, tareas, resúmenes) son de ejemplo.
- **GitHub Pages:** sube los tres archivos a la raíz de la rama publicada (o a `/docs`). No hace falta configurar nada más.

## 2. Idea del diseño

El día de estudio se dibuja como el recorrido del sol. Tres cosas lo sostienen:

1. **El cielo vivo de fondo.** Cambia con la hora y la posición del sol del visitante: azul de día, naranja al atardecer, azul oscuro con estrellas de noche.
2. **El arco del día.** Una media elipse de 8:00 a 24:00. Cada clase es un tramo de su color y el sol marca la hora actual.
3. **Tarjetas blancas tranquilas** encima del cielo. Toda la información vive en ellas.

El cielo es el ambiente; el contenido nunca depende de él para leerse.

## 3. Color

### Base
| Token | Valor | Uso |
|---|---|---|
| `--ink` | `#0D2340` | Texto principal, botón primario, bandas oscuras. |
| `--mute` | `#54657B` | Texto secundario sobre blanco o papel. |
| `--paper` | `#F5F9FE` | Fondo de los capítulos de contenido y de las zonas internas de tarjeta. |
| `--card` | `#FFFFFF` | Tarjetas. |
| `--line` | `#E1EAF4` | Separadores de 1 px y bordes suaves. |
| `--sun` | `#FF7A2F` | Acento único: sol, botón de descarga, barra de progreso. Texto encima siempre en `--ink`, nunca blanco. |
| `--blue` | `#2563EB` | Enlaces al pasar el ratón, gráficas y foco. |

### Asignaturas
Cada asignatura tiene un color fijo que la acompaña en toda la app: punto, tramo del arco, píldora, barra de progreso.

| Asignatura | Token | Valor |
|---|---|---|
| Cálculo II | `--c-calc` | `#2563EB` |
| Estructuras de Datos | `--c-eda` | `#0E9F8E` |
| Física I | `--c-fis` | `#D9468A` |
| Estadística | `--c-est` | `#F08C00` |
| Inglés técnico B2 | `--c-ing` | `#4F7A28` |
| Robótica (optativa) | `--c-rob` | `#B45309` |
| Desarrollo web (optativa) | `--c-web` | `#475569` |

Los fondos de las píldoras y bloques se derivan del color: `color-mix(in srgb, var(--c) 14%, white)` para el fondo, y `color-mix(in srgb, var(--c) 75%, #0D2340)` para el texto.

### Estados
| Estado | Color |
|---|---|
| Listo / correcto | `#16A34A` (fondo `#E8F7EE`, texto `#14632F`) |
| En curso / hoy | `#E0560F` |
| Aviso | fondo `#FFF4E5`, texto `#8A4B00` |
| Quitar / peligro | texto `#B42318`, fondo `#FFF5F4` |

### Qué no usar
- **Violeta o lavanda** en ningún sitio.
- **Texto con degradado.**
- **Brillos de colores** fuera del propio sol.
- **Gris puro sin tinte azul.**

## 4. El cielo (`sky.js`)

`sky.js` calcula la altura del sol para la hora local y una ubicación aproximada. Luego escribe estas variables en `<html>`:

| Variable | Qué es |
|---|---|
| `--bg-a`, `--bg-b`, `--bg-c` | Las tres paradas del degradado del cielo (arriba, centro, abajo). |
| `--on-sky`, `--on-sky-mute` | Color del texto que va directamente sobre el cielo. Oscuro de día, claro de noche. |
| `--stars` | Opacidad de las estrellas: de 0 a 1. |

**Ubicación.** Una página web publicada no puede leer la ubicación sin permiso. Por eso se deduce de la zona horaria del dispositivo (`Europe/Madrid` → Madrid), y si no es conocida, del desfase UTC. El usuario puede elegir otra ciudad. La versión final de la app puede pedir la ubicación real.

**API:**
```js
Sky.apply()          // recalcula con la hora actual
Sky.preview(19.5)    // muestra el cielo de las 19:30 (sin cambiar la hora real)
Sky.live()           // vuelve a la hora real
Sky.setCity('Bilbao')// fija una ciudad ('auto' = por zona horaria)
Sky.cities           // lista de ciudades disponibles
```
Los elementos con `data-sky-label`, `data-sky-how` y `data-sky-range` se rellenan solos.

**Reglas:**
- **Texto sobre el cielo:** usa siempre `var(--on-sky)` y `var(--on-sky-mute)`, nunca colores fijos.
- **Contenido largo:** va en bandas de papel (`.band`) o en tarjetas blancas, que se leen igual de día y de noche.
- **Dónde se ve el cielo:** solo en la cabecera (hero), en el capítulo del cielo y en el cierre. Las bandas de contenido lo tapan.

## 5. Tipografía

| Rol | Familia | Uso |
|---|---|---|
| Titulares | **Bricolage Grotesque** 650 | h1, h2, títulos de tarjeta, cifras grandes. Interletrado negativo: `-0.02em` a `-0.04em`. |
| Interfaz y texto | **Figtree** 400–700 | Párrafos, botones, etiquetas. |
| Horas y datos | **JetBrains Mono** 400–600 | Horas (`09:00`), duraciones, códigos de asignatura (`EDA`), código. |

**Escala:**

| Elemento | Tamaño | Interlineado |
|---|---|---|
| h1 de la landing | `clamp(40px, 6.2vw, 82px)` | 0.98 |
| h2 de capítulo (`.h2`) | `clamp(32px, 4.2vw, 54px)` | 1.02 |
| Título de tarjeta | 19–24 px | — |
| Texto de entrada (`.lead`) | 18 px, color `--mute`, máximo 56ch | — |
| Texto normal | 16 px en la landing, 14.5 px en la app | 1.55 |
| Etiquetas pequeñas | 12–13.5 px | — |

Los titulares llevan `text-wrap: balance`. Nunca pongas un rótulo pequeño en mayúsculas encima de un titular: el titular se sostiene solo.

## 6. Espaciado, formas y sombras

- **Contenedor:** `.wrap`, con un máximo de 1180 px (1240 en la app) y margen lateral mínimo de 20 px (`max(20px, env(safe-area-inset-left))`).
- **Capítulos (`.chap`):** 88 px arriba y abajo en escritorio, 64 px en móvil. Dos capítulos seguidos: el segundo empieza con 24 px. **No uses `min-height: 100vh`** en capítulos de contenido: deja huecos vacíos en escritorio.
- **Huecos:** 16 px entre tarjetas de una rejilla, 12–14 px dentro de una tarjeta, 56 px entre las dos columnas de un `.split`.
- **Radios:**

  | Elemento | Radio |
  |---|---|
  | Píldoras y botones | 999 px |
  | Tarjetas | 22–24 px |
  | Zonas internas | 14–18 px |
  | Bloques del horario | 9–10 px |
  | Banda oscura de descarga | 32 px |

- **Sombras** (siempre con desplazamiento y desenfoque, teñidas de `--ink`):
  - Tarjeta: `0 1px 2px rgba(13,35,64,.05), 0 30px 60px -36px rgba(13,35,64,.45)`
  - Flotante: `0 18px 40px -20px rgba(13,35,64,.5)`
- **Anidamiento:** como máximo dos niveles de caja (tarjeta → zona interna en `--paper`). Nunca una tarjeta dentro de otra tarjeta.

## 7. Componentes

| Componente | Clase | Notas |
|---|---|---|
| Botón primario | `.btn.pri` | Fondo `--ink`, texto blanco. |
| Botón de descarga | `.btn.sun` | Fondo `--sun`, texto `--ink`. Solo para "Descargar". |
| Botón secundario | `.btn.sec` | Blanco con borde `--line`. |
| Tamaños | `.btn` 48 px · `.btn.sm` 40 px | Área táctil mínima: 44 px. |
| Píldora | `.pill` + `--c` | Estado o código de asignatura. |
| Tarjeta | `.card` | Blanca, radio 24, sombra de tarjeta. |
| Chip flotante | `.chip` | Aviso de la app sobre la maqueta (solo en la cabecera; se oculta por debajo de 1100 px). |
| Interruptor | `.sw[role=switch][aria-checked]` + `--c` | Optativas. |
| Navegación | `.nav` + `.links` | Cápsula blanca centrada; el enlace activo se pinta en `--ink`. Se vuelve opaca al salir de la cabecera. |
| Maqueta de la app | `.frame` + `.app` | Barra de ventana con tres puntos y la pantalla Hoy. |
| Banda oscura | `.dl` | Una sola por página (descarga). Resplandor del sol en una esquina. |

**Iconos:** trazo de 1.8 px, 24 × 24, `stroke: currentColor`, extremos redondeados. Se definen en el objeto `P` del script y se insertan con `<i data-i="nombre"></i>`. Disponibles: `gh, arrow, down, win, linux, apple, spark, clock, cal, mic, toggle, doc`. Para añadir uno, añade su `path` a `P`. No uses emojis como iconos.

## 8. Movimiento y respuesta al scroll

**Respuesta al scroll en la landing:**
1. **Barra de progreso** naranja arriba (`--p` de 0 a 1).
2. **Navegación:** el enlace del capítulo visible se activa.
3. **Cabecera:** el sol avanza por el arco de 16:42 a 21:00 al bajar, y la maqueta cambia de estado.
4. **Cómo funciona:** la tarjeta fija (`position: sticky`) cambia entre grabación, transcripción y resumen según el paso que está en el centro de la pantalla.
5. **Capítulo del cielo:** ocupa 220 vh con el contenido fijo. Al bajar, el cielo recorre el día de 06:00 a 24:00. Al salir vuelve a la hora real.

**Reglas:**
- **Curva:** `cubic-bezier(.2,.8,.2,1)`, en `--ease`. Duraciones de 0.15 s (interacción) a 0.9 s (entradas).
- **Hover:** los botones suben 2 px y se hunden al pulsarlos; las tarjetas enlazadas suben 3 px.
- **Entradas:** solo la cabecera, una vez al cargar. Las entradas mueven la posición, nunca parten de opacidad 0.
- **Revelados al aparecer en pantalla:** solo cuando forman parte del contenido (el horario se rellena, las barras crecen). Nunca un fundido genérico en cada sección.
- **Nada de** inclinaciones, carruseles automáticos ni parpadeos.
- **`prefers-reduced-motion`:** todo queda quieto y visible, y el capítulo del cielo deja de estar fijo.
- **Rendimiento:** un solo manejador de scroll, limitado con `requestAnimationFrame`. Los cambios de estado van por `IntersectionObserver`.

## 9. Cómo crear un bloque nuevo

1. **Decide dónde va.** El contenido normal va dentro de una `.band` (fondo papel). Va sobre el cielo solo si el bloque trata del día o del tiempo.
2. **Usa la estructura de capítulo:**
   ```html
   <section class="chap wrap" id="nombre" aria-labelledby="nombre-h">
     <div class="split">            <!-- o una rejilla de 3: .trio -->
       <div>
         <h2 class="h2" id="nombre-h">Un titular que nombra algo concreto</h2>
         <p class="lead">Una o dos frases que expliquen qué hace y para quién.</p>
       </div>
       <article class="card"> … demostración real de la app … </article>
     </div>
   </section>
   ```
3. **Enséñalo, no lo describas.** Cada bloque lleva un trozo de la app en HTML real (una lista de clases, una tarea que se puede marcar, un horario), con datos de ejemplo verosímiles. Nada de fotos de archivo ni iconos sueltos en cuadrados.
4. **Usa el color de las asignaturas** para los datos, `--sun` solo para descargar y el sol, y `--ink` para la acción principal.
5. **Una acción principal por bloque, como mucho.** Los botones dicen verbo y objeto: "Descargar para Windows", no "Saber más".
6. **Si el bloque necesita movimiento**, que sea uno solo y ligado a su propio contenido. Respeta el punto 8.
7. **Añádelo a la navegación** si es un capítulo principal: un enlace en `.links` y su `id` en la lista del `IntersectionObserver` de la navegación.
8. **Compruébalo** a 1440, 1024, 768 y 375 px:
   - sin scroll horizontal;
   - nada que se pise;
   - botones de al menos 44 px de alto en móvil;
   - contraste mínimo de 4.5:1 en el texto normal.

## 10. Diseño adaptable

| Ancho | Cambios |
|---|---|
| Hasta 1100 px | Se ocultan los chips flotantes. |
| Hasta 900 px | Una sola columna. La navegación central se oculta (quedan GitHub y Descargar). Los botones de la cabecera ocupan todo el ancho. El horario muestra códigos (`CAL`, `EDA`…) en lugar de nombres. La tarjeta de "cómo funciona" deja de ser fija. |

En la app, por debajo de 900 px:
- La navegación pasa a una barra inferior flotante.
- El horario semanal se convierte en una vista por días (Lun–Vie) con lista de clases.

## 11. Textos

- **Idioma:** español, tuteando, frases cortas y directas.
- **Nombres:** las cosas se llaman como las conoce el estudiante: "clase", "resumen", "horario", "optativa", "entrega".
- **Sin cifras inventadas:** nada de número de usuarios, valoraciones, testimonios ni comparativas.
- **Plataformas:** Windows "disponible", Linux "próximamente", macOS "en estudio". Cambia estas tres etiquetas a la vez cuando haya novedades, en la cabecera y en el bloque de descarga.

## 12. Accesibilidad

- Navegable con teclado y foco visible: contorno azul de 2 px.
- Los interruptores y casillas llevan `role` y `aria-checked`.
- Las maquetas decorativas llevan `aria-hidden="true"`.
- Las gráficas tienen `aria-label` con su lectura.
- Contraste mínimo de 4.5:1 en el texto normal.
- Nunca texto blanco sobre `--sun`.
