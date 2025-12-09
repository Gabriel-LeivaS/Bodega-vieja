from index import db, User, app  # Importar la aplicación Flask
from werkzeug.security import generate_password_hash

# Crear un nuevo usuario
username = "admin"
password = "123456"

# Hashear la contraseña
hashed_password = generate_password_hash(password)

# Usar el contexto de la aplicación
with app.app_context():
    # Crear el usuario
    new_user = User(username=username, password=hashed_password)

    # Agregar el usuario a la base de datos
    db.session.add(new_user)
    db.session.commit()

    print(f"Usuario '{username}' agregado exitosamente.")