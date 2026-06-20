// ==========================================
// AUTENTICACIÓN - FRONTEND
// ==========================================

let usuarioActual = null;

// Verificar estado de sesión al cargar
document.addEventListener('DOMContentLoaded', async function() {
    await verificarEstadoSesion();
});

async function verificarEstadoSesion() {
    try {
        const response = await fetch('/api/auth/estado');
        
        // Verificar que la respuesta sea JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            console.warn('Respuesta no es JSON, tratando como visitante');
            usuarioActual = null;
            mostrarPerfilVisitante(0, 4);
            return;
        }
        
        const data = await response.json();
        
        if (data.logueado) {
            usuarioActual = data.user;
            mostrarPerfilLogueado(data.user);
        } else {
            usuarioActual = null;
            mostrarPerfilVisitante(data.consultas_visitante, data.max_consultas);
        }
    } catch (error) {
        console.error('Error verificando sesión:', error);
        usuarioActual = null;
        mostrarPerfilVisitante(0, 4);
    }
}

function mostrarPerfilLogueado(user) {
    document.getElementById('perfil-no-logueado').style.display = 'none';
    document.getElementById('perfil-logueado').style.display = 'block';
    document.getElementById('nombre-usuario-menu').textContent = user.nombre;
    
    // Mostrar botón de historial para usuarios logueados
    const btnHistorial = document.getElementById('btn-historial');
    if (btnHistorial) {
        btnHistorial.style.display = 'block';
    }
    
    const avatarImg = document.getElementById('avatar-menu-img');
    if (user.foto_perfil && user.foto_perfil !== 'avatar_default.svg') {
        avatarImg.src = `/static/avatars/${user.foto_perfil}`;
    } else {
        avatarImg.src = '/static/avatars/avatar_default.svg';
    }
    
    // Autocompletar correo en sección de reportes
    const inputCorreo = document.getElementById('input-correo');
    if (inputCorreo && user.email) {
        inputCorreo.value = user.email;
        inputCorreo.readOnly = true;
        inputCorreo.style.backgroundColor = '#f0f0f0';
    }
}

function mostrarPerfilVisitante(consultas, maxConsultas) {
    document.getElementById('perfil-no-logueado').style.display = 'block';
    document.getElementById('perfil-logueado').style.display = 'none';
    
    // Ocultar botón de historial para visitantes
    const btnHistorial = document.getElementById('btn-historial');
    if (btnHistorial) {
        btnHistorial.style.display = 'none';
    }
    
    // Habilitar edición de correo para visitantes
    const inputCorreo = document.getElementById('input-correo');
    if (inputCorreo) {
        inputCorreo.readOnly = false;
        inputCorreo.style.backgroundColor = '';
    }
    
    const restantes = maxConsultas - consultas;
    const mensaje = document.getElementById('contador-visitante-msg');
    if (mensaje && restantes > 0) {
        mensaje.textContent = `Tienes ${restantes} consulta${restantes !== 1 ? 's' : ''} gratuita${restantes !== 1 ? 's' : ''}`;
    } else if (mensaje) {
        mensaje.textContent = '';
    }
}

function mostrarModalLogin() {
    document.getElementById('modal-auth').style.display = 'flex';
    mostrarLogin();
}

function mostrarModalRegistro() {
    document.getElementById('modal-auth').style.display = 'flex';
    mostrarRegistro();
}

function cerrarModalAuth() {
    document.getElementById('modal-auth').style.display = 'none';
    document.getElementById('login-error').textContent = '';
    document.getElementById('registro-error').textContent = '';
}

function mostrarLogin() {
    document.getElementById('form-login').style.display = 'block';
    document.getElementById('form-registro').style.display = 'none';
    document.getElementById('switch-a-registro').style.display = 'inline';
    document.getElementById('switch-a-login').style.display = 'none';
    document.getElementById('modal-auth-titulo').textContent = 'Iniciar sesión';
    document.getElementById('modal-auth-subtitulo').textContent = 'Accede para seguir conversando';
}

function mostrarRegistro() {
    document.getElementById('form-login').style.display = 'none';
    document.getElementById('form-registro').style.display = 'block';
    document.getElementById('switch-a-registro').style.display = 'none';
    document.getElementById('switch-a-login').style.display = 'inline';
    document.getElementById('modal-auth-titulo').textContent = 'Crear cuenta';
    document.getElementById('modal-auth-subtitulo').textContent = 'Regístrate para acceso ilimitado';
}

async function iniciarSesion() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');
    
    errorDiv.textContent = '';
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (data.exito) {
            usuarioActual = data.user;
            cerrarModalAuth();
            mostrarPerfilLogueado(data.user);
            // Limpiar formulario
            document.getElementById('login-email').value = '';
            document.getElementById('login-password').value = '';
        } else {
            errorDiv.textContent = data.error || 'Error al iniciar sesión';
        }
    } catch (error) {
        errorDiv.textContent = 'Error de conexión. Intenta nuevamente.';
    }
}

async function registrarUsuario() {
    const nombre = document.getElementById('registro-nombre').value.trim();
    const email = document.getElementById('registro-email').value.trim();
    const password = document.getElementById('registro-password').value;
    const passwordConfirm = document.getElementById('registro-password-confirm').value;
    const errorDiv = document.getElementById('registro-error');
    
    errorDiv.textContent = '';
    
    if (password !== passwordConfirm) {
        errorDiv.textContent = 'Las contraseñas no coinciden';
        return;
    }
    
    if (password.length < 8) {
        errorDiv.textContent = 'La contraseña debe tener al menos 8 caracteres';
        return;
    }
    
    try {
        const response = await fetch('/api/auth/registro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre, email, password })
        });
        
        const data = await response.json();
        
        if (data.exito) {
            usuarioActual = data.user;
            cerrarModalAuth();
            mostrarPerfilLogueado(data.user);
            // Limpiar formulario
            document.getElementById('registro-nombre').value = '';
            document.getElementById('registro-email').value = '';
            document.getElementById('registro-password').value = '';
            document.getElementById('registro-password-confirm').value = '';
        } else {
            errorDiv.textContent = data.error || 'Error al registrar';
        }
    } catch (error) {
        errorDiv.textContent = 'Error de conexión. Intenta nuevamente.';
    }
}

async function cerrarSesion() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        usuarioActual = null;
        mostrarPerfilVisitante(0, 4);
        // Recargar para limpiar estado
        window.location.reload();
    } catch (error) {
        console.error('Error al cerrar sesión:', error);
    }
}

function cerrarModalLimite() {
    document.getElementById('modal-limite').style.display = 'none';
}

function mostrarModalLimiteAlcanzado() {
    document.getElementById('modal-limite').style.display = 'flex';
}

// Cerrar modal al hacer clic fuera
document.addEventListener('click', function(e) {
    const modalAuth = document.getElementById('modal-auth');
    const modalLimite = document.getElementById('modal-limite');
    
    if (e.target === modalAuth) {
        cerrarModalAuth();
    }
    if (e.target === modalLimite) {
        cerrarModalLimite();
    }
});

// Cerrar modal con ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        cerrarModalAuth();
        cerrarModalLimite();
    }
});
