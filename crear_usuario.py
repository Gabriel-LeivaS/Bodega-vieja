#!/usr/bin/env python3
# Script para crear un nuevo usuario en la base de datos

import sys
import getpass
from werkzeug.security import generate_password_hash

# Importamos la aplicación y los modelos de la base de datos
from index import app, db, User

def crear_usuario():
    """
    Función para crear un nuevo usuario en la base de datos.
    Solicita los datos por consola de manera segura.
    """
    print("\n=== Creación de Nuevo Usuario ===\n")
    
    # Solicitar datos del usuario
    username = input("Nombre de usuario: ").strip()
    
    # Verificar si el usuario ya existe
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f"\n❌ El usuario '{username}' ya existe en la base de datos.")
            return
    
    email = input("Correo electrónico: ").strip()
    
    while True:
        password = getpass.getpass("Contraseña (mínimo 6 caracteres): ")
        confirm_password = getpass.getpass("Confirmar contraseña: ")
        
        if len(password) < 6:
            print("❌ La contraseña debe tener al menos 6 caracteres.")
            continue
            
        if password != confirm_password:
            print("❌ Las contraseñas no coinciden. Inténtalo de nuevo.")
            continue
            
        break
    
    # Crear el hash de la contraseña
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    # Crear y guardar el usuario
    try:
        with app.app_context():
            nuevo_usuario = User(
                username=username,
                email=email,
                password=hashed_password
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            
        print(f"\n✅ Usuario '{username}' creado exitosamente!")
        print(f"Correo: {email}")
        
    except Exception as e:
        print(f"\n❌ Error al crear el usuario: {str(e)}")
        if 'db.session' in locals():
            db.session.rollback()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--admin":
        # Crear un usuario administrador por defecto
        with app.app_context():
            if not User.query.filter_by(username='admin').first():
                admin_user = User(
                    username='admin',
                    email='admin@example.com',
                    password=generate_password_hash('admin123', method='pbkdf2:sha256')
                )
                db.session.add(admin_user)
                db.session.commit()
                print("✅ Usuario administrador creado exitosamente!")
                print("Usuario: admin")
                print("Contraseña: admin123")
                print("\n⚠️  POR SEGURIDAD, CAMBIA LA CONTRASEÑA DESPUÉS DE INICIAR SESIÓN")
            else:
                print("❌ El usuario administrador ya existe.")
    else:
        crear_usuario()
