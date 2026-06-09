const SESSION_CHAT_ID = "session_" + Math.random().toString(36).substring(2, 11);

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
            .replace(/\s+/g, ' ')
            .trim();

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
        
        function tipear() {
            if (i < texto.length) {
                // Detectar sintaxis Markdown para negrita (**texto**)
                if (texto.substring(i, i + 2) === '**') {
                    isBold = !isBold;
                    currentHTML += isBold ? '<strong>' : '</strong>';
                    i += 2;
                    tipear(); // Avanzar instantáneamente sin delay
                    return;
                }
                
                // Escapar caracteres y convertir saltos de línea para innerHTML
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
                
                // Si la etiqueta strong está abierta, la cerramos virtualmente para que el navegador no se rompa
                elemento.innerHTML = currentHTML + (isBold ? '</strong>' : '');
                
                i++;
                const contenedor = document.getElementById('historial-mensajes');
                if (contenedor) contenedor.scrollTop = contenedor.scrollHeight;
                setTimeout(tipear, velocidad);
            } else {
                resolve();
            }
        }
        tipear();
    });
}

async function enviarMensajeChat() {
    const inputElement = document.getElementById('input-mensaje-usuario');
    const historial = document.getElementById('historial-mensajes');

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

    const comunaActivaId = window.comunaSeleccionadaGlobal || "puerto-montt";

    try {
        const respuesta = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: SESSION_CHAT_ID,
                mensaje: mensajeTexto,
                comuna_id: comunaActivaId
            })
        });

        if (!respuesta.ok) throw new Error("Error en la respuesta del agente de IA");

        const data = await respuesta.json();

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

        animator.setState('talk');
        await escribirProgresivamente(burbujaIA, data.respuesta);
        animator.setState('idle');

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
        nodoError.textContent = "❌ Error: El agente no pudo procesar tu mensaje temporal.";
        historial.appendChild(nodoError);
    } finally {
        inputElement.disabled = false;
        inputElement.focus();
        historial.scrollTop = historial.scrollHeight;
    }
}
