import json
import os
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


# Rutas absolutas basadas en la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_USUARIOS = os.path.join(BASE_DIR, "memoria", "usuarios.json")
RUTA_AVATARES = os.path.join(BASE_DIR, "static", "avatars")
AVATAR_DEFAULT = "avatar_default.svg"
DURACION_SESION_DIAS = 7


class GestorUsuarios:
    def __init__(self, ruta_usuarios: str = RUTA_USUARIOS):
        self.ruta_usuarios = ruta_usuarios
        self._asegurar_archivo()
        self._asegurar_carpeta_avatares()

    def _asegurar_archivo(self):
        os.makedirs(os.path.dirname(self.ruta_usuarios), exist_ok=True)
        if not os.path.exists(self.ruta_usuarios):
            data = {"usuarios": [], "sesiones": {}}
            self._guardar(data)

    def _asegurar_carpeta_avatares(self):
        os.makedirs(RUTA_AVATARES, exist_ok=True)

    def _cargar(self) -> dict:
        try:
            with open(self.ruta_usuarios, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"usuarios": [], "sesiones": {}}

    def _guardar(self, data: dict):
        with open(self.ruta_usuarios, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _hash_password(self, password: str) -> str:
        if BCRYPT_AVAILABLE:
            return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        else:
            salt = secrets.token_hex(16)
            hash_val = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
            return f"pbkdf2:{salt}:{hash_val.hex()}"

    def _verificar_password(self, password: str, hash_almacenado: str) -> bool:
        if BCRYPT_AVAILABLE and hash_almacenado.startswith("$2"):
            return bcrypt.checkpw(password.encode("utf-8"), hash_almacenado.encode("utf-8"))
        elif hash_almacenado.startswith("pbkdf2:"):
            partes = hash_almacenado.split(":")
            if len(partes) == 3:
                _, salt, hash_val = partes
                hash_calculado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
                return hash_calculado.hex() == hash_val
        return False

    def _generar_token(self) -> str:
        return secrets.token_hex(32)

    def _email_existe(self, email: str) -> bool:
        data = self._cargar()
        email_lower = email.lower().strip()
        return any(u["email"].lower() == email_lower for u in data["usuarios"])

    def _obtener_usuario_por_email(self, email: str) -> Optional[dict]:
        data = self._cargar()
        email_lower = email.lower().strip()
        for u in data["usuarios"]:
            if u["email"].lower() == email_lower:
                return u
        return None

    def _obtener_usuario_por_id(self, user_id: str) -> Optional[dict]:
        data = self._cargar()
        for u in data["usuarios"]:
            if u["id"] == user_id:
                return u
        return None

    def _limpiar_sesiones_expiradas(self):
        data = self._cargar()
        ahora = datetime.now(timezone.utc)
        sesiones_validas = {}
        for token, sesion in data["sesiones"].items():
            expiracion = datetime.fromisoformat(sesion["expiracion"])
            if ahora < expiracion:
                sesiones_validas[token] = sesion
        data["sesiones"] = sesiones_validas
        self._guardar(data)

    def _validar_email(self, email: str) -> bool:
        import re
        patron = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(patron, email))

    def _validar_password(self, password: str) -> tuple[bool, str]:
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"
        return True, ""

    def registrar(self, nombre: str, email: str, password: str) -> dict:
        nombre = nombre.strip()
        email = email.strip().lower()

        if not nombre:
            return {"exito": False, "error": "El nombre no puede estar vacío"}

        if not self._validar_email(email):
            return {"exito": False, "error": "El formato del correo no es válido"}

        if self._email_existe(email):
            return {"exito": False, "error": "Ya existe una cuenta con ese correo"}

        valido, msg = self._validar_password(password)
        if not valido:
            return {"exito": False, "error": msg}

        data = self._cargar()
        user_id = str(uuid.uuid4())
        password_hash = self._hash_password(password)
        token = self._generar_token()
        ahora = datetime.now(timezone.utc)
        expiracion = ahora + timedelta(days=DURACION_SESION_DIAS)

        nuevo_usuario = {
            "id": user_id,
            "nombre": nombre,
            "email": email,
            "password_hash": password_hash,
            "foto_perfil": AVATAR_DEFAULT,
            "fecha_creacion": ahora.isoformat(),
            "tokens_consumidos": 0
        }

        data["usuarios"].append(nuevo_usuario)
        data["sesiones"][token] = {
            "user_id": user_id,
            "creacion": ahora.isoformat(),
            "expiracion": expiracion.isoformat()
        }

        self._guardar(data)

        usuario_sin_password = {k: v for k, v in nuevo_usuario.items() if k != "password_hash"}

        return {
            "exito": True,
            "token": token,
            "user": usuario_sin_password
        }

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        usuario = self._obtener_usuario_por_email(email)

        if not usuario:
            return {"exito": False, "error": "Correo o contraseña incorrectos"}

        if not self._verificar_password(password, usuario["password_hash"]):
            return {"exito": False, "error": "Correo o contraseña incorrectos"}

        self._limpiar_sesiones_expiradas()

        data = self._cargar()
        token = self._generar_token()
        ahora = datetime.now(timezone.utc)
        expiracion = ahora + timedelta(days=DURACION_SESION_DIAS)

        data["sesiones"][token] = {
            "user_id": usuario["id"],
            "creacion": ahora.isoformat(),
            "expiracion": expiracion.isoformat()
        }
        self._guardar(data)

        usuario_sin_password = {k: v for k, v in usuario.items() if k != "password_hash"}

        return {
            "exito": True,
            "token": token,
            "user": usuario_sin_password
        }

    def logout(self, token: str) -> dict:
        data = self._cargar()
        if token in data["sesiones"]:
            del data["sesiones"][token]
            self._guardar(data)
            return {"exito": True}
        return {"exito": False, "error": "Sesión no encontrada"}

    def validar_sesion(self, token: str) -> Optional[dict]:
        if not token:
            return None

        data = self._cargar()
        if token not in data["sesiones"]:
            return None

        sesion = data["sesiones"][token]
        expiracion = datetime.fromisoformat(sesion["expiracion"])
        ahora = datetime.now(timezone.utc)

        if ahora >= expiracion:
            del data["sesiones"][token]
            self._guardar(data)
            return None

        usuario = self._obtener_usuario_por_id(sesion["user_id"])
        if usuario:
            return {k: v for k, v in usuario.items() if k != "password_hash"}
        return None

    def obtener_perfil(self, user_id: str) -> Optional[dict]:
        usuario = self._obtener_usuario_por_id(user_id)
        if usuario:
            return {k: v for k, v in usuario.items() if k != "password_hash"}
        return None

    def actualizar_perfil(self, user_id: str, cambios: dict) -> dict:
        data = self._cargar()
        usuario = None
        indice = -1

        for i, u in enumerate(data["usuarios"]):
            if u["id"] == user_id:
                usuario = u
                indice = i
                break

        if not usuario:
            return {"exito": False, "error": "Usuario no encontrado"}

        if "nombre" in cambios and cambios["nombre"].strip():
            data["usuarios"][indice]["nombre"] = cambios["nombre"].strip()

        if "email" in cambios and cambios["email"].strip():
            nuevo_email = cambios["email"].strip().lower()
            if not self._validar_email(nuevo_email):
                return {"exito": False, "error": "El formato del correo no es válido"}
            if self._email_existe(nuevo_email) and nuevo_email != usuario["email"]:
                return {"exito": False, "error": "Ya existe una cuenta con ese correo"}
            data["usuarios"][indice]["email"] = nuevo_email

        if "foto_perfil" in cambios and cambios["foto_perfil"].strip():
            data["usuarios"][indice]["foto_perfil"] = cambios["foto_perfil"].strip()

        self._guardar(data)

        usuario_actualizado = {k: v for k, v in data["usuarios"][indice].items() if k != "password_hash"}
        return {"exito": True, "user": usuario_actualizado}

    def cambiar_password(self, user_id: str, password_actual: str, password_nueva: str) -> dict:
        data = self._cargar()
        usuario = None
        indice = -1

        for i, u in enumerate(data["usuarios"]):
            if u["id"] == user_id:
                usuario = u
                indice = i
                break

        if not usuario:
            return {"exito": False, "error": "Usuario no encontrado"}

        if not self._verificar_password(password_actual, usuario["password_hash"]):
            return {"exito": False, "error": "La contraseña actual es incorrecta"}

        valido, msg = self._validar_password(password_nueva)
        if not valido:
            return {"exito": False, "error": msg}

        data["usuarios"][indice]["password_hash"] = self._hash_password(password_nueva)
        self._guardar(data)

        return {"exito": True}

    def guardar_foto(self, user_id: str, archivo_bytes: bytes, extension: str) -> dict:
        data = self._cargar()
        usuario = self._obtener_usuario_por_id(user_id)

        if not usuario:
            return {"exito": False, "error": "Usuario no encontrado"}

        extensiones_validas = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
        if extension.lower() not in extensiones_validas:
            return {"exito": False, "error": "Formato de imagen no soportado"}

        nombre_archivo = f"{user_id}_{secrets.token_hex(4)}{extension.lower()}"
        ruta_completa = os.path.join(RUTA_AVATARES, nombre_archivo)

        with open(ruta_completa, "wb") as f:
            f.write(archivo_bytes)

        return self.actualizar_perfil(user_id, {"foto_perfil": nombre_archivo})

    def obtener_ruta_avatar(self, nombre_archivo: str) -> str:
        ruta = os.path.join(RUTA_AVATARES, nombre_archivo)
        if os.path.exists(ruta):
            return ruta
        return os.path.join(RUTA_AVATARES, AVATAR_DEFAULT)

    def incrementar_tokens(self, user_id: str, tokens: int):
        data = self._cargar()
        for i, u in enumerate(data["usuarios"]):
            if u["id"] == user_id:
                data["usuarios"][i]["tokens_consumidos"] = u.get("tokens_consumidos", 0) + tokens
                self._guardar(data)
                break


gestor_usuarios_global = GestorUsuarios()
