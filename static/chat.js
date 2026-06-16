const SESSION_CHAT_ID = "session_" + Math.random().toString(36).substring(2, 11);
let autodestructActivo = false;
let timeoutsAutodestruct = [];
let cancelarGeneracion = false;
let timeoutTipeoActual = null;
let generandoRespuesta = false;

// --- LÓGICA DE ANIMACIÓN DEL SPRITE ---
const spriteImage = new Image();
spriteImage.src = "/static/Sol_Sprite.png";

const SPRITE_CONFIG = {
    // Al analizar las casillas negras de la nueva imagen, 
    // definimos un tamaño de corte estándar que cabe dentro de todos los recuadros
    frameWidth: 398, 
    frameHeight: 398,
    columns: 3,
    // Coordenadas iniciales exactas calculadas midiendo el espacio interior de las casillas negras
    colStartX: [59, 512, 975],
    rowStartY: [32, 509, 968],
    animations: {
        idle: { frames: [0], delay: 1000, loop: false },
        // Restauramos el salto por toda la grilla 3x3 para que haga diferentes formas
        talk: { frames: [1, 2, 3, 4, 7, 8, 2, 1], delay: 120, loop: true }
    }
};

class SpriteAnimator {
    constructor(canvas, config) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.config = config;
        this.currentState = 'idle';
        this.frameIdx = 0;
        this.frameTimer = 0;
        this.lastTime = performance.now();
    }

    setState(state) {
        if (this.currentState !== state && this.config.animations[state]) {
            this.currentState = state;
            this.frameIdx = 0;
            this.frameTimer = 0;
        }
    }

    update(deltaTime) {
        const anim = this.config.animations[this.currentState];
        if (!anim) return;

        this.frameTimer += deltaTime;
        if (this.frameTimer >= anim.delay) {
            this.frameTimer = 0;
            this.frameIdx++;
            if (this.frameIdx >= anim.frames.length) {
                if (anim.loop) {
                    this.frameIdx = 0;
                } else {
                    this.frameIdx = anim.frames.length - 1;
                }
            }
        }
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (!spriteImage.complete) return;

        const anim = this.config.animations[this.currentState];
        if (!anim) return;

        const frameIndex = anim.frames[this.frameIdx];
        const col = frameIndex % this.config.columns;
        const row = Math.floor(frameIndex / this.config.columns);
        
        // Obtenemos la posición exacta ignorando los bordes negros
        const sx = this.config.colStartX[col];
        const sy = this.config.rowStartY[row];

        this.ctx.drawImage(
            spriteImage, 
            sx, sy, this.config.frameWidth, this.config.frameHeight,
            0, 0, this.canvas.width, this.canvas.height
        );
    }
}

const activeAnimators = [];

function animationLoop(timestamp) {
    activeAnimators.forEach(animator => {
        const deltaTime = timestamp - animator.lastTime;
        animator.lastTime = timestamp;
        animator.update(deltaTime);
        animator.draw();
    });
    requestAnimationFrame(animationLoop);
}
requestAnimationFrame(animationLoop);
// --- FIN LÓGICA DE ANIMACIÓN ---

// --- CONVERSIÓN DE NÚMEROS A PALABRAS (ESPAÑOL) ---
function numeroAPalabras(num) {
    const unidades = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
                      'diez', 'once', 'doce', 'trece', 'catorce', 'quince'];
    const especiales = ['dieciséis', 'diecisiete', 'dieciocho', 'diecinueve'];
    const veintis = ['veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro',
                     'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve'];
    const decenas = ['', 'diez', 'veinte', 'treinta', 'cuarenta', 'cincuenta',
                     'sesenta', 'setenta', 'ochenta', 'noventa'];

    let signo = '';
    if (num < 0) { signo = 'menos '; num = Math.abs(num); }

    if (!Number.isInteger(num)) {
        const [entero, decimal] = num.toString().split('.');
        const decPalabras = decimal.split('').map(d => unidades[parseInt(d)]).join(' ');
        return signo + numeroAPalabras(parseInt(entero)) + ' punto ' + decPalabras;
    }

    if (num === 100) return signo + 'cien';
    if (num > 100 && num < 200) return signo + 'ciento ' + numeroAPalabras(num - 100);
    if (num >= 200 && num < 1000) {
        const c = Math.floor(num / 100);
        const centenas = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
                          'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos'];
        const resto = num % 100;
        return signo + centenas[c] + (resto > 0 ? ' ' + numeroAPalabras(resto) : '');
    }

    if (num <= 15) return signo + unidades[num];
    if (num < 20) return signo + especiales[num - 16];
    if (num < 30) return signo + veintis[num - 20];

    const d = Math.floor(num / 10);
    const u = num % 10;
    if (u === 0) return signo + decenas[d];
    return signo + decenas[d] + ' y ' + unidades[u];
}

// --- FUNCIÓN PARA REPRODUCIR VOZ HUMANA (EDGE TTS) ---
window.reproducirVozHumana = async function(btnElement, animatorIndex) {
    if (btnElement.classList.contains('cargando-voz')) return;

    const textoCrudo = btnElement.dataset.texto;
    if (!textoCrudo) return;

    const iconoOriginal = btnElement.textContent;
    btnElement.textContent = "⏳";
    btnElement.classList.add('cargando-voz');

    try {
        const textoLimpio = textoCrudo
            .replace(/\p{Emoji}/gu, '')
            .replace(/\*\*/g, '')
            .replace(/\*/g, '')
            .replace(/(\d+)\s*°C/g, '$1 grados Celsius')
            .replace(/(\d+)\s*°F/g, '$1 grados Fahrenheit')
            .replace(/(\d+)\s*%/g, '$1 por ciento')
            .replace(/(\d+)\s*km\/h/g, '$1 kilómetros por hora')
            .replace(/(\d+)\s*mm/g, '$1 milímetros')
            .replace(/(\d+)\s*m\/s/g, '$1 metros por segundo')
            .replace(/-?\d+(?:\.\d+)?/g, m => numeroAPalabras(parseFloat(m)))
            .replace(/\s+/g, ' ')
            .trim();

        console.log('[TTS DEBUG] Texto original:', textoCrudo);
        console.log('[TTS DEBUG] Texto limpio:', textoLimpio);

        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: textoLimpio })
        });

        if (!res.ok) throw new Error("Error en la síntesis de voz");
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        
        const animator = activeAnimators[animatorIndex];
        if (animator) {
            audio.onplay = () => animator.setState('talk');
            audio.onended = () => {
                animator.setState('idle');
                URL.revokeObjectURL(url);
            };
            audio.onpause = () => animator.setState('idle');
        }

        audio.play();
    } catch (err) {
        console.error(err);
        alert("Hubo un problema al generar la voz humana.");
    } finally {
        btnElement.textContent = iconoOriginal;
        btnElement.classList.remove('cargando-voz');
    }
}

function escribirProgresivamente(elemento, texto, velocidad = 18) {
    return new Promise(resolve => {
        let i = 0;
        let isBold = false;
        let currentHTML = "";
        let cancelado = false;
        
        function tipear() {
            if (cancelarGeneracion) {
                cancelado = true;
                if (timeoutTipeoActual) clearTimeout(timeoutTipeoActual);
                resolve(cancelado);
                return;
            }
            if (i < texto.length) {
                if (texto.substring(i, i + 2) === '**') {
                    isBold = !isBold;
                    currentHTML += isBold ? '<strong>' : '</strong>';
                    i += 2;
                    tipear();
                    return;
                }
                
                let char = texto.charAt(i);
                if (char === '\n') {
                    currentHTML += '<br>';
                } else if (char === '<') {
                    currentHTML += '&lt;';
                } else if (char === '>') {
                    currentHTML += '&gt;';
                } else {
                    currentHTML += char;
                }
                
                elemento.innerHTML = currentHTML + (isBold ? '</strong>' : '');
                
                i++;
                const contenedor = document.getElementById('historial-mensajes');
                if (contenedor) contenedor.scrollTop = contenedor.scrollHeight;
                timeoutTipeoActual = setTimeout(tipear, velocidad);
            } else {
                resolve(cancelado);
            }
        }
        tipear();
    });
}

async function enviarMensajeChat() {
    if (generandoRespuesta) return;
    const inputElement = document.getElementById('input-mensaje-usuario');
    const historial = document.getElementById('historial-mensajes');

    if (autodestructActivo) return;
    if (!inputElement || !inputElement.value.trim()) return;

    const welcome = document.getElementById('welcome-screen');
    if (welcome) welcome.style.display = 'none';

    const mensajeTexto = inputElement.value.trim();
    inputElement.value = "";

    // Mensaje usuario con avatar
    const filaUsuario = document.createElement('div');
    filaUsuario.className = "mensaje-fila usuario";

    const avatarUser = document.createElement('div');
    avatarUser.className = "avatar-msg";
    avatarUser.textContent = "👤";

    const burbujaUser = document.createElement('div');
    burbujaUser.className = "mensaje mensaje-usuario";
    burbujaUser.textContent = mensajeTexto;

    filaUsuario.appendChild(burbujaUser);
    filaUsuario.appendChild(avatarUser);
    historial.appendChild(filaUsuario);
    historial.scrollTop = historial.scrollHeight;

    inputElement.disabled = true;
    generandoRespuesta = true;

    const comunaActivaId = window.comunaSeleccionadaGlobal || "puerto-montt";

    let respuesta, data;
    try {
        respuesta = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: SESSION_CHAT_ID,
                mensaje: mensajeTexto,
                comuna_id: comunaActivaId
            })
        });

        data = await respuesta.json();

        if (data.autodestruct) {
            activarAutodestruct();
            inputElement.disabled = false;
            return;
        }

        if (data.autodestruct_cancelado) {
            const burbujaIA = document.createElement('div');
            burbujaIA.className = "mensaje mensaje-ia";
            burbujaIA.textContent = data.respuesta;
            const filaIA = document.createElement('div');
            filaIA.className = "mensaje-fila agente";
            filaIA.appendChild(burbujaIA);
            document.getElementById('historial-mensajes').appendChild(filaIA);
            document.getElementById('historial-mensajes').scrollTop = document.getElementById('historial-mensajes').scrollHeight;
            inputElement.disabled = false;
            return;
        }

        if (!respuesta.ok) {
            const msg = data && data.error ? data.error : "Error en la respuesta del agente";
            throw new Error(msg);
        }

        // Mensaje IA con avatar animado por Canvas
        const filaIA = document.createElement('div');
        filaIA.className = "mensaje-fila agente";

        const avatarIA = document.createElement('div');
        avatarIA.className = "avatar-msg";
        
        const canvasIA = document.createElement('canvas');
        canvasIA.width = 36;
        canvasIA.height = 36;
        avatarIA.appendChild(canvasIA);

        // Inicializar animador para este avatar
        const animator = new SpriteAnimator(canvasIA, SPRITE_CONFIG);
        activeAnimators.push(animator);

        const columnaIA = document.createElement('div');
        columnaIA.style.cssText = "display:flex;flex-direction:column;";

        const burbujaIA = document.createElement('div');
        burbujaIA.className = "mensaje mensaje-ia";
        columnaIA.appendChild(burbujaIA);

        filaIA.appendChild(avatarIA);
        filaIA.appendChild(columnaIA);
        historial.appendChild(filaIA);

        const iconosDerecha = document.getElementById('iconos-input-derecha');
        const iconoMicrofono = document.getElementById('icono-microfono');
        const iconoEnviar = document.getElementById('icono-enviar');

        const btnDetener = document.createElement('span');
        btnDetener.className = "btn-detener-generacion";
        btnDetener.title = "Detener respuesta";
        btnDetener.textContent = "✕";

        if (iconosDerecha && iconoMicrofono && iconoEnviar) {
            iconoMicrofono.style.display = 'none';
            iconoEnviar.style.display = 'none';
            iconosDerecha.appendChild(btnDetener);
        }

        cancelarGeneracion = false;
        animator.setState('talk');

        btnDetener.addEventListener('click', () => {
            cancelarGeneracion = true;
        });

        const fueCancelado = await escribirProgresivamente(burbujaIA, data.respuesta);
        animator.setState('idle');

        if (fueCancelado) {
            burbujaIA.innerHTML += ' <em style="opacity:0.5;font-size:0.85em;">[cancelado]</em>';
        }

        const animatorIndex = activeAnimators.length - 1; // El índice del animador actual

        const textoOriginal = data.respuesta;

        // Herramientas: copiar y voz
        const herramientas = document.createElement('div');
        herramientas.className = "herramientas-msg";

        const btnCopiar = document.createElement('span');
        btnCopiar.title = "Copiar";
        btnCopiar.textContent = "📋";
        btnCopiar.addEventListener('click', () => {
            navigator.clipboard.writeText(textoOriginal);
        });

        const btnVoz = document.createElement('span');
        btnVoz.title = "Escuchar Voz Humana";
        btnVoz.textContent = "🔊";
        btnVoz.dataset.texto = textoOriginal;
        btnVoz.addEventListener('click', function() {
            window.reproducirVozHumana(this, animatorIndex);
        });

        herramientas.appendChild(btnCopiar);
        herramientas.appendChild(btnVoz);
        columnaIA.appendChild(herramientas);

    } catch (error) {
        console.error(error);
        const nodoError = document.createElement('div');
        nodoError.className = "mensaje mensaje-ia";
        nodoError.style.backgroundColor = "#FF597B";
        const detalles = data && data.error ? data.error : (error.message || "Error de conexión con el servidor.");
        nodoError.textContent = "❌ " + detalles;
        historial.appendChild(nodoError);
    } finally {
        cancelarGeneracion = false;
        if (timeoutTipeoActual) clearTimeout(timeoutTipeoActual);
        generandoRespuesta = false;
        const btnDetener = document.querySelector('.btn-detener-generacion');
        if (btnDetener && btnDetener.parentNode) btnDetener.remove();
        const iconoMicrofono = document.getElementById('icono-microfono');
        const iconoEnviar = document.getElementById('icono-enviar');
        if (iconoMicrofono) iconoMicrofono.style.display = '';
        if (iconoEnviar) iconoEnviar.style.display = '';
        inputElement.disabled = false;
        inputElement.focus();
        historial.scrollTop = historial.scrollHeight;
    }
}

const BOMBA_ASCII = [
    "        __  ",
    "    _  |  |_",
    "   | |_/\\_| |",
    "   |    _   |",
    "   |_  ( )  |",
    "    |_|   |_|",
    "     |___|",
    "    __|_|__",
    "   /       \\",
    "  |  x   x  |",
    "  |    _    |",
    "   \\_______/",
    "      | |",
    "     _| |_",
    "    |_____|",
];

const EXPLOSION_ASCII = [
    "             ",
    "    .         ",
    "   ,|,     ",
    "  .;*;.    ",
    "   ;*;     ",
    "  ,/|\\,    ",
    " .';*;'.   ",
    "  ;***;    ",
    " ,/|||\\,   ",
    ".;*****;.  ",
];

function activarAutodestruct() {
    if (autodestructActivo) return;
    autodestructActivo = true;

    const overlay = document.createElement('div');
    overlay.id = 'autodestruct-overlay';
    overlay.innerHTML = `
        <div id="autodestruct-contenido">
            <div id="autodestruct-bomba"></div>
            <div id="autodestruct-timer">3</div>
            <div id="autodestruct-label">AUTODESTRUCCION</div>
            <div id="autodestruct-cancel-hint">Presiona ESC o haz clic para cancelar</div>
        </div>
        <div id="autodestruct-restos"></div>
    `;
    document.body.appendChild(overlay);

    const bombaEl = document.getElementById('autodestruct-bomba');
    const timerEl = document.getElementById('autodestruct-timer');
    const labelEl = document.getElementById('autodestruct-label');
    const hintEl = document.getElementById('autodestruct-cancel-hint');
    let countdown = 3;
    timeoutsAutodestruct = [];

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay || e.target === hintEl) {
            cancelarAutodestruct();
        }
    });

    function onKeyDown(e) {
        if (e.key === 'Escape') {
            cancelarAutodestruct();
        }
    }
    document.addEventListener('keydown', onKeyDown);

    function renderBomba() {
        bombaEl.textContent = BOMBA_ASCII.join('\n');
    }

    function animarExplosion() {
        autodestructActivo = false;
        document.removeEventListener('keydown', onKeyDown);
        bombaEl.textContent = EXPLOSION_ASCII.join('\n');
        bombaEl.className = 'explosion-frame';
        timerEl.style.display = 'none';
        labelEl.textContent = 'BOOOOOOOM';
        if (hintEl) hintEl.style.display = 'none';

        const restos = document.getElementById('autodestruct-restos');
        for (let i = 0; i < 30; i++) {
            const fragmento = document.createElement('div');
            fragmento.className = 'resto';
            fragmento.style.setProperty('--x', (Math.random() * 100) + '%');
            fragmento.style.setProperty('--y', (Math.random() * 100) + '%');
            fragmento.style.setProperty('--r', (Math.random() * 720) + 'deg');
            fragmento.style.setProperty('--s', (0.3 + Math.random() * 0.7) + 's');
            fragmento.style.setProperty('--d', (Math.random() * 300) + 'ms');
            restos.appendChild(fragmento);
        }

        const t1 = setTimeout(() => {
            overlay.className = 'destruido';
            const t2 = setTimeout(() => {
                document.querySelectorAll('.mensaje-fila').forEach(el => el.remove());
                const historial = document.getElementById('historial-mensajes');
                const welcome = document.getElementById('welcome-screen');
                if (welcome) {
                    welcome.style.display = 'flex';
                } else {
                    const nuevoWelcome = document.createElement('div');
                    nuevoWelcome.id = 'welcome-screen';
                    nuevoWelcome.className = 'bienvenida-ia-bloque';
                    nuevoWelcome.innerHTML = '<img src="/static/Logo.png" alt="Agente Clima" class="sol-logo-grande"><h1>Agente-Clima</h1>';
                    historial.prepend(nuevoWelcome);
                }
                overlay.remove();
            }, 1500);
            timeoutsAutodestruct.push(t2);
        }, 1000);
        timeoutsAutodestruct.push(t1);
    }

    function tick() {
        timerEl.textContent = countdown;
        if (countdown === 0) {
            animarExplosion();
            return;
        }
        bombaEl.style.animation = 'shake 0.3s ease-in-out';
        const tShake = setTimeout(() => { bombaEl.style.animation = ''; }, 300);
        timeoutsAutodestruct.push(tShake);
        countdown--;
        const tTick = setTimeout(tick, 1000);
        timeoutsAutodestruct.push(tTick);
    }

    renderBomba();
    const tStart = setTimeout(tick, 500);
    timeoutsAutodestruct.push(tStart);
}

function cancelarAutodestruct() {
    if (!autodestructActivo) return;
    autodestructActivo = false;

    timeoutsAutodestruct.forEach(t => clearTimeout(t));
    timeoutsAutodestruct = [];

    const overlay = document.getElementById('autodestruct-overlay');
    if (overlay) {
        overlay.classList.add('cancelando');
        setTimeout(() => {
            if (overlay.parentNode) overlay.remove();
        }, 400);
    }

    const inputElement = document.getElementById('input-mensaje');
    if (inputElement) inputElement.disabled = false;
}
