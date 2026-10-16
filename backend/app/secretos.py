"""La clave con la que se firman los tokens.

Vivia duplicada en auth.py y auth_cliente.py como

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

y ese valor por defecto esta escrito en un repo PUBLICO. Si la app se
desplegaba alguna vez sin la variable no fallaba: arrancaba y firmaba los
tokens con un secreto que cualquiera puede leer en GitHub, o sea que
cualquiera podia fabricarse un token de admin. Fallaba abierta.

Ahora falla cerrada: contra Postgres (produccion) exige la variable y se
niega a arrancar sin ella. Contra SQLite (local y tests) sigue habiendo un
valor por defecto, porque ahi no hay nada que proteger y pedir configuracion
para correr los tests solo estorba.
"""

import os

_FALLBACK_DEV = "dev-secret-change-me"


def get_secret_key() -> str:
    clave = os.getenv("SECRET_KEY")
    if clave:
        return clave

    url = os.getenv("DATABASE_URL", "")
    if url and not url.startswith("sqlite"):
        raise RuntimeError(
            "SECRET_KEY no esta definida y DATABASE_URL apunta a una base real. "
            "Sin ella los tokens se firmarian con un secreto publico. "
            "Configurala en las variables de entorno antes de arrancar."
        )
    return _FALLBACK_DEV
