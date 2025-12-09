# Iniciar Servidor: source venv/bin/activate
# python index.py

# BIBLIOTECAS NECESARIAS
from flask import Flask, request, render_template, flash, redirect, url_for, make_response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, date
from flask_migrate import Migrate
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from livereload import Server
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from functools import wraps
import re
import os
import logging

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv no está instalado. Usando valores por defecto.")

# Configuración de la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'Fernando2003_fallback_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///bodega_vieja.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de Flask-Mail
app.config.update(
    MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
    MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.getenv('MAIL_USERNAME', 'bodega.vieja10@gmail.com'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD', ''),
    MAIL_DEFAULT_SENDER=(os.getenv('MAIL_DEFAULT_SENDER', 'Bodega Vieja'), os.getenv('MAIL_USERNAME', 'bodega.vieja10@gmail.com')),
    MAIL_DEBUG=True,
    MAIL_SUPPRESS_SEND=False,
    MAIL_ASCII_ATTACHMENTS=False
)
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG'] = os.getenv('DEBUG', 'True') == 'True'

# Inicializar extensiones
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)  # Inicializar Flask-Mail

# Configurar protección CSRF
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# Configurar el logger de SQLAlchemy para que no muestre consultas SQL
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

# Importar Serializer para tokens (secrets y datetime ya importados arriba)
from itsdangerous import URLSafeTimedSerializer as Serializer

def generate_reset_token(email):
    serializer = Serializer(app.secret_key, salt='password-reset-salt')
    return serializer.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expiration=3600):
    """Verifica y decodifica un token de restablecimiento de contraseña."""
    serializer = Serializer(app.secret_key, salt='password-reset-salt')
    try:
        email = serializer.loads(
            token,
            max_age=expiration
        )
        return email
    except (SignatureExpired, BadSignature) as e:
        app.logger.warning(f'Token inválido o expirado: {str(e)}')
        return None
    except Exception as e:
        app.logger.error(f'Error al verificar token: {str(e)}')
        return None

# Decorador para rutas protegidas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validar_email(email):
    """Valida el formato de un email."""
    if not email:
        return False
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

def sanitizar_input(texto, max_length=None):
    """Sanitiza un input eliminando espacios extras y limitando longitud."""
    if not texto:
        return ''
    texto = texto.strip()
    if max_length and len(texto) > max_length:
        texto = texto[:max_length]
    return texto

def validar_rut_chileno(rut):
    """
    Valida un RUT chileno con o sin puntos y guión.
    Retorna (rut_formateado, digito_verificador) si es válido, (None, None) si no.
    """
    # Limpiar el RUT
    rut = str(rut).replace('.', '').replace('-', '').upper().strip()
    
    # Validar formato
    if not re.match(r'^\d{7,8}[0-9Kk]$', rut):
        return None, None
    
    # Separar número y dígito verificador
    numero = rut[:-1]
    dv = rut[-1].upper()
    
    # Validar dígito verificador
    suma = 0
    multiplo = 2
    
    # Calcular dígito verificador
    for r in reversed(numero):
        suma += int(r) * multiplo
        multiplo += 1
        if multiplo > 7:
            multiplo = 2
    
    resto = suma % 11
    dv_esperado = 11 - resto
    
    # Casos especiales
    if dv_esperado == 11:
        dv_esperado = '0'
    elif dv_esperado == 10:
        dv_esperado = 'K'
    else:
        dv_esperado = str(dv_esperado)
    
    if dv_esperado != dv:
        return None, None
    
    # Formatear RUT con puntos y guión
    rut_formateado = f"{int(numero):,}".replace(',', '.') + '-' + dv
    return rut_formateado, dv


# Modelos de la base de datos
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)

class Proyecto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True)

class Empleados(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    puesto = db.Column(db.String(100), nullable=False)
    rut = db.Column(db.String(20), unique=True, nullable=False)
    fecha_contratacion = db.Column(db.Date, nullable=False)
    
class Presupuesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_nombre = db.Column(db.String(100), nullable=False)
    cliente_rut = db.Column(db.String(20), nullable=False)
    cliente_direccion = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    nombre_proyecto = db.Column(db.String(200), nullable=True)
    total_neto = db.Column(db.Float, nullable=False, default=0.0)
    iva = db.Column(db.Float, nullable=False, default=0.0)
    total_con_iva = db.Column(db.Float, nullable=False, default=0.0)

class ServicioPresupuesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    presupuesto_id = db.Column(db.Integer, db.ForeignKey('presupuesto.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    presupuesto = db.relationship('Presupuesto', backref=db.backref('servicios', lazy=True))

class Contacto(db.Model):
    __tablename__ = 'contacto'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    mensaje = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    leido = db.Column(db.Boolean, default=False, nullable=False)

class Asistencia(db.Model):
    __tablename__ = 'asistencia'
    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(db.Integer, db.ForeignKey('empleados.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    hora_entrada = db.Column(db.Time, nullable=True)
    hora_salida = db.Column(db.Time, nullable=True)
    estado = db.Column(db.String(20), nullable=False, default='Presente')  # Presente, Ausente, Tardanza, Permiso
    observaciones = db.Column(db.Text, nullable=True)
    
    empleado = db.relationship('Empleados', backref=db.backref('asistencias', lazy=True))


# ===================== COTIZADOR DE CASAS - DATOS =====================
CASAS_BASE = {
    "CASA BÁSICA": {
        "subtotal_original": 12735000.0,
        "items_costo": {
            "madera_estructura": 5985000.0,
            "instalacion_electrica": 520000.0,
            "instalacion_sanitaria": 680000.0,
            "puertas_ventanas": 1050000.0,
            "aislacion_revestimientos": 1900000.0,
            "terminaciones": 1600000.0
        }
    },
    "CASA MEDIA": {
        "subtotal_original": 19375000.0,
        "items_costo": {
            "madera_estructura": 9665000.0,
            "instalacion_electrica": 600000.0,
            "instalacion_sanitaria": 720000.0,
            "puertas_ventanas": 1200000.0,
            "aislacion_revestimientos": 2960000.0,
            "terminaciones": 2480000.0
        }
    },
    "CASA AMPLIADA": {
        "subtotal_original": 27180000.0,
        "items_costo": {
            "madera_estructura": 13990000.0,
            "instalacion_electrica": 680000.0,
            "instalacion_sanitaria": 790000.0,
            "puertas_ventanas": 1300000.0,
            "aislacion_revestimientos": 4320000.0,
            "terminaciones": 3600000.0
        }
    }
}

OPCIONES_MEJORA = {
    "tipo_madera": {
        "Roble blanco": 1.00,
        "Roble raulí": 1.10,
        "Roble pellín": 1.25,
        "Roble tratado": 1.15
    },
    "instalacion_electrica": {
        "Estándar": 1.00,
        "Mejorada LED": 1.15,
        "Domótica básica": 1.30
    },
    "instalacion_sanitaria": {
        "Básica": 1.00,
        "Extendida": 1.20
    },
    "puertas_ventanas": {
        "Roble nativo": 1.00,
        "PVC": 0.90,
        "Madera-aluminio": 1.40
    },
    "aislacion_revestimientos": {
        "Lana mineral": 1.00,
        "Lana de oveja": 1.30,
        "Panel SIP": 1.20
    },
    "terminaciones": {
        "Económicas": 1.00,
        "Medias": 1.20,
        "Premium": 1.50
    }
}

EXTRAS_DISPONIBLES = {
    "Terraza": 500000.0,
    "Estacionamiento": 300000.0,
    "Cierre perimetral": 700000.0,
    "Canaletas": 150000.0
}

PORCENTAJES_FIJOS = {
    "indirectos": 0.10,
    "utilidad": 0.15,
    "iva_chileno": 0.19
}
# ======================================================================


# ===================== COTIZADOR DE CASAS - LÓGICA =====================
def cotizar_casa(tipo_casa, opciones_elegidas, extras_seleccionados):
    datos_base = CASAS_BASE.get(tipo_casa)
    if not datos_base:
        return {"error": "Tipo de casa no válido."}

    subtotal_actual = datos_base["subtotal_original"]
    costos_items_originales = datos_base["items_costo"]
    ajustes_detalle = []

    for categoria_key, opcion_elegida in opciones_elegidas.items():
        if categoria_key in OPCIONES_MEJORA and opcion_elegida in OPCIONES_MEJORA[categoria_key]:
            factor = OPCIONES_MEJORA[categoria_key][opcion_elegida]
            costo_item_original = 0
            nombre_item_afectado = ""
            if categoria_key == "tipo_madera":
                costo_item_original = costos_items_originales["madera_estructura"]
                nombre_item_afectado = "Estructura y Cubierta de Madera"
            elif categoria_key == "instalacion_electrica":
                costo_item_original = costos_items_originales["instalacion_electrica"]
                nombre_item_afectado = "Instalación Eléctrica"
            elif categoria_key == "instalacion_sanitaria":
                costo_item_original = costos_items_originales["instalacion_sanitaria"]
                nombre_item_afectado = "Instalación Sanitaria"
            elif categoria_key == "puertas_ventanas":
                costo_item_original = costos_items_originales["puertas_ventanas"]
                nombre_item_afectado = "Puertas y Ventanas"
            elif categoria_key == "aislacion_revestimientos":
                costo_item_original = costos_items_originales["aislacion_revestimientos"]
                nombre_item_afectado = "Aislación y Revestimientos"
            elif categoria_key == "terminaciones":
                costo_item_original = costos_items_originales["terminaciones"]
                nombre_item_afectado = "Terminaciones"
            if costo_item_original > 0:
                costo_item_nuevo = costo_item_original * factor
                diferencia_costo = costo_item_nuevo - costo_item_original
                subtotal_actual += diferencia_costo
                ajustes_detalle.append({
                    "descripcion": f"Mejora {nombre_item_afectado}: {opcion_elegida}",
                    "precio": diferencia_costo
                })

    costo_indirectos = subtotal_actual * PORCENTAJES_FIJOS["indirectos"]
    costo_utilidad = subtotal_actual * PORCENTAJES_FIJOS["utilidad"]
    subtotal_con_margenes = subtotal_actual + costo_indirectos + costo_utilidad

    costo_extras = 0
    extras_detalle = []
    for extra in extras_seleccionados:
        if extra in EXTRAS_DISPONIBLES:
            costo_extra_valor = EXTRAS_DISPONIBLES[extra]
            costo_extras += costo_extra_valor
            extras_detalle.append({
                "descripcion": f"Extra: {extra}",
                "precio": costo_extra_valor
            })

    total_neto_final_para_iva = subtotal_con_margenes + costo_extras
    iva_calculado = total_neto_final_para_iva * PORCENTAJES_FIJOS["iva_chileno"]
    total_con_iva_final = total_neto_final_para_iva + iva_calculado

    return {
        "tipo_casa": tipo_casa,
        "subtotal_base_original": datos_base["subtotal_original"],
        "subtotal_ajustado": subtotal_actual,
        "costo_indirectos": costo_indirectos,
        "costo_utilidad": costo_utilidad,
        "subtotal_con_margenes": subtotal_con_margenes,
        "costo_extras": costo_extras,
        "total_neto_final_para_iva": total_neto_final_para_iva,
        "iva_calculado": iva_calculado,
        "valor_final_cotizado": total_con_iva_final,
        "ajustes_detalle": ajustes_detalle,
        "extras_detalle": extras_detalle
    }
# ======================================================================


# Rutas de la aplicación
@app.route('/')
def index():
    return render_template('index.html')

# RUTA DE CONTACTO (para mensajes generales)
@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        nombre = sanitizar_input(request.form.get('nombre'), 100)
        email = sanitizar_input(request.form.get('email'), 120)
        telefono = sanitizar_input(request.form.get('telefono'), 20)
        mensaje = sanitizar_input(request.form.get('mensaje'), 2000)
        
        # Validar campos obligatorios
        if not all([nombre, email, mensaje]):
            flash('Por favor complete todos los campos obligatorios', 'error')
            return redirect(url_for('contacto'))
        
        # Validar email
        if not validar_email(email):
            flash('Por favor ingrese un email válido', 'error')
            return redirect(url_for('contacto'))
        
        # Crear y guardar el mensaje
        nuevo_mensaje = Contacto(
            nombre=nombre,
            email=email,
            telefono=telefono if telefono else None,
            mensaje=mensaje
        )
        
        try:
            db.session.add(nuevo_mensaje)
            db.session.commit()
            flash('¡Mensaje enviado con éxito! Nos pondremos en contacto contigo pronto.', 'success')
            return redirect(url_for('contacto'))
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al enviar el mensaje. Por favor, inténtalo de nuevo.', 'error')
            app.logger.error(f'Error al guardar mensaje de contacto: {str(e)}')
    
    # Renderizar el template de contacto para la vista GET y en caso de error POST
    return render_template(
        'contacto.html',
        casas_base=CASAS_BASE,
        opciones_mejora=OPCIONES_MEJORA,
        extras_disponibles=EXTRAS_DISPONIBLES
    )

# RUTA DE COTIZADOR DE CONTACTO (para cotizaciones avanzadas)
@app.route('/cotizador/contacto', methods=['POST'])
def cotizador_contacto():
    descripcion = request.form['descripcion'] if 'descripcion' in request.form else None
    tipo_casa = request.form['tipo_casa']
    opciones_elegidas = {}
    for categoria_key in OPCIONES_MEJORA.keys():
        opcion_valor = request.form.get(categoria_key)
        if opcion_valor:
            opciones_elegidas[categoria_key] = opcion_valor
    extras_seleccionados = request.form.getlist('extras')
    cliente_nombre = request.form['cliente_nombre']
    cliente_rut = request.form['cliente_rut']
    cliente_direccion = request.form['cliente_direccion']
    cotizacion_resultado = cotizar_casa(tipo_casa, opciones_elegidas, extras_seleccionados)
    
    if "error" in cotizacion_resultado:
        flash(cotizacion_resultado["error"], 'danger')
        return redirect(url_for('contacto')) # Redirige a la página de contacto si hay error
    
    try:
        nuevo_presupuesto = Presupuesto(
            cliente_nombre=cliente_nombre,
            cliente_rut=cliente_rut,
            cliente_direccion=cliente_direccion,
            fecha=datetime.utcnow().date(),
            total_neto=cotizacion_resultado['total_neto_final_para_iva'],
            iva=cotizacion_resultado['iva_calculado'],
            total_con_iva=cotizacion_resultado['valor_final_cotizado']
        )
        db.session.add(nuevo_presupuesto)
        db.session.flush() # Asigna un ID al nuevo_presupuesto antes del commit
        
        # Guardar los detalles de la cotización como ServicioPresupuesto
        db.session.add(ServicioPresupuesto(
            presupuesto_id=nuevo_presupuesto.id,
            descripcion=f"Casa Base: {tipo_casa} (Subtotal Original)",
            precio=cotizacion_resultado['subtotal_base_original']
        ))
        for detalle in cotizacion_resultado['ajustes_detalle']:
            db.session.add(ServicioPresupuesto(
                presupuesto_id=nuevo_presupuesto.id,
                descripcion=detalle['descripcion'],
                precio=detalle['precio']
            ))
        db.session.add(ServicioPresupuesto(
            presupuesto_id=nuevo_presupuesto.id,
            descripcion="Costos Indirectos (10%)",
            precio=cotizacion_resultado['costo_indirectos']
        ))
        db.session.add(ServicioPresupuesto(
            presupuesto_id=nuevo_presupuesto.id,
            descripcion="Utilidad (15%)",
            precio=cotizacion_resultado['costo_utilidad']
        ))
        for detalle in cotizacion_resultado['extras_detalle']:
            db.session.add(ServicioPresupuesto(
                presupuesto_id=nuevo_presupuesto.id,
                descripcion=detalle['descripcion'],
                precio=detalle['precio']
            ))
            
        db.session.commit()
        flash('Cotización enviada correctamente. ¡Gracias por tu interés!', 'success')
        return redirect(url_for('contacto')) # Redirige a la página de contacto (o a una de éxito)
    except Exception as e:
        db.session.rollback() # Revierte la transacción en caso de error
        flash(f"Error al guardar la cotización: {e}", 'danger')
        app.logger.error(f"Error al guardar cotización: {e}") # Log del error
        return redirect(url_for('contacto'))

# RUTA DE NOSOTROS
@app.route('/nosotros')
def nosotros():
    return render_template('nosotros.html')

# RUTA DE LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = sanitizar_input(request.form.get('username', ''), 80)
        password = request.form.get('password', '')
        
        # Validar campos
        if not username or not password:
            flash('Por favor ingrese usuario y contraseña', 'danger')
            return redirect(url_for('login'))

        try:
            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password, password):
                session['logged_in'] = True
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Inicio de sesión exitoso', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Nombre de usuario o contraseña incorrectos', 'danger')
        except Exception as e:
            app.logger.error(f'Error en login: {str(e)}')
            flash('Error al iniciar sesión. Intente nuevamente.', 'danger')

    return render_template('login.html', show_reset_link=True)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# Rutas para recuperación de contraseña
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Por favor ingresa un correo electrónico', 'error')
            return redirect(url_for('forgot_password'))
            
        user = User.query.filter_by(email=email).first()
        
        if user:
            try:
                token = generate_reset_token(user.email)
                reset_url = url_for('reset_password', token=token, _external=True)
                
                msg = Message(
                    'Restablecer contraseña - Bodega Vieja',
                    sender=('Bodega Vieja', app.config['MAIL_USERNAME']),
                    recipients=[user.email]
                )
                
                msg.body = f'''Hola {user.username},

Para restablecer tu contraseña, por favor haz clic en el siguiente enlace:

{reset_url}

Este enlace expirará en 1 hora.

Si no solicitaste este restablecimiento, por favor ignora este correo.

Atentamente,
El equipo de Bodega Vieja
'''
                
                msg.extra_headers = {
                    'X-Priority': '1',
                    'Importance': 'high',
                }
                
                mail.send(msg)
                app.logger.info(f'Correo de recuperación enviado a {user.email}')
                flash('Se ha enviado un correo con instrucciones para restablecer tu contraseña. Por favor revisa tu bandeja de entrada.', 'info')
                
            except Exception as e:
                app.logger.error(f'Error al enviar correo a {email}: {str(e)}')
                app.logger.error(f'Tipo de error: {type(e).__name__}')
                flash('''Lo sentimos, ha ocurrido un error al enviar el correo de recuperación. 
                      Por favor, inténtalo de nuevo más tarde o contacta al soporte técnico.''', 'error')
                return redirect(url_for('forgot_password'))
        else:
            app.logger.warning(f'Intento de recuperación para correo no registrado: {email}')
            
        flash('Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'info')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash('El enlace de restablecimiento no es válido o ha expirado.', 'error')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(request.url)
        
        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres', 'error')
            return redirect(request.url)
        
        user.password = generate_password_hash(password)
        db.session.commit()
        
        flash('Tu contraseña ha sido actualizada correctamente. Por favor inicia sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)


# RUTA DE SERVICIOS
@app.route('/servicios')
def servicios():
    return render_template('servicios.html')

# # RUTA DE ADMINISTRACION
@app.route('/admin')
@login_required
def admin():
    # Obtener la cantidad de mensajes no leídos para mostrar en el badge
    mensajes_no_leidos = Contacto.query.filter_by(leido=False).count() # Obtener mensajes no leídos
    return render_template('admin/admin.html', mensajes_no_leidos=mensajes_no_leidos)

# RUTA DE MENSAJES
@app.route('/admin/mensajes')
@login_required
def ver_mensajes():
    mensajes = Contacto.query.order_by(Contacto.fecha_creacion.desc()).all() # Obtener todos los mensajes
    return render_template('admin/mensajes.html', mensajes=mensajes)

@app.route('/admin/mensajes/marcar_leido/<int:mensaje_id>', methods=['POST'])
@login_required
def marcar_mensaje_leido(mensaje_id):
    mensaje = Contacto.query.get_or_404(mensaje_id)
    mensaje.leido = True
    db.session.commit()
    flash('Mensaje marcado como leído.', 'success')
    return redirect(url_for('ver_mensajes'))

@app.route('/admin/mensajes/eliminar/<int:mensaje_id>', methods=['POST'])
@login_required
def eliminar_mensaje(mensaje_id):
    mensaje = Contacto.query.get_or_404(mensaje_id)
    db.session.delete(mensaje)
    db.session.commit()
    flash('Mensaje eliminado.', 'success')
    return redirect(url_for('ver_mensajes'))


# RUTA DE EMPLEADOS
@app.route('/empleados')
@login_required
def lista_empleados():
    empleados = Empleados.query.all()
    return render_template('admin/empleados.html', empleados=empleados)

# AGREGAR UN EMPLEADO
@app.route('/empleados/agregar', methods=['POST'])
@login_required
def agregar_empleado():
    try:
        nombre = sanitizar_input(request.form.get('nombre', ''), 100)
        puesto = sanitizar_input(request.form.get('puesto', ''), 100)
        rut = request.form.get('rut', '')
        fecha_contratacion_str = request.form.get('fecha_contratacion', '')
        
        # Validar campos obligatorios
        if not all([nombre, puesto, rut, fecha_contratacion_str]):
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('lista_empleados'))
        
        # Validar RUT
        rut_formateado, _ = validar_rut_chileno(rut)
        if not rut_formateado:
            flash('El RUT ingresado no es válido', 'error')
            return redirect(url_for('lista_empleados'))
        
        # Validar y convertir fecha
        try:
            fecha_contratacion = datetime.strptime(fecha_contratacion_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido', 'error')
            return redirect(url_for('lista_empleados'))

        nuevo_empleado = Empleados(
            nombre=nombre,
            puesto=puesto,
            rut=rut_formateado,
            fecha_contratacion=fecha_contratacion
        )

        db.session.add(nuevo_empleado)
        db.session.commit()
        flash('Empleado agregado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error al agregar empleado: {str(e)}')
        flash('Error al agregar empleado. Verifique que el RUT no esté duplicado.', 'error')
    
    return redirect(url_for('lista_empleados'))

# ELIMINAR UN EMPLEADO
@app.route('/empleados/eliminar/<int:empleado_id>', methods=['POST'])
@login_required
def eliminar_empleado(empleado_id):
    empleado = Empleados.query.get_or_404(empleado_id)

    db.session.delete(empleado)
    db.session.commit()

    flash('Empleado eliminado exitosamente', 'success')
    return redirect(url_for('lista_empleados'))

# # RUTA DE PROYECTOS
@app.route('/proyectos')
@login_required
def lista_proyectos():
    proyectos = Proyecto.query.all()
    return render_template('admin/proyectos.html', proyectos=proyectos)

# AGREGAR UN PROYECTO
@app.route('/proyectos/agregar', methods=['POST'])
@login_required
def agregar_proyecto():
    try:
        nombre = sanitizar_input(request.form.get('nombre', ''), 100)
        fecha_inicio_str = request.form.get('fecha_inicio', '')
        fecha_fin_str = request.form.get('fecha_fin', '')
        
        # Validar campos obligatorios
        if not nombre or not fecha_inicio_str:
            flash('El nombre y fecha de inicio son obligatorios', 'error')
            return redirect(url_for('lista_proyectos'))
        
        # Validar y convertir fechas
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else None
            
            # Validar que fecha_fin sea posterior a fecha_inicio
            if fecha_fin and fecha_fin < fecha_inicio:
                flash('La fecha de fin no puede ser anterior a la fecha de inicio', 'error')
                return redirect(url_for('lista_proyectos'))
        except ValueError:
            flash('Formato de fecha inválido', 'error')
            return redirect(url_for('lista_proyectos'))

        nuevo_proyecto = Proyecto(nombre=nombre, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
        db.session.add(nuevo_proyecto)
        db.session.commit()
        flash('Proyecto agregado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error al agregar proyecto: {str(e)}')
        flash('Error al agregar proyecto', 'error')
    
    return redirect(url_for('lista_proyectos'))

# ELIMINAR UN PROYECTO
@app.route('/proyectos/eliminar/<int:proyecto_id>', methods=['POST'])
@login_required
def eliminar_proyecto(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)

    db.session.delete(proyecto)
    db.session.commit()

    flash('Proyecto eliminado exitosamente', 'success')
    return redirect(url_for('lista_proyectos'))

@app.route('/presupuestos')
@login_required
def lista_presupuestos():
    presupuestos = Presupuesto.query.all()
    return render_template(
        'admin/presupuestos.html',
        presupuestos=presupuestos,
        casas_base=CASAS_BASE,
        opciones_mejora=OPCIONES_MEJORA,
        extras_disponibles=EXTRAS_DISPONIBLES
    )

@app.route('/presupuestos/agregar', methods=['GET', 'POST'])
@login_required
def agregar_presupuesto():
    if request.method == 'POST':
        cliente_nombre = request.form['cliente_nombre']
        cliente_rut = request.form['cliente_rut']
        cliente_direccion = request.form['cliente_direccion']
        nombre_proyecto = request.form.get('nombre_proyecto', '') # Usamos .get() por si el campo no se envía
        
        # Validar RUT
        rut_formateado, _ = validar_rut_chileno(cliente_rut)
        if not rut_formateado:
            flash('El RUT ingresado no es válido', 'error')
            return redirect(url_for('lista_presupuestos'))

        nuevo_presupuesto = Presupuesto(
            cliente_nombre=cliente_nombre,
            cliente_rut=rut_formateado,
            cliente_direccion=cliente_direccion,
            nombre_proyecto=nombre_proyecto
        )
        db.session.add(nuevo_presupuesto)
        db.session.commit()

        flash('Presupuesto creado exitosamente', 'success')
        return redirect(url_for('lista_presupuestos'))

    return render_template('admin/agregar_presupuesto.html')

@app.route('/presupuestos/<int:presupuesto_id>/servicios/agregar', methods=['POST'])
@login_required
def agregar_servicio_presupuesto(presupuesto_id):
    try:
        descripcion = sanitizar_input(request.form.get('descripcion', ''), 200)
        precio_str = request.form.get('precio', '')
        
        # Validar campos
        if not descripcion or not precio_str:
            flash('Descripción y precio son obligatorios', 'error')
            return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))
        
        # Validar y convertir precio
        try:
            precio = float(precio_str)
            if precio < 0:
                flash('El precio no puede ser negativo', 'error')
                return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))
        except ValueError:
            flash('Precio inválido', 'error')
            return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))

        servicio = ServicioPresupuesto(
            presupuesto_id=presupuesto_id,
            descripcion=descripcion,
            precio=precio
        )
        db.session.add(servicio)

        presupuesto = Presupuesto.query.get_or_404(presupuesto_id)
        presupuesto.total_neto += precio
        presupuesto.iva = presupuesto.total_neto * 0.19
        presupuesto.total_con_iva = presupuesto.total_neto + presupuesto.iva

        db.session.commit()
        flash('Servicio agregado exitosamente', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error al agregar servicio: {str(e)}')
        flash('Error al agregar servicio', 'error')
    
    return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))

@app.route('/presupuestos/<int:presupuesto_id>')
@login_required
def detalle_presupuesto(presupuesto_id):
    presupuesto = Presupuesto.query.get_or_404(presupuesto_id)
    return render_template('admin/detalle_presupuesto.html', presupuesto=presupuesto)

@app.route('/presupuestos/<int:presupuesto_id>/servicios/<int:servicio_id>/eliminar', methods=['POST'])
@login_required
def eliminar_servicio_presupuesto(presupuesto_id, servicio_id):
    servicio = ServicioPresupuesto.query.get_or_404(servicio_id)
    presupuesto = Presupuesto.query.get_or_404(presupuesto_id)

    presupuesto.total_neto -= servicio.precio
    presupuesto.iva = presupuesto.total_neto * 0.19
    presupuesto.total_con_iva = presupuesto.total_neto + presupuesto.iva

    db.session.delete(servicio)
    db.session.commit()

    flash('Servicio eliminado exitosamente', 'success')
    return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))

@app.route('/presupuestos/eliminar/<int:presupuesto_id>', methods=['POST'])
@login_required
def eliminar_presupuesto(presupuesto_id):
    presupuesto = Presupuesto.query.get_or_404(presupuesto_id)
    
    # Primero eliminamos los servicios asociados
    ServicioPresupuesto.query.filter_by(presupuesto_id=presupuesto_id).delete()
    
    # Luego eliminamos el presupuesto
    db.session.delete(presupuesto)
    db.session.commit()
    
    flash('Presupuesto eliminado correctamente', 'success')
    return redirect(url_for('lista_presupuestos'))


@app.route('/presupuestos/<int:presupuesto_id>/pdf')
@login_required
def descargar_presupuesto_pdf(presupuesto_id):
    presupuesto = Presupuesto.query.get_or_404(presupuesto_id)
    
    if not presupuesto.servicios:
        session.pop('_flashes', None)
        flash('No se puede generar el PDF: El presupuesto no tiene servicios agregados.', 'warning')
        return redirect(url_for('detalle_presupuesto', presupuesto_id=presupuesto_id))
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          rightMargin=2*cm, leftMargin=2*cm,
                          topMargin=2*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CustomDocTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=18, alignment=TA_CENTER, spaceAfter=2, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomDocSubInfo', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_CENTER, spaceAfter=12, textColor=colors.darkgrey))
    styles.add(ParagraphStyle(name='CustomSectionTitle', parent=styles['h2'], fontName='Helvetica-Bold', fontSize=14, alignment=TA_LEFT, spaceBefore=10, spaceAfter=6, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomClientInfo', parent=styles['Normal'], fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=2, leading=14, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomRightAlign', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_RIGHT, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomTableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomTableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_LEFT, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomTableCellRight', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_RIGHT, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomFooterText', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.darkgrey, spaceBefore=15))
    styles.add(ParagraphStyle(name='CustomBoldText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.black))
    styles.add(ParagraphStyle(name='CustomBoldTextRight', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_RIGHT, textColor=colors.black))
    styles.add(ParagraphStyle(name='SignatureLine', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_LEFT, spaceBefore=15, textColor=colors.black))
    styles.add(ParagraphStyle(name='SignatureText', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_LEFT, spaceBefore=2, textColor=colors.black))

    story = []

    pdf_main_title = presupuesto.nombre_proyecto if presupuesto.nombre_proyecto else f"Presupuesto"
    story.append(Paragraph(pdf_main_title, styles['CustomDocTitle']))
    
    fecha_creacion_str = presupuesto.fecha.strftime('%d/%m/%Y') if hasattr(presupuesto, 'fecha') and presupuesto.fecha else 'N/A'
    sub_info_text = f"Presupuesto N°: {presupuesto.id}  |  Fecha: {fecha_creacion_str}"
    story.append(Paragraph(sub_info_text, styles['CustomDocSubInfo']))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Información del Cliente", styles['CustomSectionTitle']))
    story.append(Paragraph(f"<b>Nombre:</b> {presupuesto.cliente_nombre}", styles['CustomClientInfo']))
    story.append(Paragraph(f"<b>RUT:</b> {presupuesto.cliente_rut}", styles['CustomClientInfo']))
    story.append(Paragraph(f"<b>Dirección:</b> {presupuesto.cliente_direccion}", styles['CustomClientInfo']))
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("Detalle de Servicios", styles['CustomSectionTitle']))
    table_data = [
        [Paragraph('Descripción', styles['CustomTableHeader']), Paragraph('Precio Unitario', styles['CustomTableHeader'])]
    ]
    if presupuesto.servicios:
        for servicio in presupuesto.servicios:
            table_data.append([
                Paragraph(servicio.descripcion, styles['CustomTableCell']),
                Paragraph(f"${servicio.precio:,.0f}".replace(',', '.'), styles['CustomTableCellRight'])
            ])
    else:
        table_data.append([Paragraph('No hay servicios agregados.', styles['CustomTableCell'], colSpan=2)])

    col_widths = [12.5*cm, 3.5*cm]
    services_table = Table(table_data, colWidths=col_widths)
    table_style_elements = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.darkgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]
    if not presupuesto.servicios:
        table_style_elements.append(('SPAN', (0,1), (1,1)))
        table_style_elements.append(('ALIGN', (0,1), (1,1), 'CENTER'))

    services_table.setStyle(TableStyle(table_style_elements))
    story.append(services_table)
    story.append(Spacer(1, 0.6*cm))

    totals_data = [
        [Paragraph('Total Neto:', styles['CustomTableCell']), Paragraph(f"${presupuesto.total_neto:,.0f}".replace(',', '.'), styles['CustomTableCellRight'])],
        [Paragraph('IVA (19%):', styles['CustomTableCell']), Paragraph(f"${presupuesto.iva:,.0f}".replace(',', '.'), styles['CustomTableCellRight'])],
        [Paragraph('Total con IVA:', styles['CustomBoldText']), Paragraph(f"${presupuesto.total_con_iva:,.0f}".replace(',', '.'), styles['CustomBoldTextRight'])]
    ]
    totals_table = Table(totals_data, colWidths=[12.5*cm - 4*cm, 4*cm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica')
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 1.5*cm))

    story.append(Paragraph('_________________________', styles['SignatureLine']))
    story.append(Paragraph('Firma Autorizada', styles['SignatureText']))
    story.append(Paragraph('Bodega Vieja', styles['SignatureText']))
    story.append(Spacer(1, 0.5*cm))
    
    story.append(Paragraph("Gracias por su preferencia.", styles['CustomFooterText']))

    doc.build(story)
    
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    
    clean_proyecto_nombre = ""
    if presupuesto.nombre_proyecto:
        clean_proyecto_nombre = ''.join(c if c.isalnum() or c in (' ', '-') else '' for c in presupuesto.nombre_proyecto).strip().replace(' ', '_')
    
    if clean_proyecto_nombre:
        filename = f"Presupuesto_{clean_proyecto_nombre}.pdf"
    else:
        filename = f"Presupuesto_N{presupuesto.id}.pdf"
        
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@app.route('/apu', methods=['GET', 'POST'])
@login_required
def apu():
    global CASAS_BASE, OPCIONES_MEJORA, EXTRAS_DISPONIBLES, PORCENTAJES_FIJOS # Declara que usarás las variables globales
    if request.method == 'POST':
        # Actualizar casas base
        for casa in CASAS_BASE.keys():
            key = f'casas_base_{casa}'
            if key in request.form:
                try:
                    CASAS_BASE[casa]['subtotal_original'] = float(request.form[key])
                except ValueError:
                    pass
        # Actualizar opciones de mejora
        for categoria in OPCIONES_MEJORA.keys():
            for opcion in OPCIONES_MEJORA[categoria].keys():
                key = f'opciones_mejora_{categoria}_{opcion}'
                if key in request.form:
                    try:
                        OPCIONES_MEJORA[categoria][opcion] = float(request.form[key])
                    except ValueError:
                        pass
        # Actualizar extras
        for extra in EXTRAS_DISPONIBLES.keys():
            key = f'extras_disponibles_{extra}'
            if key in request.form:
                try:
                    EXTRAS_DISPONIBLES[extra] = float(request.form[key])
                except ValueError:
                    pass
        # Actualizar porcentajes fijos
        for key in PORCENTAJES_FIJOS.keys():
            form_key = f'porcentajes_fijos_{key}'
            if form_key in request.form:
                try:
                    PORCENTAJES_FIJOS[key] = float(request.form[form_key])
                except ValueError:
                    pass
        flash('Valores de APU actualizados correctamente.', 'success')
        return redirect(url_for('apu'))
    return render_template('admin/apu.html',
        casas_base=CASAS_BASE,
        opciones_mejora=OPCIONES_MEJORA,
        extras_disponibles=EXTRAS_DISPONIBLES,
        porcentajes_fijos=PORCENTAJES_FIJOS)

# RUTAS DE ASISTENCIA
@app.route('/asistencia')
@login_required
def lista_asistencia():
    empleados = Empleados.query.all()
    asistencias = Asistencia.query.order_by(Asistencia.fecha.desc()).all()
    return render_template('admin/asistencia.html', empleados=empleados, asistencias=asistencias)

@app.route('/asistencia/agregar', methods=['POST'])
@login_required
def agregar_asistencia():
    try:
        empleado_id = int(request.form['empleado_id'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        hora_entrada = request.form.get('hora_entrada')
        hora_salida = request.form.get('hora_salida')
        estado = request.form.get('estado', 'Presente')
        observaciones = request.form.get('observaciones', '')
        
        # Convertir horas si están presentes
        hora_entrada_time = datetime.strptime(hora_entrada, '%H:%M').time() if hora_entrada else None
        hora_salida_time = datetime.strptime(hora_salida, '%H:%M').time() if hora_salida else None
        
        nueva_asistencia = Asistencia(
            empleado_id=empleado_id,
            fecha=fecha,
            hora_entrada=hora_entrada_time,
            hora_salida=hora_salida_time,
            estado=estado,
            observaciones=observaciones
        )
        
        db.session.add(nueva_asistencia)
        db.session.commit()
        flash('Asistencia registrada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar asistencia: {str(e)}', 'error')
    
    return redirect(url_for('lista_asistencia'))

@app.route('/asistencia/eliminar/<int:asistencia_id>', methods=['POST'])
@login_required
def eliminar_asistencia(asistencia_id):
    try:
        asistencia = Asistencia.query.get_or_404(asistencia_id)
        db.session.delete(asistencia)
        db.session.commit()
        flash('Asistencia eliminada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar asistencia: {str(e)}', 'error')
    
    return redirect(url_for('lista_asistencia'))

def crear_proyectos_base():
    if Proyecto.query.count() == 0:
        proyectos_base = [
            {
                'nombre': 'Proyecto de Mantenimiento',
                'fecha_inicio': '2025-06-01',
                'fecha_fin': '2025-12-31'
            },
            {
                'nombre': 'Renovación de Instalaciones',
                'fecha_inicio': '2025-07-01',
                'fecha_fin': '2025-09-30'
            },
            {
                'nombre': 'Ampliación de Bodega',
                'fecha_inicio': '2025-08-01',
                'fecha_fin': '2025-11-30'
            }
        ]
        
        for proyecto in proyectos_base:
            fecha_inicio = datetime.strptime(proyecto['fecha_inicio'], '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(proyecto['fecha_fin'], '%Y-%m-%d').date()
            nuevo_proyecto = Proyecto(
                nombre=proyecto['nombre'],
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin
            )
            db.session.add(nuevo_proyecto)
        
        try:
            db.session.commit()
            print("Proyectos base creados exitosamente")
        except Exception as e:
            db.session.rollback()
            print(f"Error al crear proyectos base: {str(e)}")

def crear_usuario_admin_base():
    with app.app_context():
        # Verificar si ya existe un usuario 'admin'
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('adminpass', method='pbkdf2:sha256')
            admin_user = User(username='admin', email='bodega.vieja10@gmail.com', password=hashed_password)
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario 'admin' creado exitosamente.")
        else:
            print("El usuario 'admin' ya existe.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Asegúrate de que las tablas se creen
        crear_proyectos_base()
        crear_usuario_admin_base() # Llama a la función para crear el usuario admin

    # Iniciar el servidor Livereload para desarrollo
    server = Server(app.wsgi_app)
    server.serve(port=5012, debug=True)