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

from app.routers import auth, auth_cliente, categorias, ingredientes, permisos, recetas  # noqa: E402

app.include_router(auth.router)
app.include_router(auth_cliente.router)
app.include_router(permisos.router)
app.include_router(categorias.router)
app.include_router(ingredientes.router)
app.include_router(recetas.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
