# Marca de Agente de clases: dirección "Subrayado"

La web de la app. Está en `docs/` y se publica con GitHub Pages en https://ganxxhy.github.io/class-transcripter/. Solo tiene tema oscuro. Es estática, no hay que compilar nada y usa rutas relativas.

## Personaje

No hay mascota: el personaje es el **fosforito**. Habla con notas a mano en el margen ("esto cae seguro", "apuntado ✓").

Frase de marca: **"La chuleta perfecta de cada clase"**. Otra frase: "Lo que entra en el examen, ya subrayado".

## Código de colores (con significado)

| Tipo | Color | Texto encima |
|---|---|---|
| Examen | `#F5FF4F` | `#111111` |
| Entrega | `#FF7EB6` | `#111111` |
| Fecha | `#6CF0A8` | `#111111` |
| Aviso | `#7CC8FF` | `#111111` |

Encima de los cuatro colores el texto va siempre en tinta `#111`, también en modo oscuro.

## Interfaz

| Papel | Claro | Oscuro |
|---|---|---|
| Fondo | `#FAFAF6` | `#111111` |
| Papel o tarjeta | `#FFFFFF` | `#1A1A1A` |
| Tinta | `#111111` | `#F2F2EC` |
| Texto secundario | `#5C5C57` | `#A6A69E` |
| Líneas | `rgba(17,17,17,.12)` | `rgba(242,242,236,.14)` |
| Notas a mano y foco | `#D6286F` | `#FF8CC0` |
| Botón principal | amarillo examen, borde y sombra de 3 px en `#111` | igual |

## Icono y logo

- `assets/icon.svg`: las 5 barras del icono actual (alturas 4, 10, 16, 10 y 4), cada una de un color del código, sobre tinta.
- `assets/logo.svg`: el icono más "AGENTE DE CLASES" en Anton, con "CLASES" subrayado en amarillo. Para usarlo en la app conviene pasar el texto a trazos.
- `favicon.svg`: el mismo que el icono.

## Letras

| Papel | Fuente |
|---|---|
| Titulares (en mayúsculas) | **Anton** |
| Texto | **Inter** (400–700) |
| Detalles técnicos | **JetBrains Mono** (400–500) |
| Notas al margen | **Caveat** (500–700), solo para la voz del fosforito |

Las cuatro son de Google Fonts y tienen licencia OFL.

## Partes interactivas

- **Portada:** un fosforito recorre la chuleta y subraya cada destacado con su color.
- **Cómo funciona:** cuatro tarjetas, cada una con una animación pequeña (grabar, transcribir, resumir y leer en el móvil).
- **Un lunes con la app:** mueves la hora y la ventana de la bandeja cambia de estado (fuera de horario, preparándose, grabando, descanso corto, transcribiendo, resumen listo). Al lado está la semana con la clase de ese momento marcada.
- **Panel "Mis clases":** una simulación del panel. Eliges un color, subrayas la transcripción, ves cómo aparecen los destacados junto al resumen por temas y comparas tu resultado con el de la app ("Coincides con la app en X de 4"). Tiene modo claro y oscuro, y el puntero toma la forma de un fosforito del color elegido.
- **Ventana de actualización:** "Actualizar ahora", "Ahora no" y "Saltar esta versión" responden al pulsarlos.
- **Aviso de Windows:** la ventana de SmartScreen se recorre en dos clics.
- **Novedades:** se leen de la API de GitHub, igual que en la web del búho.
- Con `prefers-reduced-motion` todo aparece ya subrayado y quieto.
