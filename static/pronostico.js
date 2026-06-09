const CONFIG_ESTILOS_CLIMA = {
    0:  { icono: "☀️", bg: "#EBCF7C", desc: "Despejado" },
    1:  { icono: "☀️", bg: "#EBCF7C", desc: "Principalmente Despejado" },
    2:  { icono: "⛅", bg: "#D3D3D3", desc: "Parcialmente Nublado" },
    3:  { icono: "☁️", bg: "#D3D3D3", desc: "Nublado" },
    51: { icono: "🌦️", bg: "#B8D6EB", desc: "Llovizna" },
    53: { icono: "🌦️", bg: "#B8D6EB", desc: "Llovizna Moderada" },
    61: { icono: "🌧️", bg: "#B8D6EB", desc: "Lluvia Débil" },
    80: { icono: "🌧️", bg: "#B8D6EB", desc: "Chubascos Débiles" }
};

const DIAS_ES = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

function obtenerVisualizacionClima(codigo) {
    if (CONFIG_ESTILOS_CLIMA[codigo]) {
        return CONFIG_ESTILOS_CLIMA[codigo];
    }
    if (codigo >= 51 && codigo <= 69) return { icono: "🌧️", bg: "#B8D6EB", desc: "Lluvia" };
    if (codigo >= 71 && codigo <= 79) return { icono: "❄️", bg: "#E3F2FD", desc: "Nieve" };
    if (codigo >= 80 && codigo <= 86) return { icono: "🌧️", bg: "#B8D6EB", desc: "Chubascos" };
    return { icono: "🌤️", bg: "#D3D3D3", desc: "Variable" };
}

function renderizarPronosticoSemanal(dailyData) {
    const contenedor = document.getElementById('contenedor-pronostico-semanal');
    if (!contenedor) return;

    contenedor.innerHTML = "";

    const hoyObj = new Date();
    const hoyString = hoyObj.getFullYear() + '-' +
                      String(hoyObj.getMonth() + 1).padStart(2, '0') + '-' +
                      String(hoyObj.getDate()).padStart(2, '0');

    for (let i = 0; i < dailyData.time.length; i++) {
        const fechaStr = dailyData.time[i];
        const codigoWmo = dailyData.weather_code[i];
        const tMax = Math.round(dailyData.temperature_2m_max[i]);
        const tMin = Math.round(dailyData.temperature_2m_min[i]);

        const visual = obtenerVisualizacionClima(codigoWmo);

        const fechaMapeada = new Date(fechaStr + "T12:00:00");
        const nombreDia = DIAS_ES[fechaMapeada.getDay()];
        const numeroDia = String(fechaMapeada.getDate()).padStart(2, '0');

        const esHoy = (fechaStr === hoyString);
        const claseTarjeta = esHoy ? "tarjeta-clima-dia hoy-activo" : "tarjeta-clima-dia";
        const badgeHoyHtml = esHoy ? "<span class='badge-hoy'>HOY</span>" : "";

        const htmlCard = `
            <div class="${claseTarjeta}" style="background-color: ${visual.bg}" title="${visual.desc}">
                ${badgeHoyHtml}
                <div class="dia-icono">${visual.icono}</div>
                <div class="dia-temperatura-principal">${tMax}°</div>
                <div class="dia-texto">${nombreDia} ${numeroDia}</div>
                <div class="dia-temperaturas">
                    <span class="max">${tMax}°</span>
                    <span class="min">${tMin}°</span>
                </div>
            </div>
        `;
        contenedor.insertAdjacentHTML('beforeend', htmlCard);
    }
}

async function cargarDatosClima(comunaId) {
    try {
        const respuesta = await fetch(`/api/pronostico?comuna_id=${comunaId}`);
        if (!respuesta.ok) throw new Error("Error al obtener el pronóstico del servidor");

        const data = await respuesta.json();
        renderizarPronosticoSemanal(data.daily);
    } catch (error) {
        console.error(error);
        const contenedor = document.getElementById('contenedor-pronostico-semanal');
        if (contenedor) {
            contenedor.innerHTML = "<div class='cargando-placeholder'>⚠️ Error al conectar con Open-Meteo</div>";
        }
    }
}
