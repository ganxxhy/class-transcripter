/* Agente de clases — versión "Subrayado" (sin dependencias) */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const pad = n => String(n).padStart(2, '0');
  const COLORS = { examen: '#F5FF4F', entrega: '#FF7EB6', fecha: '#6CF0A8', aviso: '#7CC8FF' };
  const LABEL = { examen: 'examen', entrega: 'entrega', fecha: 'fecha', aviso: 'aviso' };

  /* ---------- Hero: el fosforito subraya la chuleta ---------- */
  const sheet = $('.hero__sheet');
  const chuleta = $('.chuleta');
  const pen = $('[data-pen]');
  const seq = $$('[data-seq]').sort((a, b) => a.dataset.seq - b.dataset.seq);

  async function heroRun() {
    const h1hl = $('[data-hero-hl]');
    if (reduce) { h1hl.classList.add('is-on'); seq.forEach(s => s.classList.add('is-on')); chuleta.classList.add('is-done'); return; }
    await wait(650);
    h1hl.classList.add('is-on');
    await wait(450);
    const base = sheet.getBoundingClientRect();
    const place = (x, y) => `translate(${x - 11}px, ${y - 150}px) rotate(32deg)`;
    pen.style.opacity = '1';
    for (const span of seq) {
      const rects = span.getClientRects();
      const a = rects[0], b = rects[rects.length - 1];
      const color = getComputedStyle(span).getPropertyValue('--c').trim();
      pen.style.setProperty('--pen-c', color);
      const from = place(a.left - base.left, a.bottom - base.top - 4);
      const to = place(b.right - base.left, b.bottom - base.top - 4);
      await pen.animate([{ transform: pen.style.transform || from }, { transform: from }], { duration: 260, easing: 'cubic-bezier(0.23, 1, 0.32, 1)', fill: 'forwards' }).finished;
      pen.style.transform = from;
      span.classList.add('is-on');
      await pen.animate([{ transform: from }, { transform: to }], { duration: 640, easing: 'cubic-bezier(0.77, 0, 0.175, 1)', fill: 'forwards' }).finished;
      pen.style.transform = to;
    }
    await pen.animate([{ opacity: 1 }, { opacity: 0, transform: pen.style.transform + ' translateY(-20px)' }], { duration: 300, fill: 'forwards' }).finished;
    chuleta.classList.add('is-done');
  }
  if (sheet) {
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(heroRun); else heroRun();
  }

  /* ---------- Cinta ---------- */
  const track = $('[data-ribbon]');
  if (track && !reduce) {
    const clone = track.innerHTML.replace(/<span>/g, '<span aria-hidden="true">');
    track.insertAdjacentHTML('beforeend', clone);
  }
  const pauseBtn = $('[data-ribbon-pause]');
  pauseBtn?.addEventListener('click', () => {
    const r = pauseBtn.closest('.ribbon');
    const p = r.classList.toggle('is-paused');
    pauseBtn.setAttribute('aria-pressed', String(p));
    pauseBtn.setAttribute('aria-label', p ? 'Reanudar la cinta de frases' : 'Pausar la cinta de frases');
  });

  /* ---------- Subraya tú ---------- */
  const transcript = $('[data-transcript]');
  const lines = $$('button[data-ans]', transcript);
  const mine = $('[data-mine]');
  const count = $('[data-count]');
  const score = $('[data-score]');
  let current = 'examen';

  function cursorFor(cat) {
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g transform='rotate(40 16 16)'><rect x='12' y='0' width='9' height='9' rx='2' fill='%23111'/><rect x='12' y='8' width='9' height='15' fill='${COLORS[cat].replace('#', '%23')}' stroke='%23111' stroke-width='1.5'/><path d='M13 23 h7 v3 l-4 5 h-3z' fill='${COLORS[cat].replace('#', '%23')}' stroke='%23111' stroke-width='1.5'/></g></svg>`;
    return `url("data:image/svg+xml;utf8,${svg}") 6 28, pointer`;
  }
  function setPen(cat) {
    current = cat;
    $$('.penbtn').forEach(b => b.setAttribute('aria-checked', String(b.dataset.pen === cat)));
    transcript.style.setProperty('--cursor', cursorFor(cat));
    transcript.style.setProperty('--hover-c', COLORS[cat]);
  }
  $$('.penbtn').forEach(b => b.addEventListener('click', () => setPen(b.dataset.pen)));
  // Flechas del teclado dentro del grupo de colores
  $('.pens').addEventListener('keydown', e => {
    if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(e.key)) return;
    e.preventDefault();
    const btns = $$('.penbtn'), i = btns.findIndex(b => b.dataset.pen === current);
    const n = btns[(i + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1) + btns.length) % btns.length];
    setPen(n.dataset.pen); n.focus();
  });
  setPen('examen');

  function renderMine() {
    const marked = lines.filter(l => l.dataset.mark);
    count.textContent = `· ${marked.length}`;
    if (!marked.length) { mine.innerHTML = '<li class="empty">Elige un color y toca una frase de la transcripción.</li>'; return; }
    mine.innerHTML = marked.map(l => `<li><b class="tag tag--${l.dataset.mark}">${LABEL[l.dataset.mark]}</b><span>${l.querySelector('span').textContent}</span></li>`).join('');
  }
  renderMine();
  function clearVerdicts() { $$('li[data-verdict]', transcript).forEach(li => li.removeAttribute('data-verdict')); score.textContent = ''; }

  lines.forEach(l => l.addEventListener('click', () => {
    clearVerdicts();
    if (l.dataset.mark === current) { delete l.dataset.mark; l.setAttribute('aria-pressed', 'false'); }
    else { l.dataset.mark = current; l.setAttribute('aria-pressed', 'true'); }
    l.setAttribute('aria-label', l.dataset.mark ? `${l.querySelector('span').textContent} (subrayada como ${l.dataset.mark})` : l.querySelector('span').textContent);
    renderMine();
  }));

  $('[data-auto]').addEventListener('click', async () => {
    clearVerdicts();
    const before = new Map(lines.map(l => [l, l.dataset.mark || '']));
    const userDid = [...before.values()].some(Boolean);
    lines.forEach(l => { if (!l.dataset.ans) { delete l.dataset.mark; l.setAttribute('aria-pressed', 'false'); } });
    let hits = 0, total = 0;
    for (const l of lines) {
      if (!l.dataset.ans) continue;
      total++;
      const ok = before.get(l) === l.dataset.ans;
      if (ok) hits++;
      if (!reduce && l.dataset.mark !== l.dataset.ans) { delete l.dataset.mark; await wait(30); }
      l.dataset.mark = l.dataset.ans; l.setAttribute('aria-pressed', 'true');
      if (userDid) l.parentElement.dataset.verdict = ok ? 'ok' : 'miss';
      renderMine();
      if (!reduce) await wait(260);
    }
    score.textContent = userDid ? `Coincides con la app en ${hits} de ${total}.` : 'Así lo deja la app: cuatro destacados, cada uno con su color.';
  });
  $('[data-clear]').addEventListener('click', () => {
    clearVerdicts();
    lines.forEach(l => { delete l.dataset.mark; l.setAttribute('aria-pressed', 'false'); });
    renderMine();
  });

  /* ---------- Un lunes con la app ---------- */
  const range = $('[data-day-range]');
  const tray = $('.tray');
  const tOut = $('[data-day-time]');
  const stateOut = $('[data-day-state]');
  const lineOut = $('[data-day-line]');
  const blkCalc = $('[data-blk="calc"]');
  const blkFis = $('[data-blk="fis"]');
  const nowLine = $('[data-nowline]');
  const hm = m => `${pad(Math.floor(m / 60) % 24)}:${pad(m % 60)}`;

  function dayModel(t) {
    const cls = (name, start, end) => {
      if (t >= start - 5 && t < start) return { tray: 'ready', state: 'Preparándose', line: `${name} empieza en ${start - t} min. Se prepara.` };
      if (t >= start && t < end) {
        if (name === 'Cálculo II' && t >= 590 && t < 595) return { tray: 'rec', state: 'Descanso corto', line: 'Descanso corto: sigue grabando.', now: name };
        return { tray: 'rec', state: '● Grabando', line: t === start ? `Empieza ${name}. Graba.` : `Grabando ${name}. Lleva ${t - start} min.`, now: name };
      }
      if (t >= end && t < end + 30) return { tray: 'write', state: 'Transcribiendo', line: 'Clase terminada. La transcribe en tu ordenador y prepara el resumen.' };
      return null;
    };
    return cls('Cálculo II', 540, 640)
      || cls('Física', 900, 1000)
      || (t < 535 ? { tray: 'sleep', state: 'Fuera de horario', line: 'Fuera de horario no graba nada. Empieza a las 8:55.' }
        : t < 895 ? { tray: 'done', state: 'Resumen listo', line: 'Cálculo II ya está en “Mis clases”. Después, Física a las 15:00.' }
        : t < 1320 ? { tray: 'done', state: 'Día terminado', line: 'Hoy no quedan clases. Las dos están resumidas en “Mis clases”.' }
        : { tray: 'sleep', state: 'Fuera de horario', line: 'De noche no graba nada. Mañana, Álgebra a las 11:00.' });
  }

  let lastLine = '';
  function renderDay() {
    const t = +range.value;
    const m = dayModel(t);
    tOut.textContent = hm(t);
    range.style.setProperty('--p', ((t - 420) / (1440 - 420) * 100) + '%');
    range.setAttribute('aria-valuetext', `${hm(t)}, ${m.state}`);
    tray.dataset.tray = m.tray;
    stateOut.textContent = m.state;
    if (m.line !== lastLine) {
      lastLine = m.line;
      if (reduce) lineOut.textContent = m.line;
      else {
        lineOut.classList.add('is-swap');
        clearTimeout(renderDay.tm);
        renderDay.tm = setTimeout(() => { lineOut.textContent = m.line; lineOut.classList.remove('is-swap'); }, 140);
      }
    }
    blkCalc.classList.toggle('is-now', m.now === 'Cálculo II');
    blkFis.classList.toggle('is-now', m.now === 'Física');
    blkCalc.classList.toggle('is-done', t >= 640);
    blkFis.classList.toggle('is-done', t >= 1000);
    const inGrid = t >= 540 && t <= 1080;
    nowLine.hidden = !inGrid;
    if (inGrid) nowLine.style.setProperty('--t', (t - 540) / 540);
    $$('[data-jump]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.jump === t)));
  }
  range.addEventListener('input', renderDay);
  $$('[data-jump]').forEach(b => b.addEventListener('click', () => {
    const target = +b.dataset.jump;
    if (reduce) { range.value = target; renderDay(); return; }
    const from = +range.value, dur = 520, t0 = performance.now();
    const ease = x => 1 - Math.pow(1 - x, 3);
    const step = now => {
      const k = Math.min(1, (now - t0) / dur);
      range.value = Math.round((from + (target - from) * ease(k)) / 5) * 5;
      renderDay();
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }));
  renderDay();

  /* ---------- Panel: modo oscuro ---------- */
  const frame = $('.app-frame');
  const themeBtn = $('[data-panel-toggle]');
  themeBtn.addEventListener('click', () => {
    const dark = frame.dataset.panelTheme !== 'dark';
    frame.dataset.panelTheme = dark ? 'dark' : 'light';
    themeBtn.setAttribute('aria-label', dark ? 'Cambiar el panel a modo claro' : 'Cambiar el panel a modo oscuro');
  });

  /* ---------- Ventana de actualización ---------- */
  const updRes = $('[data-upd-result]');
  const updMsgs = {
    now: 'Actualizando… al terminar te enseña las novedades.',
    later: 'Vale, te lo recuerda más tarde.',
    skip: 'Hecho. No te vuelve a avisar de esta versión.'
  };
  $$('[data-upd-act]').forEach(b => b.addEventListener('click', () => { updRes.textContent = updMsgs[b.dataset.updAct]; }));

  /* ---------- Aviso de Windows ---------- */
  const ss = $('[data-ss]');
  const hint = $('[data-ss-hint]');
  const setSS = n => {
    ss.dataset.ss = String(n);
    hint.textContent = n === 1 ? 'Paso 1 de 2: pulsa “Más información”.' : n === 2 ? 'Paso 2 de 2: pulsa “Ejecutar de todas formas”.' : 'Hecho. Después del instalador empieza el asistente de primera vez.';
  };
  $('[data-ss-more]').addEventListener('click', () => { setSS(2); $('[data-ss-run]').focus(); });
  $('[data-ss-run]').addEventListener('click', () => {
    setSS(3);
    requestAnimationFrame(() => requestAnimationFrame(() => ss.classList.add('is-run')));
    $('[data-ss-reset]').focus({ preventScroll: true });
  });
  $('[data-ss-no]').addEventListener('click', () => { hint.textContent = 'Sin problema. Para seguir: “Más información” y luego “Ejecutar de todas formas”.'; });
  $('[data-ss-reset]').addEventListener('click', () => { ss.classList.remove('is-run'); setSS(1); $('[data-ss-more]').focus(); });

  /* ---------- Versiones desde GitHub ---------- */
  const esc = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>');
  function bodyToHtml(body) {
    const items = [], paras = [];
    (body || '').split(/\r?\n/).forEach(raw => {
      const l = raw.trim();
      if (!l || /^#/.test(l)) return;
      const m = l.match(/^[-*+]\s+(.*)/);
      if (m) items.push(m[1]); else paras.push(l);
    });
    let html = '';
    if (paras.length) html += `<p>${inline(paras[0])}</p>`;
    if (items.length) html += '<ul>' + items.slice(0, 6).map(i => `<li>${inline(i)}</li>`).join('') + '</ul>';
    return html || '<p>Sin notas para esta versión.</p>';
  }
  fetch('https://api.github.com/repos/ganxxhy/class-transcripter/releases?per_page=3', { headers: { Accept: 'application/vnd.github+json' } })
    .then(r => r.ok ? r.json() : [])
    .then(list => {
      const rel = (list || []).filter(r => !r.draft);
      if (!rel.length) return;
      const latest = rel.find(r => !r.prerelease) || rel[0];
      const v = latest.tag_name.replace(/^v/i, '');
      $$('[data-version-label]').forEach(e => { e.textContent = 'versión ' + v; });
      const asset = (latest.assets || []).find(a => /instalador\.exe$/i.test(a.name));
      $$('[data-filename]').forEach(e => { e.textContent = asset ? asset.name : `AgenteClases-${v}-instalador.exe`; });
      $('[data-upd-version]').textContent = v;
      const fmt = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
      $('[data-releases]').innerHTML = rel.map(r => `
        <article class="release">
          <p><span class="release__tag mono">${esc(r.tag_name.replace(/^v/i, ''))}</span><span class="release__date mono">${fmt.format(new Date(r.published_at || r.created_at))}</span></p>
          ${bodyToHtml(r.body)}
        </article>`).join('');
    })
    .catch(() => {});

  /* ---------- Subrayado del cierre: al llegar ---------- */
  const closeHl = $('[data-close-hl]');
  if (closeHl) {
    if (reduce || !('IntersectionObserver' in window)) closeHl.classList.add('is-on');
    else {
      const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { closeHl.classList.add('is-on'); io.disconnect(); } }, { threshold: 0.6 });
      io.observe(closeHl);
    }
  }

  /* ---------- Menú móvil ---------- */
  const toggle = $('.nav__toggle'), sheetMenu = $('#sheet');
  const setMenu = open => {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    sheetMenu.hidden = !open;
    document.body.style.overflow = open ? 'hidden' : '';
  };
  toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
  sheetMenu.addEventListener('click', e => { if (e.target.closest('a')) setMenu(false); });
  addEventListener('keydown', e => { if (e.key === 'Escape' && !sheetMenu.hidden) { setMenu(false); toggle.focus(); } });

  $$('[data-year]').forEach(e => { e.textContent = new Date().getFullYear(); });
})();
