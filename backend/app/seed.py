from sqlalchemy.orm import Session

from app.auth import hash_pin
from app.models import Categoria, User
from app.permissions import seed_default_permissions


def seed_data(db: Session):
    if db.query(User).count() > 0:
        return

    admin = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(admin)

    categorias = [
        Categoria(nombre="Panes", tipo="receta", margen_objetivo=60, orden=1),
        Categoria(nombre="Masas Madre", tipo="receta", margen_objetivo=60, orden=2),
        Categoria(nombre="Bollería", tipo="receta", margen_objetivo=55, orden=3),
        Categoria(nombre="Pastelería", tipo="receta", margen_objetivo=55, orden=4),
        Categoria(nombre="Harinas", tipo="ingrediente", orden=1),
        Categoria(nombre="Lácteos", tipo="ingrediente", orden=2),
        Categoria(nombre="Grasas", tipo="ingrediente", orden=3),
        Categoria(nombre="Azúcares", tipo="ingrediente", orden=4),
        Categoria(nombre="Levaduras y Mejorantes", tipo="ingrediente", orden=5),
        Categoria(nombre="Frutas y Frutos Secos", tipo="ingrediente", orden=6),
        Categoria(nombre="Otros", tipo="ingrediente", orden=7),
    ]
    db.add_all(categorias)
    db.commit()
    seed_default_permissions(db)
