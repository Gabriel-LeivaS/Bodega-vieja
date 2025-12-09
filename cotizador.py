# BIBLIOTECAS NECESARIAS
from flask import Flask, request, render_template, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from flask_migrate import Migrate
from livereload import Server # Si no la usas en producción, puedes quitarla o comentarla

#
# Crear la aplicación Flask
app = Flask(__name__)
app.secret_key = 'Fernando2003'

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bodega_vieja.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar SQLAlchemy
db = SQLAlchemy(app)

# Inicializar Flask-Migrate
migrate = Migrate(app, db)


# ============================================================
# DATOS DEL COTIZADOR DE CASAS
# ============================================================

# --- 1. Datos de las Casas Base (Subtotal y Costos de ítems originales) ---
# Se utiliza el Subtotal como base para los cálculos de modificaciones por opciones.
# Los 'items_costo' son los valores base de las partidas específicas que serán multiplicadas por las opciones.
CASAS_BASE = {
    "CASA BÁSICA": {
        "subtotal_original": 12735000.0,
        "items_costo": {
            "madera_estructura": 5985000.0, # Ítems 3, 4, 5 (Estructura de piso, muros, cubierta de roble) 
            "instalacion_electrica": 520000.0, # Ítem 7 
            "instalacion_sanitaria": 680000.0, # Ítem 8 
            "puertas_ventanas": 1050000.0, # Ítem 9 
            "aislacion_revestimientos": 1900000.0, # Ítem 6 
            "terminaciones": 1600000.0 # Ítem 10 
        }
    },
    "CASA MEDIA": {
        "subtotal_original": 19375000.0,
        "items_costo": {
            "madera_estructura": 9665000.0, # Ítems 3, 4, 5 
            "instalacion_electrica": 600000.0, # Ítem 7 
            "instalacion_sanitaria": 720000.0, # Ítem 8 
            "puertas_ventanas": 1200000.0, # Ítem 9 
            "aislacion_revestimientos": 2960000.0, # Ítem 6 
            "terminaciones": 2480000.0 # Ítem 10 
        }
    },
    "CASA AMPLIADA": {
        "subtotal_original": 27180000.0,
        "items_costo": {
            "madera_estructura": 13990000.0, # Ítems 3, 4, 5 
            "instalacion_electrica": 680000.0, # Ítem 7 
            "instalacion_sanitaria": 790000.0, # Ítem 8 
            "puertas_ventanas": 1300000.0, # Ítem 9 
            "aislacion_revestimientos": 4320000.0, # Ítem 6 
            "terminaciones": 3600000.0 # Ítem 10 
        }
    }
}

# --- 2. Opciones de Mejora (Multiplicadores) ---
OPCIONES_MEJORA = {
    "tipo_madera": { # 
        "Roble blanco": 1.00,
        "Roble raulí": 1.10,
        "Roble pellín": 1.25,
        "Roble tratado": 1.15
    },
    "instalacion_electrica": { # 
        "Estándar": 1.00,
        "Mejorada LED": 1.15,
        "Domótica básica": 1.30
    },
    "instalacion_sanitaria": { # 
        "Básica": 1.00,
        "Extendida": 1.20
    },
    "puertas_ventanas": { # 
        "Roble nativo": 1.00,
        "PVC": 0.90,
        "Madera-aluminio": 1.40
    },
    "aislacion_revestimientos": { # 
        "Lana mineral": 1.00,
        "Lana de oveja": 1.30,
        "Panel SIP": 1.20
    },
    "terminaciones": { # 
        "Económicas": 1.00,
        "Medias": 1.20,
        "Premium": 1.50
    }
}

# --- 3. Extras Disponibles (Costos Fijos) ---
EXTRAS_DISPONIBLES = { # 
    "Terraza": 500000.0,
    "Estacionamiento": 300000.0,
    "Cierre perimetral": 700000.0,
    "Canaletas": 150000.0
}

# --- 4. Porcentajes Fijos ---
PORCENTAJES_FIJOS = {
    "indirectos": 0.10, # 10%
    "utilidad": 0.15,   # 15%
    "iva_chileno": 0.19 # IVA en Chile
}


# ============================================================
# FUNCIONES DE LÓGICA DE NEGOCIO (Cotizador de Casas)
# ============================================================

def cotizar_casa(tipo_casa, opciones_elegidas, extras_seleccionados):
    """
    Calcula el costo total de una casa personalizada.
    """
    datos_base = CASAS_BASE.get(tipo_casa)
    if not datos_base:
        return {"error": "Tipo de casa no válido."}

    subtotal_actual = datos_base["subtotal_original"]
    costos_items_originales = datos_base["items_costo"]
    
    # Detalle de los ajustes realizados
    ajustes_detalle = []

    # Aplicar ajustes por opciones de mejora
    for categoria_key, opcion_elegida in opciones_elegidas.items():
        if categoria_key in OPCIONES_MEJORA and opcion_elegida in OPCIONES_MEJORA[categoria_key]:
            factor = OPCIONES_MEJORA[categoria_key][opcion_elegida]

            costo_item_original = 0
            nombre_item_afectado = ""

            # Mapeo de categorías de opciones a los ítems de costo originales
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

    # Calcular Indirectos y Utilidad sobre el subtotal ajustado
    costo_indirectos = subtotal_actual * PORCENTAJES_FIJOS["indirectos"]
    costo_utilidad = subtotal_actual * PORCENTAJES_FIJOS["utilidad"]
    
    subtotal_con_margenes = subtotal_actual + costo_indirectos + costo_utilidad

    # Sumar extras
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

    # El total neto para IVA es el subtotal + margenes + extras
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
        "total_neto_final_para_iva": total_neto_final_para_iva, # Este es el total neto que se mostrará en Presupuesto
        "iva_calculado": iva_calculado,
        "valor_final_cotizado": total_con_iva_final, # Este es el valor final con IVA
        "ajustes_detalle": ajustes_detalle,
        "extras_detalle": extras_detalle
    }


# Rutas de la aplicación (continúa aquí con tus rutas existentes)
@app.route('/')
def index():
    return render_template('index.html')

# ... (tus otras rutas existentes)

# @app.route('/cotizador', methods=['GET', 'POST'])
def cotizador_casas():
    cotizacion_resultado = None
    if request.method == 'POST':
        tipo_casa = request.form['tipo_casa']
        
        # Recolectar opciones de mejora
        opciones_elegidas = {}
        for categoria_key in OPCIONES_MEJORA.keys():
            opcion_valor = request.form.get(categoria_key)
            if opcion_valor: # Solo añadir si se seleccionó una opción
                opciones_elegidas[categoria_key] = opcion_valor

        # Recolectar extras seleccionados
        extras_seleccionados = request.form.getlist('extras') # getlist para checkboxes

        # Cliente info
        cliente_nombre = request.form['cliente_nombre']
        cliente_rut = request.form['cliente_rut']
        cliente_direccion = request.form['cliente_direccion']

        # Realizar la cotización
        cotizacion_resultado = cotizar_casa(tipo_casa, opciones_elegidas, extras_seleccionados)
        
        if "error" in cotizacion_resultado:
            flash(cotizacion_resultado["error"], 'danger')
            return redirect(url_for('cotizador_casas')) # Redirigir de vuelta al formulario
        
        # Guardar la cotización en la base de datos (Presupuesto y ServicioPresupuesto)
        try:
            nuevo_presupuesto = Presupuesto(
                cliente_nombre=cliente_nombre,
                cliente_rut=cliente_rut,
                cliente_direccion=cliente_direccion,
                fecha=datetime.utcnow().date(), # Fecha actual
                total_neto=cotizacion_resultado['total_neto_final_para_iva'], # Total antes de IVA chileno
                iva=cotizacion_resultado['iva_calculado'],
                total_con_iva=cotizacion_resultado['valor_final_cotizado'] # Valor final con IVA chileno
            )
            db.session.add(nuevo_presupuesto)
            db.session.flush() # Para que nuevo_presupuesto.id esté disponible

            # Agregar los servicios detallados al Presupuesto
            db.session.add(ServicioPresupuesto(
                presupuesto_id=nuevo_presupuesto.id,
                descripcion=f"Casa Base: {tipo_casa} (Subtotal Original)",
                precio=cotizacion_resultado['subtotal_base_original']
            ))
            
            # Ajustes por opciones de mejora
            for detalle in cotizacion_resultado['ajustes_detalle']:
                db.session.add(ServicioPresupuesto(
                    presupuesto_id=nuevo_presupuesto.id,
                    descripcion=detalle['descripcion'],
                    precio=detalle['precio']
                ))
            
            # Adición de indirectos y utilidad (como servicios para el detalle)
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

            # Extras
            for detalle in cotizacion_resultado['extras_detalle']:
                db.session.add(ServicioPresupuesto(
                    presupuesto_id=nuevo_presupuesto.id,
                    descripcion=detalle['descripcion'],
                    precio=detalle['precio']
                ))

            db.session.commit()
            flash('Cotización generada y guardada exitosamente.', 'success')
            return redirect(url_for('detalle_presupuesto', presupuesto_id=nuevo_presupuesto.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar la cotización: {e}", 'danger')
            # Si hay un error al guardar, puedes volver al formulario con los datos o mostrar el error.
            return render_template('cotizador_casas.html',
                                   casas_base=CASAS_BASE,
                                   opciones_mejora=OPCIONES_MEJORA,
                                   extras_disponibles=EXTRAS_DISPONIBLES,
                                   cotizacion_resultado=cotizacion_resultado,
                                   form_data=request.form) # Pasa los datos del formulario de vuelta


    # Si es GET request o si hubo un error al guardar y no se redirigió
    return render_template('cotizador_casas.html',
                           casas_base=CASAS_BASE,
                           opciones_mejora=OPCIONES_MEJORA,
                           extras_disponibles=EXTRAS_DISPONIBLES)

# ... (resto de tus rutas y el if __name__ == '__main__':)