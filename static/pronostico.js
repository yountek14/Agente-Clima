const CONFIG_ESTILOS_CLIMA = {
    0:  { icono: "☀️", bg: "#EBCF7C", desc: "Despejado" },
    1:  { icono: "☀️", bg: "#EBCF7C", desc: "Principalmente Despejado" },
    2:  { icono: "⛅", bg: "#D3D3D3", desc: "Parcialmente Nublado" },
    3:  { icono: "☁️", bg: "#D3D3D3", desc: "Nublado" },
    45: { icono: "🌫️", bg: "#E0E0E0", desc: "Niebla" },
    48: { icono: "🌫️", bg: "#E0E0E0", desc: "Niebla con escarcha" },
    51: { icono: "🌦️", bg: "#B8D6EB", desc: "Llovizna ligera" },
    53: { icono: "🌦️", bg: "#A8C8DE", desc: "Llovizna moderada" },
    55: { icono: "🌦️", bg: "#98B8D0", desc: "Llovizna densa" },
    56: { icono: "🌧️", bg: "#A8C8DE", desc: "Llovizna helada" },
    57: { icono: "🌧️", bg: "#98B8D0", desc: "Llovizna helada densa" },
    61: { icono: "🌧️", bg: "#B8D6EB", desc: "Lluvia débil" },
    63: { icono: "🌧️", bg: "#A8C8DE", desc: "Lluvia moderada" },
    65: { icono: "🌧️", bg: "#98B8D0", desc: "Lluvia intensa" },
    66: { icono: "🌧️", bg: "#A8C8DE", desc: "Lluvia helada" },
    67: { icono: "🌧️", bg: "#98B8D0", desc: "Lluvia helada intensa" },
    71: { icono: "🌨️", bg: "#E3F2FD", desc: "Nieve débil" },
    73: { icono: "🌨️", bg: "#D3E8FD", desc: "Nieve moderada" },
    75: { icono: "🌨️", bg: "#C3DEFD", desc: "Nieve intensa" },
    77: { icono: "🌨️", bg: "#D3E8FD", desc: "Granizo" },
    80: { icono: "🌧️", bg: "#B8D6EB", desc: "Chubascos débiles" },
    81: { icono: "🌧️", bg: "#A8C8DE", desc: "Chubascos moderados" },
    82: { icono: "🌧️", bg: "#98B8D0", desc: "Chubascos intensos" },
    85: { icono: "🌨️", bg: "#D3E8FD", desc: "Chubascos de nieve" },
    86: { icono: "🌨️", bg: "#C3DEFD", desc: "Chubascos de nieve intensos" },
    95: { icono: "⛈️", bg: "#8BA8C8", desc: "Tormenta" },
    96: { icono: "⛈️", bg: "#7B98B8", desc: "Tormenta con granizo" },
    99: { icono: "⛈️", bg: "#6B88A8", desc: "Tormenta intensa" }
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
        const precipitacion = dailyData.precipitation_sum ? dailyData.precipitation_sum[i] : 0;
        const probPrecipitacion = dailyData.precipitation_probability_max ? dailyData.precipitation_probability_max[i] : 0;

        const visual = obtenerVisualizacionClima(codigoWmo);

        const fechaMapeada = new Date(fechaStr + "T12:00:00");
        const nombreDia = DIAS_ES[fechaMapeada.getDay()];
        const numeroDia = String(fechaMapeada.getDate()).padStart(2, '0');

        const esHoy = (fechaStr === hoyString);
        const claseTarjeta = esHoy ? "tarjeta-clima-dia hoy-activo" : "tarjeta-clima-dia";
        const badgeHoyHtml = esHoy ? "<span class='badge-hoy'>HOY</span>" : "";
        
        // Indicador de precipitación
        const precipHtml = precipitacion > 0 
            ? `<div class="dia-precipitacion" title="Precipitación: ${precipitacion}mm (${probPrecipitacion}%)">💧${precipitacion}mm</div>`
            : probPrecipitacion > 20 
                ? `<div class="dia-precipitacion" title="Probabilidad: ${probPrecipitacion}%">💧${probPrecipitacion}%</div>`
                : '';

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
                ${precipHtml}
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
        
        // Mostrar indicador de fusion si corresponde
        const badgeFusion = document.getElementById('badge-fusion');
        if (badgeFusion) {
            badgeFusion.style.display = data.fusionado ? 'inline-block' : 'none';
        }
    } catch (error) {
        console.error(error);
        const contenedor = document.getElementById('contenedor-pronostico-semanal');
        if (contenedor) {
            contenedor.innerHTML = "<div class='cargando-placeholder'>Error al conectar con Open-Meteo</div>";
        }
    }
}
