from index import app, db, User, Proyecto, Empleados, Presupuesto, ServicioPresupuesto, Contacto
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

def create_tables():
    with app.app_context():
        # Drop all tables first (be careful with this in production!)
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        # Crear usuario administrador por defecto
        try:
            # Primero verificar si el usuario ya existe
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                hashed_password = generate_password_hash('admin123')  # Contraseña por defecto
                admin = User(
                    username='admin',
                    email='fverdugo.ro@gmail.com',  # Correo del administrador
                    password=hashed_password
                    # El modelo User actual no tiene un campo 'role' o 'is_admin'
                    # Si necesitas manejar roles, deberías agregar ese campo al modelo
                )
                db.session.add(admin)
                db.session.commit()
                print("Usuario administrador creado con éxito:")
                print("Email: fverdugo.ro@gmail.com")
                print("Contraseña: admin123")
            else:
                print("El usuario administrador ya existe en la base de datos")
        except Exception as e:
            db.session.rollback()
            print(f"Error al crear el usuario administrador: {e}")

        print("Database tables created successfully!")

if __name__ == "__main__":
    create_tables()
