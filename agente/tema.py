"""Aspecto "Jornada" de Estudio para las ventanas de Tkinter.

Colores y letras de la guía de diseño: tinta azul noche, papel claro, tarjetas blancas y el sol
naranja. La cabecera pinta un cielo que cambia con la hora del día, como el panel y la web.
"""
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import ttk

INK = "#0D2340"
MUTE = "#54657B"
PAPER = "#F5F9FE"
CARD = "#FFFFFF"
LINE = "#E3EBF4"
LINE2 = "#CBD6E3"
SUN = "#FF7A2F"
OK = "#16A34A"
NOW = "#E0560F"
REC = "#E5484D"
TEAL = "#0E9F8E"
HOVER = "#17365F"
SKY_C = "#F3F8FF"

# Cielo por horas: (arriba, abajo, texto, texto suave). Igual que sky.js, simplificado a la hora local.
_CIELOS = [
    (0, ("#08122A", "#1D2F5C", "#F2F5FA", "#B9C6DA")),
    (6, ("#1E3F7A", "#E9946A", "#F2F5FA", "#E4ECF7")),
    (7.5, ("#74AEEB", "#F8E5CF", INK, "#3F5068")),
    (9, ("#8EC5FF", "#CFE6FF", INK, "#3F5068")),
    (18, ("#74AEEB", "#F8E5CF", INK, "#3F5068")),
    (19.5, ("#1E3F7A", "#E9946A", "#F2F5FA", "#E4ECF7")),
    (21, ("#08122A", "#1D2F5C", "#F2F5FA", "#B9C6DA")),
]


def cielo(ahora=None):
    ahora = ahora or datetime.now()
    h = ahora.hour + ahora.minute / 60
    actual = _CIELOS[0][1]
    for desde, c in _CIELOS:
        if h >= desde:
            actual = c
    return actual


def _mezcla(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _elegir(root, opciones, defecto):
    try:
        fams = set(tkfont.families(root))
    except tk.TclError:
        fams = set()
    return next((f for f in opciones if f in fams), defecto)


class Fuentes:
    def __init__(self, root):
        disp = _elegir(root, ["Bricolage Grotesque", "Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI"], "TkDefaultFont")
        ui = _elegir(root, ["Figtree", "Segoe UI Variable Text", "Segoe UI"], "TkDefaultFont")
        mono = _elegir(root, ["JetBrains Mono", "Cascadia Mono", "Consolas"], "TkFixedFont")
        self.titulo = (disp, 15, "bold")
        self.marca = (disp, 15, "bold")
        self.seccion = (disp, 11, "bold")
        self.texto = (ui, 10)
        self.texto_b = (ui, 10, "bold")
        self.peque = (ui, 9)
        self.mono = (mono, 9)


def aplicar(root):
    """Configura los estilos ttk y devuelve las fuentes."""
    f = Fuentes(root)
    root.configure(background=PAPER)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=PAPER, foreground=INK, font=f.texto, bordercolor=LINE2, lightcolor=CARD,
                 darkcolor=LINE2, troughcolor=LINE, focuscolor=INK, selectbackground="#FFD2A8", selectforeground=INK)
    st.configure("TFrame", background=PAPER)
    st.configure("Card.TFrame", background=CARD)
    st.configure("TLabel", background=PAPER, foreground=INK)
    st.configure("Card.TLabel", background=CARD, foreground=INK)
    st.configure("Sub.TLabel", background=PAPER, foreground=MUTE, font=f.peque)
    st.configure("CardSub.TLabel", background=CARD, foreground=MUTE, font=f.peque)
    st.configure("Seccion.TLabel", background=CARD, foreground=INK, font=f.seccion)
    st.configure("Titulo.TLabel", background=PAPER, foreground=INK, font=f.seccion)
    # Botones: principal en tinta, secundario blanco con borde, enlace sin caja
    st.configure("TButton", padding=(12, 6), width=0, anchor="center", relief="flat", borderwidth=1, background=CARD, foreground=INK,
                 bordercolor=LINE2, lightcolor=LINE2, darkcolor=LINE2, font=f.texto_b)
    st.map("TButton", background=[("disabled", PAPER), ("pressed", LINE), ("active", SKY_C)],
           foreground=[("disabled", "#9AA9BC")], bordercolor=[("focus", INK)])
    st.configure("Pri.TButton", background=INK, foreground="#FFFFFF", bordercolor=INK, lightcolor=INK, darkcolor=INK)
    st.map("Pri.TButton", background=[("disabled", LINE2), ("pressed", "#0A1B33"), ("active", HOVER)],
           foreground=[("disabled", "#FFFFFF")], bordercolor=[("disabled", LINE2), ("active", HOVER)])
    st.configure("Link.TButton", background=PAPER, foreground=MUTE, bordercolor=PAPER, lightcolor=PAPER,
                 darkcolor=PAPER, padding=(8, 5), font=f.texto)
    st.map("Link.TButton", background=[("active", LINE)], foreground=[("active", INK)], bordercolor=[("active", LINE)])
    st.configure("TCheckbutton", background=CARD, foreground=INK, indicatorcolor=CARD, indicatorbackground=CARD)
    st.map("TCheckbutton", indicatorcolor=[("selected", INK)], background=[("active", CARD)])
    st.configure("TRadiobutton", background=CARD, foreground=INK, indicatorcolor=CARD)
    st.map("TRadiobutton", indicatorcolor=[("selected", INK)], background=[("active", CARD)])
    st.configure("TCombobox", padding=6, fieldbackground=CARD, background=CARD, arrowcolor=INK, bordercolor=LINE2)
    st.map("TCombobox", fieldbackground=[("readonly", CARD)], bordercolor=[("focus", INK)])
    st.configure("TEntry", padding=6, fieldbackground=CARD, bordercolor=LINE2)
    st.map("TEntry", bordercolor=[("focus", INK)])
    st.configure("Nivel.Horizontal.TProgressbar", troughcolor=LINE, background=TEAL, bordercolor=LINE,
                 lightcolor=TEAL, darkcolor=TEAL, thickness=8)
    st.configure("TSeparator", background=LINE)
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", "#FFD2A8")
    root.option_add("*TCombobox*Listbox.selectForeground", INK)
    root.option_add("*TCombobox*Listbox.font", f.texto)
    return f


def tarjeta(padre, **pack):
    """Tarjeta blanca con borde suave (Tk no redondea esquinas)."""
    marco = tk.Frame(padre, background=CARD, highlightthickness=1, highlightbackground=LINE, bd=0)
    marco.pack(**pack)
    dentro = ttk.Frame(marco, style="Card.TFrame", padding=(14, 12))
    dentro.pack(fill="both", expand=True)
    return dentro


class Cabecera(tk.Canvas):
    """Cielo de la hora actual con la marca, el estado y un punto rojo si está grabando."""

    def __init__(self, padre, fuentes, alto=122):
        super().__init__(padre, height=alto, highlightthickness=0, bd=0, background=PAPER)
        self.f = fuentes
        self.estado, self.sub, self.grabando = "", "", False
        self._cielo = None
        self.bind("<Configure>", lambda e: self._pintar())

    def poner(self, estado, sub="", grabando=False):
        c = cielo()
        if (estado, sub, grabando, c) != (self.estado, self.sub, self.grabando, self._cielo):
            self.estado, self.sub, self.grabando = estado, sub, grabando
            self._pintar()

    def _pintar(self):
        w, h = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        arriba, abajo, txt, txt2 = self._cielo = cielo()
        self.delete("all")
        pasos = 28
        for i in range(pasos):
            y0, y1 = h * i / pasos, h * (i + 1) / pasos + 1
            self.create_rectangle(0, y0, w, y1, fill=_mezcla(arriba, abajo, i / (pasos - 1)), width=0)
        # Marca: sol + "estudio"
        self.create_oval(16, 15, 34, 33, fill=SUN, outline="#FFD2A8", width=2)
        self.create_text(42, 24, text="estudio", anchor="w", font=self.f.marca, fill=txt)
        x = 16
        if self.grabando:
            self.create_oval(16, 51, 27, 62, fill=REC, outline="")
            x = 34
        self.create_text(x, 44, text=self.estado, anchor="nw", font=self.f.titulo, fill=txt, width=w - x - 16)
        if self.sub:
            self.create_text(16, h - 12, text=self.sub, anchor="sw", font=self.f.peque, fill=txt2, width=w - 32)


def icono(tam=64):
    """Icono de Estudio como imagen PIL: arco del día y el sol sobre azul noche."""
    from PIL import Image, ImageDraw
    k = 4  # se dibuja grande y se reduce para suavizar bordes
    s = tam * k
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * .23), fill=INK)
    r = s * 20 / 64
    cx, cy = s / 2, s * 46 / 64
    d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill="#CFE6FF", width=int(s * 5 / 64))
    sx, sy, sr = s * 46.1 / 64, s * 31.9 / 64, s * 6.25 / 64
    d.ellipse((sx - sr - s * 1.75 / 64, sy - sr - s * 1.75 / 64, sx + sr + s * 1.75 / 64, sy + sr + s * 1.75 / 64), fill="#FFFFFF")
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=SUN)
    return img.resize((tam, tam), Image.LANCZOS)
