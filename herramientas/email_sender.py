import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from dotenv import load_dotenv

# Cargamos las variables de entorno para tener acceso a las credenciales SMTP
load_dotenv()

class EnviarEmailInput(BaseModel):
    destinatario: str = Field(default="benjita1b4@gmail.com", description="Dirección de correo electrónico que recibirá el reporte.")
    asunto: str = Field(description="Asunto del correo, debe ser claro y descriptivo (ej: '☁️ Reporte Meteorológico Puerto Montt')")
    cuerpo: str = Field(description="Contenido completo del mensaje, incluyendo las métricas, el historial comparativo y los consejos personalizados.")

class EnviarEmailTool(BaseTool):
    name: str = "enviar_reporte_email"
    description: str = "Útil para enviar el reporte final estructurado al usuario por correo electrónico. Úsala únicamente cuando ya tengas recopilado el clima actual, el historial y redactado los consejos."
    args_schema: Type[BaseModel] = EnviarEmailInput

    def _run(self, destinatario: str, asunto: str, cuerpo: str) -> str:
        # Recuperamos la configuración del archivo .env
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        remitente = os.getenv("EMAIL_REMITENTE")
        password = os.getenv("EMAIL_PASSWORD") # Password de aplicación de Gmail

        # Validación técnica preventiva (IL2.4)
        if not remitente or not password:
            return "❌ Error: Las credenciales de correo (EMAIL_REMITENTE o EMAIL_PASSWORD) no están configuradas en el archivo .env."

        try:
            # Configuración del mensaje MIME
            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            # Adjuntamos el cuerpo del texto con codificación utf-8 para soportar emojis y tildes(ahora usamos HTML)
            msg.attach(MIMEText(cuerpo, 'html', 'utf-8'))

            # Conexión segura al servidor SMTP
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls() # Cifrado TLS
            server.login(remitente, password)
            
            # Envío del correo electrónico
            server.sendmail(remitente, destinatario, msg.as_string())
            server.quit()
            
            return f"✅ Correo enviado exitosamente a {destinatario} con el asunto: '{asunto}'."
        
        except smtplib.SMTPAuthenticationError:
            return "❌ Error de autenticación: El correo o la contraseña de aplicación de Gmail son incorrectos."
        except smtplib.SMTPException as e:
            return f"❌ Error en el protocolo SMTP al enviar el correo: {str(e)}"
        except Exception as e:
            return f"❌ Error inesperado en la herramienta de email: {str(e)}"