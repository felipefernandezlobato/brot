import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, DATABASE_URL, SessionLocal, engine
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "sqlite" in DATABASE_URL:
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="BROT API", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:3003").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (  # noqa: E402
    auth,
    auth_cliente,
    catalogo,
    catalogo_admin,
    categorias,
    competencia,
    congelados,
    entregas_b2b,
    ingredientes,
    mermas,
    pedidos,
    pedidos_clientes,
    pedidos_clientes_admin,
    permisos,
    produccion,
    protocolos,
    proveedores,
    recetas,
    recurrentes,
    temperaturas,
)

app.include_router(auth.router)
app.include_router(auth_cliente.router)
app.include_router(permisos.router)
app.include_router(categorias.router)
app.include_router(ingredientes.router)
app.include_router(recetas.router)
app.include_router(mermas.router)
app.include_router(congelados.router)
app.include_router(catalogo.router)
app.include_router(catalogo_admin.router)
app.include_router(pedidos_clientes.router)
app.include_router(pedidos_clientes_admin.router)
app.include_router(recurrentes.router)
app.include_router(produccion.router)
app.include_router(proveedores.router)
app.include_router(pedidos.router)
app.include_router(entregas_b2b.clientes_router)
app.include_router(entregas_b2b.router)
app.include_router(competencia.router)
app.include_router(protocolos.router)
app.include_router(temperaturas.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
