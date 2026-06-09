window.comunaSeleccionadaGlobal = "puerto-montt";

function cambiarPestaña(tipoPestaña) {
    const pestanaChat = document.getElementById('btn-pestana-chat');
    const pestanaReporte = document.getElementById('btn-pestana-reporte');
    const contenidoChat = document.getElementById('contenido-chat');
    const contenidoReporte = document.getElementById('contenido-reporte');

    if (tipoPestaña === 'chat') {
        pestanaChat.classList.add('activo');
        pestanaReporte.classList.remove('activo');
        contenidoChat.classList.add('activa');
        contenidoReporte.classList.remove('activa');
    } else {
        pestanaReporte.classList.add('activo');
        pestanaChat.classList.remove('activo');
        contenidoReporte.classList.add('activa');
        contenidoChat.classList.remove('activa');
    }
}

function toggleMenuCiudades() {
    const menu = document.getElementById('menu-ciudades-desplegable');
    if (menu) {
        menu.classList.toggle('abierto');
    }
}

function seleccionarComuna(id, nombre) {
    window.comunaSeleccionadaGlobal = id;

    document.getElementById('nombre-comuna-activa').textContent = nombre;

    document.getElementById('menu-ciudades-desplegable').classList.remove('abierto');

    cargarDatosClima(id);

    console.log(`📍 Comuna cambiada de forma independiente a: ${nombre} (${id})`);
}

async function inicializarAplicacion() {
    window.addEventListener('click', function(e) {
        const menu = document.getElementById('menu-ciudades-desplegable');
        const btnFlecha = document.querySelector('.ubicacion-selector-footer');
        if (menu && menu.classList.contains('abierto') && !menu.contains(e.target) && !btnFlecha.contains(e.target)) {
            menu.classList.remove('abierto');
        }
    });

    try {
        const respuesta = await fetch('/api/comunas');
        if (!respuesta.ok) throw new Error("No se pudieron cargar las comunas");

        const comunasLista = await respuesta.json();
        const menuDropdown = document.getElementById('menu-ciudades-desplegable');

        if (menuDropdown) {
            menuDropdown.innerHTML = "";
            comunasLista.forEach(comuna => {
                const item = document.createElement('div');
                item.className = "opcion-comuna-item";
                item.textContent = comuna.nombre;
                item.onclick = () => seleccionarComuna(comuna.id, comuna.nombre);
                menuDropdown.appendChild(item);
            });
        }

    } catch (error) {
        console.error("Error al inicializar las comunas:", error);
    }

    cargarDatosClima(window.comunaSeleccionadaGlobal);
}

async function dispararGeneracionReporte() {
    const correo = document.getElementById('input-correo').value.trim();
    if (!correo) {
        alert("Por favor, ingresa un correo válido.");
        return;
    }

    const consola = document.getElementById('consola-pasos');
    const listaPasos = document.getElementById('lista-pasos-progreso');

    consola.style.display = "block";
    listaPasos.innerHTML = "<li>⚡ Ejecutando pipeline en segundo plano para " + window.comunaSeleccionadaGlobal + "...</li>";

    try {
        const res = await fetch('/generar-reporte', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                correo: correo,
                comuna_id: window.comunaSeleccionadaGlobal
            })
        });

        const data = await res.json();
        listaPasos.insertAdjacentHTML('beforeend', "<li>✅ Reporte enviado con éxito.</li>");

        if (data.html_preview) {
            const iframe = document.getElementById('iframe-preview');
            document.getElementById('preview-reporte-contenedor').style.display = "block";
            iframe.srcdoc = data.html_preview;
        }
    } catch (err) {
        listaPasos.insertAdjacentHTML('beforeend', "<li style='color:red;'>❌ Fallo en la cola del agente.</li>");
    }
}

document.addEventListener('DOMContentLoaded', inicializarAplicacion);
