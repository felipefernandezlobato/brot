# BROT Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a running BROT app with backend/frontend scaffolding, dual auth (employee PIN + customer email), configurable RBAC, and the first two domain modules (Ingredientes + Escandallos).

**Architecture:** Next.js 16 App Router frontend + FastAPI backend + Neon PostgreSQL. Single-page app pattern (all pages are `"use client"`, data fetched on mount). Mobile-first PWA. Spanish UI. British Racing Green branding (#004225). Follow the exact patterns established in the existing BRU apps (Escandallos, BRU1-BRU2, Checklists).

**Tech Stack:**
- Backend: FastAPI 0.115+, SQLAlchemy 2.0+, Alembic 1.16+, Pydantic 2.x, bcrypt 4.x, PyJWT 2.x, Python 3.12
- Frontend: Next.js 16, React 19, TypeScript 5, Tailwind CSS 4
- Database: PostgreSQL (Neon) / SQLite fallback

## Global Constraints

- Currency: ARS (Argentine Pesos), format: `$1.234,56`
- Language: All UI in Spanish
- Primary color: `#004225` (British Racing Green)
- Backend port (local): 8003
- Frontend port (local): 3003
- Employee token key: `brot_token`
- Customer token key: `brot_customer_token`
- All API routes under `/api/` prefix
- SQLAlchemy models use `Mapped` + `mapped_column` (modern style)
- Never use `router.push()` for tab switching — use `useState` + `window.history.replaceState()`
- Mobile touch targets: minimum 44px
- Font stack: EB Garamond (headings) + DM Sans (body)

---

## File Structure

### Backend (`backend/`)

```
backend/
  app/
    __init__.py
    main.py                    # FastAPI app, CORS, router mounting, startup seed
    database.py                # SQLAlchemy engine (SQLite/Postgres auto-detect)
    models.py                  # All SQLAlchemy ORM models
    schemas.py                 # Pydantic v2 request/response schemas
    auth.py                    # Employee PIN auth (bcrypt + JWT)
    auth_cliente.py            # Customer email auth (bcrypt + JWT)
    permissions.py             # RBAC permission checking
    seed.py                    # Idempotent seed data on first run
    routers/
      __init__.py
      auth.py                  # Employee login endpoints
      auth_cliente.py          # Customer login/register endpoints
      usuarios.py              # User CRUD (admin)
      permisos.py              # Permission management (admin)
      categorias.py            # Category CRUD
      ingredientes.py          # Ingredient CRUD + price history
      recetas.py               # Recipe CRUD + cost calculation
    services/
      __init__.py
      costes.py                # Recipe cost calculation engine
      conversiones.py          # Unit conversion (kg/g/mg, litro/ml/cl)
  alembic/
    env.py
    versions/
  alembic.ini
  start.sh
  requirements.txt
  .python-version
  tests/
    __init__.py
    conftest.py                # Test fixtures (in-memory SQLite, test client)
    test_auth.py
    test_auth_cliente.py
    test_permissions.py
    test_categorias.py
    test_ingredientes.py
    test_recetas.py
    test_costes.py
    test_conversiones.py
  data/                        # SQLite DB files (local dev only)
```

### Frontend (`frontend/`)

```
frontend/
  src/
    app/
      layout.tsx               # Root layout (fonts, metadata, PWA)
      page.tsx                 # Employee dashboard
      globals.css              # Tailwind + brand colors + safe areas
      login/page.tsx           # Employee PIN login
      cliente/
        login/page.tsx         # Customer email login
        registro/page.tsx      # Customer registration
      ingredientes/
        page.tsx               # Ingredient list
        [id]/page.tsx          # Ingredient detail/edit
        nuevo/page.tsx         # New ingredient form
      escandallos/
        page.tsx               # Recipe list
        [id]/page.tsx          # Recipe detail/edit + cost card
        nuevo/page.tsx         # New recipe form
      admin/
        layout.tsx             # Admin tab navigation
        equipo/page.tsx        # User management
        permisos/page.tsx      # RBAC config
        categorias/page.tsx    # Category management
    components/
      AppShell.tsx             # ToastProvider > AuthGuard > Shell > Nav
      AuthGuard.tsx            # Token validation + user loading
      CustomerAuthGuard.tsx    # Customer token validation
      Sidebar.tsx              # Desktop sidebar nav (green)
      BottomNav.tsx            # Mobile bottom tab bar
      Toast.tsx                # Toast notification system
      PinPad.tsx               # 4-digit PIN keypad
      PermissionGate.tsx       # Conditionally render based on RBAC
    lib/
      api.ts                   # apiFetch<T> with employee auth
      api-cliente.ts           # apiFetch<T> with customer auth
      types.ts                 # TypeScript interfaces
      format.ts                # formatARS, formatDate helpers
      permissions.ts           # usePermission hook
  public/
    manifest.json              # PWA manifest
    icons/                     # PWA icons
  next.config.ts
  package.json
  tsconfig.json
  postcss.config.mjs
```

---

## Task 1: Backend Scaffolding

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/.python-version`
- Create: `backend/start.sh`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/.gitkeep`
- Create: `backend/data/.gitkeep`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `database.py` exports `Base`, `engine`, `SessionLocal`, `get_db`
- Produces: `main.py` exports `app` (FastAPI instance)
- Produces: `conftest.py` exports `client` and `db` pytest fixtures

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.3
sqlalchemy==2.0.41
alembic==1.16.2
pydantic==2.11.3
psycopg2-binary==2.9.10
bcrypt==4.3.0
pyjwt==2.10.1
python-multipart==0.0.20
httpx==0.28.1
pytest==8.3.5
```

- [ ] **Step 2: Create .python-version**

```
3.12
```

- [ ] **Step 3: Create database.py**

```python
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")


class Base(DeclarativeBase):
    pass


if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Create main.py (minimal)**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Create start.sh**

```bash
#!/bin/bash
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 6: Create alembic.ini and alembic/env.py**

`alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///data/app.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`alembic/env.py`:
```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base
from app.models import *  # noqa: F401,F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        url=url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Create conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_TEST_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 8: Create __init__.py files and .gitkeep files**

Empty `__init__.py` in `backend/app/`, `backend/app/routers/`, `backend/app/services/`, `backend/tests/`.
Empty `.gitkeep` in `backend/alembic/versions/`, `backend/data/`.

- [ ] **Step 9: Verify backend starts**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8003
# Visit http://localhost:8003/api/health → {"status": "ok"}
```

- [ ] **Step 10: Run tests**

```bash
cd backend
pytest tests/ -v
```
Expected: no tests collected yet, but no import errors.

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffolding — FastAPI, SQLAlchemy, Alembic, test fixtures"
```

---

## Task 2: Frontend Scaffolding

**Files:**
- Create: entire `frontend/` directory via `npx create-next-app`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/components/Toast.tsx`
- Create: `frontend/public/manifest.json`

**Interfaces:**
- Produces: `api.ts` exports `apiFetch<T>(path, options?)` for employee-authed API calls
- Produces: `format.ts` exports `formatARS(n)`, `formatDate(d)`, `formatDateTime(d)`
- Produces: `Toast.tsx` exports `ToastProvider`, `useToast()` hook

- [ ] **Step 1: Create Next.js app**

```bash
cd /Users/fernaf41/projects/Tests/BROT
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --no-import-alias \
  --turbopack
```

- [ ] **Step 2: Update globals.css with BROT branding**

Replace `frontend/src/app/globals.css` with:

```css
@import "tailwindcss";

@theme {
  --color-brot: #004225;
  --color-brot-dark: #00331C;
  --color-brot-light: #005C34;
  --color-cream: #F5F0E8;
  --color-cream-dark: #E8DFD3;
  --color-warm-gray: #6B5E52;
  --color-text: #1A1A1A;
  --font-garamond: var(--font-eb-garamond);
  --font-sans: var(--font-dm-sans);
}

html {
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-cream);
}

input, select, textarea {
  font-size: max(16px, 1rem);
}
```

- [ ] **Step 3: Create layout.tsx with fonts and PWA metadata**

```tsx
import type { Metadata, Viewport } from "next";
import { EB_Garamond, DM_Sans } from "next/font/google";
import "./globals.css";

const garamond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-eb-garamond",
});
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "BROT — La Panadería",
  description: "Sistema de gestión del obrador",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#004225",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={`${garamond.variable} ${dmSans.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Create placeholder page.tsx**

```tsx
export default function Home() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <h1 className="font-[family-name:var(--font-garamond)] text-4xl text-brot">
        BROT
      </h1>
    </div>
  );
}
```

- [ ] **Step 5: Create api.ts**

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const token = localStorage.getItem("brot_token");
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("brot_token");
    window.location.href = "/login";
    throw new Error("No autorizado");
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 6: Create api-cliente.ts**

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

export async function apiClienteFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const token = localStorage.getItem("brot_customer_token");
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("brot_customer_token");
    window.location.href = "/cliente/login";
    throw new Error("No autorizado");
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 7: Create format.ts**

```typescript
export function formatARS(amount: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
```

- [ ] **Step 8: Create types.ts (initial)**

```typescript
export interface User {
  id: number;
  name: string;
  role: "admin" | "staff";
}

export interface Cliente {
  id: number;
  email: string;
  nombre: string;
  telefono?: string;
  direccion?: string;
}

export interface Categoria {
  id: number;
  nombre: string;
  tipo: "ingrediente" | "receta";
  margen_objetivo?: number;
  orden?: number;
}

export interface Permission {
  id: number;
  role: string;
  module: string;
  action: string;
  allowed: boolean;
}
```

- [ ] **Step 9: Create Toast.tsx**

```tsx
"use client";

import { createContext, useCallback, useContext, useState } from "react";

type ToastType = "success" | "error";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

const ToastContext = createContext<{
  toast: (message: string, type?: ToastType) => void;
}>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: ToastType = "success") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-20 md:bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() =>
              setToasts((prev) => prev.filter((x) => x.id !== t.id))
            }
            className={`px-4 py-2 rounded-lg text-white text-sm shadow-lg cursor-pointer animate-[slideIn_0.2s_ease-out] ${
              t.type === "success" ? "bg-brot" : "bg-red-600"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

- [ ] **Step 10: Create manifest.json**

```json
{
  "name": "BROT — La Panadería",
  "short_name": "BROT",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#F5F0E8",
  "theme_color": "#004225",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- [ ] **Step 11: Verify frontend starts**

```bash
cd frontend
npm run dev -- -p 3003
# Visit http://localhost:3003 → BROT heading with green text on cream background
```

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffolding — Next.js, Tailwind, BROT branding, API client, Toast"
```

---

## Task 3: Database Models

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`

**Interfaces:**
- Consumes: `database.py` → `Base`
- Produces: All SQLAlchemy models used by routers: `User`, `Cliente`, `Categoria`, `Ingrediente`, `HistorialPrecio`, `Receta`, `LineaReceta`, `Permission`
- Produces: All Pydantic schemas used by routers

- [ ] **Step 1: Write models.py**

```python
from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    pin_hash: Mapped[str] = mapped_column(sa.String(200))
    role: Mapped[str] = mapped_column(sa.String(20), default="staff")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(200))
    nombre: Mapped[str] = mapped_column(sa.String(200))
    telefono: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(sa.String(20))
    module: Mapped[str] = mapped_column(sa.String(50))
    action: Mapped[str] = mapped_column(sa.String(20))
    allowed: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    __table_args__ = (
        UniqueConstraint("role", "module", "action", name="uq_permission"),
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(100), unique=True)
    tipo: Mapped[str] = mapped_column(sa.String(20))
    margen_objetivo: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    orden: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True, default=0)

    ingredientes: Mapped[list["Ingrediente"]] = relationship(back_populates="categoria_rel")
    recetas: Mapped[list["Receta"]] = relationship(back_populates="categoria_rel")


class Ingrediente(Base):
    __tablename__ = "ingredientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    unidad_compra: Mapped[str] = mapped_column(sa.String(20))
    cantidad_compra: Mapped[float] = mapped_column(sa.Float)
    precio_compra: Mapped[float] = mapped_column(sa.Float)
    unidad_uso: Mapped[str] = mapped_column(sa.String(20))
    merma_porcentaje: Mapped[float] = mapped_column(sa.Float, default=0.0)
    proveedor: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    activo: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    fecha_actualizacion: Mapped[date] = mapped_column(sa.Date, default=date.today)

    categoria_rel: Mapped["Categoria"] = relationship(back_populates="ingredientes")
    historial_precios: Mapped[list["HistorialPrecio"]] = relationship(
        back_populates="ingrediente_rel", cascade="all, delete-orphan"
    )
    lineas_receta: Mapped[list["LineaReceta"]] = relationship(
        back_populates="ingrediente_rel", foreign_keys="LineaReceta.ingrediente_id"
    )


class HistorialPrecio(Base):
    __tablename__ = "historial_precios"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingrediente_id: Mapped[int] = mapped_column(ForeignKey("ingredientes.id"))
    precio_anterior: Mapped[float] = mapped_column(sa.Float)
    precio_nuevo: Mapped[float] = mapped_column(sa.Float)
    fecha_cambio: Mapped[date] = mapped_column(sa.Date, default=date.today)

    ingrediente_rel: Mapped["Ingrediente"] = relationship(back_populates="historial_precios")


class Receta(Base):
    __tablename__ = "recetas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    porciones_por_lote: Mapped[float] = mapped_column(sa.Float, default=1)
    precio_venta: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    es_subreceta: Mapped[bool] = mapped_column(default=False)
    unidad_rendimiento: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    fecha_modificacion: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria_rel: Mapped["Categoria"] = relationship(back_populates="recetas")
    lineas: Mapped[list["LineaReceta"]] = relationship(
        back_populates="receta_rel", cascade="all, delete-orphan", foreign_keys="LineaReceta.receta_id"
    )
    lineas_como_subreceta: Mapped[list["LineaReceta"]] = relationship(
        back_populates="subreceta_rel", foreign_keys="LineaReceta.subreceta_id"
    )


class LineaReceta(Base):
    __tablename__ = "lineas_receta"

    id: Mapped[int] = mapped_column(primary_key=True)
    receta_id: Mapped[int] = mapped_column(ForeignKey("recetas.id"))
    ingrediente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingredientes.id"), nullable=True)
    subreceta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    cantidad: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))

    receta_rel: Mapped["Receta"] = relationship(back_populates="lineas", foreign_keys=[receta_id])
    ingrediente_rel: Mapped[Optional["Ingrediente"]] = relationship(
        back_populates="lineas_receta", foreign_keys=[ingrediente_id]
    )
    subreceta_rel: Mapped[Optional["Receta"]] = relationship(
        back_populates="lineas_como_subreceta", foreign_keys=[subreceta_id]
    )


class PrecioCompetencia(Base):
    __tablename__ = "precios_competencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    receta_id: Mapped[int] = mapped_column(ForeignKey("recetas.id"))
    competidor_nombre: Mapped[str] = mapped_column(sa.String(200))
    precio: Mapped[float] = mapped_column(sa.Float)
    fecha_registro: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    receta_rel: Mapped["Receta"] = relationship()
```

- [ ] **Step 2: Write schemas.py**

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# --- Auth ---
class LoginRequest(BaseModel):
    name: str
    pin: str

class TokenResponse(BaseModel):
    token: str

class UserOut(BaseModel):
    id: int
    name: str
    role: str

class UserCreate(BaseModel):
    name: str
    pin: str
    role: str = "staff"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    pin: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


# --- Cliente Auth ---
class ClienteRegistro(BaseModel):
    email: str
    password: str
    nombre: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None

class ClienteLogin(BaseModel):
    email: str
    password: str

class ClienteOut(BaseModel):
    id: int
    email: str
    nombre: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None


# --- Permissions ---
class PermissionOut(BaseModel):
    id: int
    role: str
    module: str
    action: str
    allowed: bool

class PermissionUpdate(BaseModel):
    allowed: bool


# --- Categorias ---
class CategoriaCreate(BaseModel):
    nombre: str
    tipo: str
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = 0

class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = None

class CategoriaOut(BaseModel):
    id: int
    nombre: str
    tipo: str
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = None


# --- Ingredientes ---
class IngredienteCreate(BaseModel):
    nombre: str
    categoria_id: int
    unidad_compra: str
    cantidad_compra: float
    precio_compra: float
    unidad_uso: str
    merma_porcentaje: float = 0.0
    proveedor: Optional[str] = None
    notas: Optional[str] = None

class IngredienteUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    unidad_compra: Optional[str] = None
    cantidad_compra: Optional[float] = None
    precio_compra: Optional[float] = None
    unidad_uso: Optional[str] = None
    merma_porcentaje: Optional[float] = None
    proveedor: Optional[str] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None

class IngredienteOut(BaseModel):
    id: int
    nombre: str
    categoria_id: int
    categoria_nombre: str
    unidad_compra: str
    cantidad_compra: float
    precio_compra: float
    unidad_uso: str
    merma_porcentaje: float
    proveedor: Optional[str] = None
    notas: Optional[str] = None
    activo: bool
    costo_por_unidad_uso: float
    fecha_actualizacion: date

class HistorialPrecioOut(BaseModel):
    id: int
    ingrediente_id: int
    precio_anterior: float
    precio_nuevo: float
    fecha_cambio: date


# --- Recetas ---
class LineaRecetaIn(BaseModel):
    ingrediente_id: Optional[int] = None
    subreceta_id: Optional[int] = None
    cantidad: float
    unidad: str

class RecetaCreate(BaseModel):
    nombre: str
    categoria_id: int
    porciones_por_lote: float = 1
    precio_venta: Optional[float] = None
    es_subreceta: bool = False
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    lineas: list[LineaRecetaIn] = []

class RecetaUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    porciones_por_lote: Optional[float] = None
    precio_venta: Optional[float] = None
    es_subreceta: Optional[bool] = None
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[list[LineaRecetaIn]] = None

class LineaRecetaOut(BaseModel):
    id: int
    ingrediente_id: Optional[int] = None
    subreceta_id: Optional[int] = None
    cantidad: float
    unidad: str
    nombre: str
    costo_linea: float

class RecetaOut(BaseModel):
    id: int
    nombre: str
    categoria_id: int
    categoria_nombre: str
    porciones_por_lote: float
    precio_venta: Optional[float] = None
    es_subreceta: bool
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    costo_total: float
    costo_por_porcion: float
    margen: Optional[float] = None
    multi: Optional[float] = None
    lineas: list[LineaRecetaOut] = []


# --- Precio Competencia ---
class PrecioCompetenciaCreate(BaseModel):
    receta_id: int
    competidor_nombre: str
    precio: float
    notas: Optional[str] = None

class PrecioCompetenciaOut(BaseModel):
    id: int
    receta_id: int
    competidor_nombre: str
    precio: float
    fecha_registro: date
    notas: Optional[str] = None
```

- [ ] **Step 3: Create initial alembic migration**

```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "initial models"
alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/alembic/
git commit -m "feat: database models and Pydantic schemas — User, Cliente, Permission, Categoria, Ingrediente, Receta"
```

---

## Task 4: Employee Auth (Backend)

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/routers/usuarios.py`
- Create: `backend/app/seed.py`
- Modify: `backend/app/main.py` — mount routers, add startup seed
- Create: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `models.User`, `schemas.LoginRequest`, `schemas.TokenResponse`, `schemas.UserOut`
- Produces: `auth.py` exports `hash_pin(pin)`, `verify_pin(pin, hash)`, `create_token(user_id, role)`, `get_current_user(db, token)`, `require_admin(db, token)`

- [ ] **Step 1: Write test_auth.py**

```python
from app.models import User
from app.auth import hash_pin


def test_login_success(client, db):
    user = User(name="Test", pin_hash=hash_pin("1234"), role="admin")
    db.add(user)
    db.commit()

    res = client.post("/api/auth/login", json={"name": "Test", "pin": "1234"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_pin(client, db):
    user = User(name="Test", pin_hash=hash_pin("1234"), role="admin")
    db.add(user)
    db.commit()

    res = client.post("/api/auth/login", json={"name": "Test", "pin": "0000"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"name": "Ghost", "pin": "1234"})
    assert res.status_code == 401


def test_me_with_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()

    login = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    token = login.json()["token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Admin"
    assert res.json()["role"] == "admin"


def test_me_without_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_users_list_public(client, db):
    user = User(name="Ana", pin_hash=hash_pin("1111"), role="staff")
    db.add(user)
    db.commit()

    res = client.get("/api/auth/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 1
    assert users[0]["name"] == "Ana"
    assert "pin_hash" not in users[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_auth.py -v
```
Expected: ImportError or ModuleNotFoundError (auth.py doesn't exist yet).

- [ ] **Step 3: Write auth.py**

```python
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


def create_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return user
```

- [ ] **Step 4: Write routers/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_pin, verify_pin
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()
    return [{"id": u.id, "name": u.name} for u in users]


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.name, User.is_active == True).first()
    if not user or not verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": create_token(user.id, user.role)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "role": user.role}
```

- [ ] **Step 5: Write seed.py**

```python
from sqlalchemy.orm import Session

from app.auth import hash_pin
from app.models import Categoria, User


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
```

- [ ] **Step 6: Update main.py to mount routers and run seed**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import SessionLocal
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
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

from app.routers import auth  # noqa: E402

app.include_router(auth.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest tests/test_auth.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/auth.py backend/app/routers/auth.py backend/app/seed.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: employee PIN auth — login, me, user list, seed admin"
```

---

## Task 5: Customer Auth (Backend)

**Files:**
- Create: `backend/app/auth_cliente.py`
- Create: `backend/app/routers/auth_cliente.py`
- Modify: `backend/app/main.py` — mount customer auth router
- Create: `backend/tests/test_auth_cliente.py`

**Interfaces:**
- Consumes: `models.Cliente`, `schemas.ClienteRegistro`, `schemas.ClienteLogin`, `schemas.ClienteOut`
- Produces: `auth_cliente.py` exports `hash_password(pw)`, `verify_password(pw, hash)`, `create_cliente_token(cliente_id)`, `get_current_cliente(db, token)`

- [ ] **Step 1: Write test_auth_cliente.py**

```python
def test_register_cliente(client):
    res = client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com",
        "password": "secreto123",
        "nombre": "Juan",
        "telefono": "+5491155551234",
    })
    assert res.status_code == 201
    assert res.json()["email"] == "test@example.com"
    assert "password" not in res.json()


def test_register_duplicate_email(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "abc", "nombre": "A"
    })
    res = client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "def", "nombre": "B"
    })
    assert res.status_code == 409


def test_login_cliente(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "wrong"
    })
    assert res.status_code == 401


def test_cliente_me(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    login = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    token = login.json()["token"]
    res = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["nombre"] == "Juan"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_auth_cliente.py -v
```

- [ ] **Step 3: Write auth_cliente.py**

```python
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cliente

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_cliente_token(cliente_id: int) -> str:
    payload = {
        "cliente_id": cliente_id,
        "type": "cliente",
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_cliente(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Cliente:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    if payload.get("type") != "cliente":
        raise HTTPException(status_code=401, detail="Token de tipo incorrecto")

    cliente = db.query(Cliente).filter(Cliente.id == payload["cliente_id"]).first()
    if not cliente or not cliente.is_active:
        raise HTTPException(status_code=401, detail="Cliente no encontrado")
    return cliente
```

- [ ] **Step 4: Write routers/auth_cliente.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_cliente import create_cliente_token, get_current_cliente, hash_password, verify_password
from app.database import get_db
from app.models import Cliente
from app.schemas import ClienteLogin, ClienteOut, ClienteRegistro, TokenResponse

router = APIRouter(prefix="/api/auth/cliente", tags=["auth-cliente"])


@router.post("/registro", response_model=ClienteOut, status_code=201)
def registrar(data: ClienteRegistro, db: Session = Depends(get_db)):
    existing = db.query(Cliente).filter(Cliente.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ya registrado")
    cliente = Cliente(
        email=data.email,
        password_hash=hash_password(data.password),
        nombre=data.nombre,
        telefono=data.telefono,
        direccion=data.direccion,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return ClienteOut(id=cliente.id, email=cliente.email, nombre=cliente.nombre,
                      telefono=cliente.telefono, direccion=cliente.direccion)


@router.post("/login", response_model=TokenResponse)
def login(data: ClienteLogin, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.email == data.email, Cliente.is_active == True).first()
    if not cliente or not verify_password(data.password, cliente.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": create_cliente_token(cliente.id)}


@router.get("/me", response_model=ClienteOut)
def me(cliente: Cliente = Depends(get_current_cliente)):
    return ClienteOut(id=cliente.id, email=cliente.email, nombre=cliente.nombre,
                      telefono=cliente.telefono, direccion=cliente.direccion)
```

- [ ] **Step 5: Mount router in main.py**

Add to `main.py` after the existing router import:
```python
from app.routers import auth_cliente  # noqa: E402
app.include_router(auth_cliente.router)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest tests/test_auth_cliente.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/auth_cliente.py backend/app/routers/auth_cliente.py backend/app/main.py backend/tests/test_auth_cliente.py
git commit -m "feat: customer email auth — register, login, me"
```

---

## Task 6: RBAC Permission System

**Files:**
- Create: `backend/app/permissions.py`
- Create: `backend/app/routers/permisos.py`
- Modify: `backend/app/seed.py` — seed default permissions
- Modify: `backend/app/main.py` — mount permissions router
- Create: `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: `models.Permission`, `auth.get_current_user`, `auth.require_admin`
- Produces: `permissions.py` exports `require_permission(module, action)` — a FastAPI dependency factory
- Produces: `GET /api/permisos` — returns all permissions for the current user's role

- [ ] **Step 1: Write test_permissions.py**

```python
from app.auth import hash_pin
from app.models import Permission, User


def _login(client, db, role="admin"):
    user = User(name=f"User-{role}", pin_hash=hash_pin("1234"), role=role)
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": f"User-{role}", "pin": "1234"})
    return res.json()["token"]


def test_admin_bypasses_permissions(client, db):
    token = _login(client, db, "admin")
    res = client.get("/api/permisos", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_staff_denied_without_permission(client, db):
    token = _login(client, db, "staff")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=False)
    db.add(perm)
    db.commit()

    res = client.get("/api/permisos/check/ingredientes/view",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is False


def test_staff_allowed_with_permission(client, db):
    token = _login(client, db, "staff")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=True)
    db.add(perm)
    db.commit()

    res = client.get("/api/permisos/check/ingredientes/view",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is True


def test_admin_can_update_permissions(client, db):
    token = _login(client, db, "admin")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=True)
    db.add(perm)
    db.commit()

    res = client.put(f"/api/permisos/{perm.id}",
                     json={"allowed": False},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_permissions.py -v
```

- [ ] **Step 3: Write permissions.py**

```python
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Permission, User

MODULES = [
    "ingredientes", "categorias", "recetas", "stock", "congelados",
    "mermas", "produccion", "pedidos_proveedores", "pedidos_clientes",
    "entregas_proveedor", "entregas_b2b", "protocolos", "temperaturas",
    "competencia", "equipo", "permisos", "importar", "backup",
]

ACTIONS = ["view", "create", "edit", "delete"]


def check_permission(db: Session, role: str, module: str, action: str) -> bool:
    if role == "admin":
        return True
    perm = db.query(Permission).filter(
        Permission.role == role,
        Permission.module == module,
        Permission.action == action,
    ).first()
    if not perm:
        return False
    return perm.allowed


def require_permission(module: str, action: str):
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not check_permission(db, user.role, module, action):
            raise HTTPException(
                status_code=403,
                detail=f"Sin permiso: {module}/{action}",
            )
        return user
    return Depends(dependency)


def seed_default_permissions(db: Session):
    if db.query(Permission).count() > 0:
        return
    for module in MODULES:
        for action in ACTIONS:
            perm = Permission(role="staff", module=module, action=action, allowed=True)
            db.add(perm)
    db.commit()
```

- [ ] **Step 4: Write routers/permisos.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Permission, User
from app.permissions import check_permission
from app.schemas import PermissionOut, PermissionUpdate

router = APIRouter(prefix="/api/permisos", tags=["permisos"])


@router.get("", response_model=list[PermissionOut])
def list_permissions(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(Permission).order_by(Permission.module, Permission.action).all()


@router.get("/check/{module}/{action}")
def check(module: str, action: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = check_permission(db, user.role, module, action)
    return {"module": module, "action": action, "allowed": allowed}


@router.put("/{permission_id}", response_model=PermissionOut)
def update_permission(
    permission_id: int,
    data: PermissionUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    perm.allowed = data.allowed
    db.commit()
    db.refresh(perm)
    return perm


@router.get("/mi-rol")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "admin":
        return {"role": "admin", "all_allowed": True}
    perms = db.query(Permission).filter(Permission.role == user.role).all()
    return {
        "role": user.role,
        "permissions": {f"{p.module}.{p.action}": p.allowed for p in perms},
    }
```

- [ ] **Step 5: Update seed.py to seed permissions**

Add to `seed.py` after user/category seeding:
```python
from app.permissions import seed_default_permissions

def seed_data(db: Session):
    # ... existing user/category seeding ...
    seed_default_permissions(db)
```

- [ ] **Step 6: Mount router in main.py**

```python
from app.routers import permisos  # noqa: E402
app.include_router(permisos.router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest tests/test_permissions.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/permissions.py backend/app/routers/permisos.py backend/app/seed.py backend/app/main.py backend/tests/test_permissions.py
git commit -m "feat: configurable RBAC — permission model, check dependency, admin UI endpoint"
```

---

## Task 7: Unit Conversion Service + Cost Calculation Engine

**Files:**
- Create: `backend/app/services/conversiones.py`
- Create: `backend/app/services/costes.py`
- Create: `backend/tests/test_conversiones.py`
- Create: `backend/tests/test_costes.py`

**Interfaces:**
- Produces: `conversiones.py` exports `convertir(cantidad, de_unidad, a_unidad) -> float`
- Produces: `costes.py` exports `costo_por_unidad_uso(ingrediente) -> float`, `costo_receta(receta, db) -> (costo_total, costo_por_porcion)`, `costo_linea(linea, db) -> float`

- [ ] **Step 1: Write test_conversiones.py**

```python
import pytest
from app.services.conversiones import convertir


def test_kg_to_g():
    assert convertir(1, "kg", "g") == 1000


def test_g_to_kg():
    assert convertir(500, "g", "kg") == 0.5


def test_litro_to_ml():
    assert convertir(1, "litro", "ml") == 1000


def test_same_unit():
    assert convertir(5, "kg", "kg") == 5


def test_cross_family_raises():
    with pytest.raises(ValueError):
        convertir(1, "kg", "litro")


def test_unidad_to_unidad():
    assert convertir(3, "unidad", "unidad") == 3
```

- [ ] **Step 2: Write conversiones.py**

```python
CONVERSIONES = {
    ("kg", "g"): 1000,
    ("kg", "mg"): 1_000_000,
    ("g", "mg"): 1000,
    ("g", "kg"): 0.001,
    ("mg", "g"): 0.001,
    ("mg", "kg"): 0.000001,
    ("litro", "ml"): 1000,
    ("litro", "cl"): 100,
    ("ml", "litro"): 0.001,
    ("ml", "cl"): 0.1,
    ("cl", "ml"): 10,
    ("cl", "litro"): 0.01,
}

FAMILIAS = {
    "kg": "peso", "g": "peso", "mg": "peso",
    "litro": "volumen", "ml": "volumen", "cl": "volumen",
    "unidad": "unidad",
}


def convertir(cantidad: float, de_unidad: str, a_unidad: str) -> float:
    if de_unidad == a_unidad:
        return cantidad

    fam_de = FAMILIAS.get(de_unidad)
    fam_a = FAMILIAS.get(a_unidad)

    if not fam_de or not fam_a:
        raise ValueError(f"Unidad desconocida: {de_unidad} o {a_unidad}")
    if fam_de != fam_a:
        raise ValueError(f"No se puede convertir {de_unidad} ({fam_de}) a {a_unidad} ({fam_a})")

    factor = CONVERSIONES.get((de_unidad, a_unidad))
    if factor is None:
        raise ValueError(f"Conversión no definida: {de_unidad} → {a_unidad}")

    return cantidad * factor
```

- [ ] **Step 3: Run conversion tests**

```bash
cd backend && pytest tests/test_conversiones.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 4: Write test_costes.py**

```python
from app.models import Categoria, Ingrediente, LineaReceta, Receta
from app.services.costes import costo_por_unidad_uso, costo_receta


def test_costo_por_unidad_uso_simple(db):
    cat = Categoria(nombre="Test", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=500, unidad_uso="g", merma_porcentaje=0,
    )
    db.add(ing)
    db.flush()
    cost = costo_por_unidad_uso(ing)
    assert cost == pytest.approx(0.5)  # 500 ARS / 1000g


def test_costo_por_unidad_uso_with_merma(db):
    cat = Categoria(nombre="Test", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Manteca", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=1000, unidad_uso="g", merma_porcentaje=10,
    )
    db.add(ing)
    db.flush()
    cost = costo_por_unidad_uso(ing)
    assert cost == pytest.approx(1000 / 1000 / 0.9)


def test_costo_receta(db):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add(cat_r)
    db.flush()

    harina = Ingrediente(
        nombre="Harina", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=500, unidad_uso="g", merma_porcentaje=0,
    )
    db.add(harina)
    db.flush()

    receta = Receta(nombre="Pan", categoria_id=cat_r.id, porciones_por_lote=10)
    db.add(receta)
    db.flush()

    linea = LineaReceta(receta_id=receta.id, ingrediente_id=harina.id, cantidad=1000, unidad="g")
    db.add(linea)
    db.commit()

    total, por_porcion = costo_receta(receta, db)
    assert total == pytest.approx(500.0)  # 1000g × 0.5 ARS/g
    assert por_porcion == pytest.approx(50.0)  # 500 / 10 porciones


import pytest
```

- [ ] **Step 5: Write costes.py**

```python
from sqlalchemy.orm import Session

from app.models import Ingrediente, LineaReceta, Receta
from app.services.conversiones import convertir


def costo_por_unidad_uso(ing: Ingrediente) -> float:
    cantidad_en_uso = convertir(ing.cantidad_compra, ing.unidad_compra, ing.unidad_uso)
    cpu = ing.precio_compra / cantidad_en_uso
    if ing.merma_porcentaje > 0:
        cpu = cpu / (1 - ing.merma_porcentaje / 100)
    return cpu


def costo_linea(linea: LineaReceta, db: Session, visited: set[int] | None = None) -> float:
    if visited is None:
        visited = set()

    if linea.ingrediente_id:
        ing = linea.ingrediente_rel or db.query(Ingrediente).get(linea.ingrediente_id)
        cpu = costo_por_unidad_uso(ing)
        cantidad_convertida = convertir(linea.cantidad, linea.unidad, ing.unidad_uso)
        return cpu * cantidad_convertida

    if linea.subreceta_id:
        if linea.subreceta_id in visited:
            return 0
        sub = linea.subreceta_rel or db.query(Receta).get(linea.subreceta_id)
        total_sub, _ = costo_receta(sub, db, visited)
        costo_por_porcion_sub = total_sub / sub.porciones_por_lote
        if sub.unidad_rendimiento and linea.unidad != sub.unidad_rendimiento:
            cantidad = convertir(linea.cantidad, linea.unidad, sub.unidad_rendimiento)
        else:
            cantidad = linea.cantidad
        return costo_por_porcion_sub * cantidad

    return 0


def costo_receta(receta: Receta, db: Session, visited: set[int] | None = None) -> tuple[float, float]:
    if visited is None:
        visited = set()
    visited.add(receta.id)

    lineas = receta.lineas or db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
    total = sum(costo_linea(l, db, visited) for l in lineas)
    por_porcion = total / receta.porciones_por_lote if receta.porciones_por_lote else total
    return total, por_porcion
```

- [ ] **Step 6: Run cost tests**

```bash
cd backend && pytest tests/test_costes.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ backend/tests/test_conversiones.py backend/tests/test_costes.py
git commit -m "feat: unit conversion + recipe cost engine — supports sub-recipes, merma, cycle detection"
```

---

## Task 8: Categorías CRUD

**Files:**
- Create: `backend/app/routers/categorias.py`
- Modify: `backend/app/main.py` — mount router
- Create: `backend/tests/test_categorias.py`

**Interfaces:**
- Consumes: `models.Categoria`, `schemas.CategoriaCreate/Update/Out`, `permissions.require_permission`
- Produces: CRUD endpoints at `/api/categorias`

- [ ] **Step 1: Write test_categorias.py**

```python
from app.auth import hash_pin
from app.models import User


def _admin_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    return res.json()["token"]


def test_create_categoria(client, db):
    token = _admin_token(client, db)
    res = client.post("/api/categorias", json={
        "nombre": "Panes", "tipo": "receta", "margen_objetivo": 60
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert res.json()["nombre"] == "Panes"


def test_list_categorias(client, db):
    token = _admin_token(client, db)
    client.post("/api/categorias", json={"nombre": "A", "tipo": "ingrediente"},
                headers={"Authorization": f"Bearer {token}"})
    client.post("/api/categorias", json={"nombre": "B", "tipo": "receta"},
                headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/categorias", headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 2


def test_list_categorias_filter_tipo(client, db):
    token = _admin_token(client, db)
    client.post("/api/categorias", json={"nombre": "A", "tipo": "ingrediente"},
                headers={"Authorization": f"Bearer {token}"})
    client.post("/api/categorias", json={"nombre": "B", "tipo": "receta"},
                headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/categorias?tipo=ingrediente",
                     headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1


def test_update_categoria(client, db):
    token = _admin_token(client, db)
    created = client.post("/api/categorias", json={"nombre": "Old", "tipo": "receta"},
                          headers={"Authorization": f"Bearer {token}"})
    cat_id = created.json()["id"]
    res = client.put(f"/api/categorias/{cat_id}", json={"nombre": "New"},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.json()["nombre"] == "New"


def test_delete_categoria(client, db):
    token = _admin_token(client, db)
    created = client.post("/api/categorias", json={"nombre": "Del", "tipo": "receta"},
                          headers={"Authorization": f"Bearer {token}"})
    cat_id = created.json()["id"]
    res = client.delete(f"/api/categorias/{cat_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_categorias.py -v
```

- [ ] **Step 3: Write routers/categorias.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Categoria, Ingrediente, Receta, User
from app.permissions import require_permission
from app.schemas import CategoriaCreate, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/api/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoriaOut])
def list_categorias(
    tipo: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Categoria)
    if tipo:
        q = q.filter(Categoria.tipo == tipo)
    return q.order_by(Categoria.orden, Categoria.nombre).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def create_categoria(
    data: CategoriaCreate,
    user: User = require_permission("categorias", "create"),
    db: Session = Depends(get_db),
):
    cat = Categoria(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{cat_id}", response_model=CategoriaOut)
def update_categoria(
    cat_id: int,
    data: CategoriaUpdate,
    user: User = require_permission("categorias", "edit"),
    db: Session = Depends(get_db),
):
    cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(cat, key, val)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}")
def delete_categoria(
    cat_id: int,
    user: User = require_permission("categorias", "delete"),
    db: Session = Depends(get_db),
):
    cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    if db.query(Ingrediente).filter(Ingrediente.categoria_id == cat_id).count() > 0:
        raise HTTPException(status_code=409, detail="Categoría tiene ingredientes asociados")
    if db.query(Receta).filter(Receta.categoria_id == cat_id).count() > 0:
        raise HTTPException(status_code=409, detail="Categoría tiene recetas asociadas")
    db.delete(cat)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Mount router in main.py**

```python
from app.routers import categorias  # noqa: E402
app.include_router(categorias.router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_categorias.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/categorias.py backend/app/main.py backend/tests/test_categorias.py
git commit -m "feat: categorías CRUD with RBAC and referential integrity guards"
```

---

## Task 9: Ingredientes CRUD + Price History

**Files:**
- Create: `backend/app/routers/ingredientes.py`
- Modify: `backend/app/main.py` — mount router
- Create: `backend/tests/test_ingredientes.py`

**Interfaces:**
- Consumes: `models.Ingrediente/HistorialPrecio`, `schemas.IngredienteCreate/Update/Out`, `services.costes.costo_por_unidad_uso`, `permissions.require_permission`
- Produces: CRUD + price history endpoints at `/api/ingredientes`

- [ ] **Step 1: Write test_ingredientes.py**

```python
from app.auth import hash_pin
from app.models import Categoria, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, cat.id


def test_create_ingrediente(client, db):
    token, cat_id = _setup(client, db)
    res = client.post("/api/ingredientes", json={
        "nombre": "Harina 000", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 25,
        "precio_compra": 5000, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert res.json()["nombre"] == "Harina 000"
    assert "costo_por_unidad_uso" in res.json()


def test_list_ingredientes(client, db):
    token, cat_id = _setup(client, db)
    client.post("/api/ingredientes", json={
        "nombre": "A", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 100, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/ingredientes", headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1


def test_update_precio_creates_historial(client, db):
    token, cat_id = _setup(client, db)
    created = client.post("/api/ingredientes", json={
        "nombre": "Manteca", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 1000, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    ing_id = created.json()["id"]

    client.put(f"/api/ingredientes/{ing_id}", json={"precio_compra": 1200},
               headers={"Authorization": f"Bearer {token}"})

    res = client.get(f"/api/ingredientes/{ing_id}/historial",
                     headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1
    assert res.json()[0]["precio_anterior"] == 1000
    assert res.json()[0]["precio_nuevo"] == 1200


def test_delete_blocked_if_in_recipe(client, db):
    token, cat_id = _setup(client, db)
    # Create ingredient
    ing = client.post("/api/ingredientes", json={
        "nombre": "X", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 100, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    ing_id = ing.json()["id"]

    # Create recipe category + recipe using the ingredient
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add(cat_r)
    db.commit()
    from app.models import LineaReceta, Receta
    receta = Receta(nombre="Pan", categoria_id=cat_r.id, porciones_por_lote=1)
    db.add(receta)
    db.flush()
    linea = LineaReceta(receta_id=receta.id, ingrediente_id=ing_id, cantidad=100, unidad="g")
    db.add(linea)
    db.commit()

    res = client.delete(f"/api/ingredientes/{ing_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_ingredientes.py -v
```

- [ ] **Step 3: Write routers/ingredientes.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import HistorialPrecio, Ingrediente, LineaReceta, User
from app.permissions import require_permission
from app.schemas import (
    HistorialPrecioOut,
    IngredienteCreate,
    IngredienteOut,
    IngredienteUpdate,
)
from app.services.costes import costo_por_unidad_uso

router = APIRouter(prefix="/api/ingredientes", tags=["ingredientes"])


def _to_out(ing: Ingrediente) -> dict:
    return {
        "id": ing.id,
        "nombre": ing.nombre,
        "categoria_id": ing.categoria_id,
        "categoria_nombre": ing.categoria_rel.nombre if ing.categoria_rel else "",
        "unidad_compra": ing.unidad_compra,
        "cantidad_compra": ing.cantidad_compra,
        "precio_compra": ing.precio_compra,
        "unidad_uso": ing.unidad_uso,
        "merma_porcentaje": ing.merma_porcentaje,
        "proveedor": ing.proveedor,
        "notas": ing.notas,
        "activo": ing.activo,
        "costo_por_unidad_uso": costo_por_unidad_uso(ing),
        "fecha_actualizacion": ing.fecha_actualizacion,
    }


@router.get("", response_model=list[IngredienteOut])
def list_ingredientes(
    categoria_id: int | None = Query(None),
    buscar: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Ingrediente).options(joinedload(Ingrediente.categoria_rel))
    if categoria_id:
        q = q.filter(Ingrediente.categoria_id == categoria_id)
    if buscar:
        q = q.filter(Ingrediente.nombre.ilike(f"%{buscar}%"))
    return [_to_out(i) for i in q.order_by(Ingrediente.nombre).all()]


@router.get("/{ing_id}", response_model=IngredienteOut)
def get_ingrediente(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).options(
        joinedload(Ingrediente.categoria_rel)
    ).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    return _to_out(ing)


@router.post("", response_model=IngredienteOut, status_code=201)
def create_ingrediente(
    data: IngredienteCreate,
    user: User = require_permission("ingredientes", "create"),
    db: Session = Depends(get_db),
):
    ing = Ingrediente(**data.model_dump())
    db.add(ing)
    db.commit()
    db.refresh(ing)
    db.refresh(ing, ["categoria_rel"])
    return _to_out(ing)


@router.put("/{ing_id}", response_model=IngredienteOut)
def update_ingrediente(
    ing_id: int,
    data: IngredienteUpdate,
    user: User = require_permission("ingredientes", "edit"),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).options(
        joinedload(Ingrediente.categoria_rel)
    ).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    updates = data.model_dump(exclude_unset=True)
    precio_cambio = "precio_compra" in updates and updates["precio_compra"] != ing.precio_compra

    if precio_cambio:
        historial = HistorialPrecio(
            ingrediente_id=ing.id,
            precio_anterior=ing.precio_compra,
            precio_nuevo=updates["precio_compra"],
        )
        db.add(historial)

    for key, val in updates.items():
        setattr(ing, key, val)
    db.commit()
    db.refresh(ing)
    return _to_out(ing)


@router.delete("/{ing_id}")
def delete_ingrediente(
    ing_id: int,
    user: User = require_permission("ingredientes", "delete"),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    if db.query(LineaReceta).filter(LineaReceta.ingrediente_id == ing_id).count() > 0:
        raise HTTPException(status_code=409, detail="Ingrediente usado en recetas")
    db.delete(ing)
    db.commit()
    return {"ok": True}


@router.get("/{ing_id}/historial", response_model=list[HistorialPrecioOut])
def get_historial(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(HistorialPrecio)
        .filter(HistorialPrecio.ingrediente_id == ing_id)
        .order_by(HistorialPrecio.fecha_cambio.desc())
        .all()
    )
```

- [ ] **Step 4: Mount router in main.py**

```python
from app.routers import ingredientes  # noqa: E402
app.include_router(ingredientes.router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_ingredientes.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ingredientes.py backend/app/main.py backend/tests/test_ingredientes.py
git commit -m "feat: ingredientes CRUD with auto price history, cost calculation, referential integrity"
```

---

## Task 10: Recetas CRUD + Cost Cards

**Files:**
- Create: `backend/app/routers/recetas.py`
- Modify: `backend/app/main.py` — mount router
- Create: `backend/tests/test_recetas.py`

**Interfaces:**
- Consumes: `models.Receta/LineaReceta/PrecioCompetencia`, `schemas.RecetaCreate/Update/Out`, `services.costes.costo_receta`, `permissions.require_permission`
- Produces: CRUD + cost card endpoints at `/api/recetas`, competitor prices at `/api/competencia`

- [ ] **Step 1: Write test_recetas.py**

```python
from app.auth import hash_pin
from app.models import Categoria, Ingrediente, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat_i = Categoria(nombre="Harinas", tipo="ingrediente")
    cat_r = Categoria(nombre="Panes", tipo="receta", margen_objetivo=60)
    db.add_all([cat_i, cat_r])
    db.commit()

    harina = Ingrediente(
        nombre="Harina", categoria_id=cat_i.id,
        unidad_compra="kg", cantidad_compra=25,
        precio_compra=5000, unidad_uso="g",
    )
    db.add(harina)
    db.commit()

    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, cat_r.id, harina.id


def test_create_receta_with_lines(client, db):
    token, cat_id, harina_id = _setup(client, db)
    res = client.post("/api/recetas", json={
        "nombre": "Pan Francés",
        "categoria_id": cat_id,
        "porciones_por_lote": 20,
        "precio_venta": 500,
        "lineas": [
            {"ingrediente_id": harina_id, "cantidad": 1000, "unidad": "g"},
        ],
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    data = res.json()
    assert data["nombre"] == "Pan Francés"
    assert data["costo_total"] > 0
    assert data["costo_por_porcion"] > 0
    assert data["margen"] is not None
    assert data["multi"] is not None
    assert len(data["lineas"]) == 1


def test_update_receta_replaces_lines(client, db):
    token, cat_id, harina_id = _setup(client, db)
    created = client.post("/api/recetas", json={
        "nombre": "Pan", "categoria_id": cat_id, "porciones_por_lote": 10,
        "lineas": [{"ingrediente_id": harina_id, "cantidad": 500, "unidad": "g"}],
    }, headers={"Authorization": f"Bearer {token}"})
    rec_id = created.json()["id"]

    res = client.put(f"/api/recetas/{rec_id}", json={
        "lineas": [{"ingrediente_id": harina_id, "cantidad": 1000, "unidad": "g"}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["lineas"][0]["cantidad"] == 1000


def test_delete_receta(client, db):
    token, cat_id, harina_id = _setup(client, db)
    created = client.post("/api/recetas", json={
        "nombre": "Pan", "categoria_id": cat_id, "porciones_por_lote": 1,
        "lineas": [],
    }, headers={"Authorization": f"Bearer {token}"})
    rec_id = created.json()["id"]
    res = client.delete(f"/api/recetas/{rec_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_recetas.py -v
```

- [ ] **Step 3: Write routers/recetas.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, LineaReceta, Receta, User
from app.permissions import require_permission
from app.schemas import RecetaCreate, RecetaOut, RecetaUpdate, LineaRecetaOut
from app.services.costes import costo_linea, costo_receta

router = APIRouter(prefix="/api/recetas", tags=["recetas"])


def _linea_out(linea: LineaReceta, db: Session) -> dict:
    nombre = ""
    if linea.ingrediente_rel:
        nombre = linea.ingrediente_rel.nombre
    elif linea.subreceta_rel:
        nombre = linea.subreceta_rel.nombre
    return {
        "id": linea.id,
        "ingrediente_id": linea.ingrediente_id,
        "subreceta_id": linea.subreceta_id,
        "cantidad": linea.cantidad,
        "unidad": linea.unidad,
        "nombre": nombre,
        "costo_linea": costo_linea(linea, db),
    }


def _to_out(receta: Receta, db: Session) -> dict:
    total, por_porcion = costo_receta(receta, db)
    margen = None
    multi = None
    if receta.precio_venta and receta.precio_venta > 0 and por_porcion > 0:
        margen = (receta.precio_venta - por_porcion) / receta.precio_venta * 100
        multi = receta.precio_venta / por_porcion

    return {
        "id": receta.id,
        "nombre": receta.nombre,
        "categoria_id": receta.categoria_id,
        "categoria_nombre": receta.categoria_rel.nombre if receta.categoria_rel else "",
        "porciones_por_lote": receta.porciones_por_lote,
        "precio_venta": receta.precio_venta,
        "es_subreceta": receta.es_subreceta,
        "unidad_rendimiento": receta.unidad_rendimiento,
        "notas": receta.notas,
        "costo_total": total,
        "costo_por_porcion": por_porcion,
        "margen": round(margen, 2) if margen is not None else None,
        "multi": round(multi, 2) if multi is not None else None,
        "lineas": [_linea_out(l, db) for l in receta.lineas],
    }


@router.get("", response_model=list[RecetaOut])
def list_recetas(
    categoria_id: int | None = Query(None),
    es_subreceta: bool | None = Query(None),
    buscar: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
    )
    if categoria_id:
        q = q.filter(Receta.categoria_id == categoria_id)
    if es_subreceta is not None:
        q = q.filter(Receta.es_subreceta == es_subreceta)
    if buscar:
        q = q.filter(Receta.nombre.ilike(f"%{buscar}%"))
    recetas = q.order_by(Receta.nombre).all()
    return [_to_out(r, db) for r in recetas]


@router.get("/{rec_id}", response_model=RecetaOut)
def get_receta(rec_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    receta = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
    ).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return _to_out(receta, db)


@router.post("", response_model=RecetaOut, status_code=201)
def create_receta(
    data: RecetaCreate,
    user: User = require_permission("recetas", "create"),
    db: Session = Depends(get_db),
):
    receta = Receta(
        nombre=data.nombre,
        categoria_id=data.categoria_id,
        porciones_por_lote=data.porciones_por_lote,
        precio_venta=data.precio_venta,
        es_subreceta=data.es_subreceta,
        unidad_rendimiento=data.unidad_rendimiento,
        notas=data.notas,
    )
    db.add(receta)
    db.flush()

    for l in data.lineas:
        linea = LineaReceta(
            receta_id=receta.id,
            ingrediente_id=l.ingrediente_id,
            subreceta_id=l.subreceta_id,
            cantidad=l.cantidad,
            unidad=l.unidad,
        )
        db.add(linea)

    db.commit()
    db.refresh(receta, ["lineas", "categoria_rel"])
    for linea in receta.lineas:
        db.refresh(linea, ["ingrediente_rel", "subreceta_rel"])
    return _to_out(receta, db)


@router.put("/{rec_id}", response_model=RecetaOut)
def update_receta(
    rec_id: int,
    data: RecetaUpdate,
    user: User = require_permission("recetas", "edit"),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas),
    ).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    updates = data.model_dump(exclude_unset=True)
    lineas_data = updates.pop("lineas", None)

    for key, val in updates.items():
        setattr(receta, key, val)

    if lineas_data is not None:
        for old_line in receta.lineas:
            db.delete(old_line)
        db.flush()
        for l in lineas_data:
            linea = LineaReceta(
                receta_id=receta.id,
                ingrediente_id=l.get("ingrediente_id"),
                subreceta_id=l.get("subreceta_id"),
                cantidad=l["cantidad"],
                unidad=l["unidad"],
            )
            db.add(linea)

    db.commit()
    db.refresh(receta, ["lineas", "categoria_rel"])
    for linea in receta.lineas:
        db.refresh(linea, ["ingrediente_rel", "subreceta_rel"])
    return _to_out(receta, db)


@router.delete("/{rec_id}")
def delete_receta(
    rec_id: int,
    user: User = require_permission("recetas", "delete"),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if db.query(LineaReceta).filter(LineaReceta.subreceta_id == rec_id).count() > 0:
        raise HTTPException(status_code=409, detail="Receta usada como subreceta")
    db.delete(receta)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Mount router in main.py**

```python
from app.routers import recetas  # noqa: E402
app.include_router(recetas.router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/test_recetas.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/recetas.py backend/app/main.py backend/tests/test_recetas.py
git commit -m "feat: recetas CRUD — cost cards with sub-recipes, margin, multiplier, line replacement"
```

---

## Task 11: Frontend — AppShell, AuthGuard, Navigation

**Files:**
- Create: `frontend/src/components/AuthGuard.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/BottomNav.tsx`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/PinPad.tsx`
- Create: `frontend/src/components/PermissionGate.tsx`
- Create: `frontend/src/lib/permissions.ts`
- Create: `frontend/src/app/login/page.tsx`
- Modify: `frontend/src/app/layout.tsx` — wrap in AppShell
- Modify: `frontend/src/app/page.tsx` — employee dashboard placeholder

**Interfaces:**
- Consumes: `api.ts` → `apiFetch`
- Produces: `AppShell` component wrapping all employee pages
- Produces: `AuthGuard` with render-prop `children: (user: User) => ReactNode`
- Produces: `PermissionGate` component and `usePermission(module, action)` hook
- Produces: Employee login page at `/login`

- [ ] **Step 1: Create AuthGuard.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { User } from "@/lib/types";

interface Props {
  children: (user: User) => React.ReactNode;
}

export function AuthGuard({ children }: Props) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = pathname === "/login" || pathname.startsWith("/cliente");

  useEffect(() => {
    if (isPublic) {
      setLoading(false);
      return;
    }
    const token = localStorage.getItem("brot_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("brot_token");
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [isPublic, router]);

  if (isPublic) return <>{(children as any)}</>;
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }
  if (!user) return null;
  return <>{children(user)}</>;
}
```

- [ ] **Step 2: Create Sidebar.tsx**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Inicio", icon: "🏠" },
  { href: "/ingredientes", label: "Ingredientes", icon: "🧂" },
  { href: "/escandallos", label: "Escandallos", icon: "📋" },
  { href: "/admin", label: "Admin", icon: "⚙️", admin: true },
];

export function Sidebar({ role }: { role: string }) {
  const pathname = usePathname();

  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <aside className="hidden md:flex fixed left-0 top-0 bottom-0 w-56 bg-brot flex-col z-40">
      <div className="p-4 border-b border-white/10">
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-white tracking-wider">
          BROT
        </h1>
        <p className="text-white/60 text-xs mt-1">La Panadería</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-white/15 text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-white/10">
        <button
          onClick={() => {
            localStorage.removeItem("brot_token");
            window.location.href = "/login";
          }}
          className="w-full text-left px-3 py-2 text-white/60 hover:text-white text-sm"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Create BottomNav.tsx**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Inicio", icon: "🏠" },
  { href: "/ingredientes", label: "Ingredientes", icon: "🧂" },
  { href: "/escandallos", label: "Escandallos", icon: "📋" },
  { href: "/admin", label: "Admin", icon: "⚙️", admin: true },
];

export function BottomNav({ role }: { role: string }) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-cream-dark z-40 pb-[env(safe-area-inset-bottom)]">
      <div className="flex justify-around">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center py-2 px-3 min-w-[64px] min-h-[44px] ${
                active ? "text-brot" : "text-warm-gray"
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              <span className="text-[10px] mt-0.5">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
```

- [ ] **Step 4: Create AppShell.tsx**

```tsx
"use client";

import { usePathname } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { Sidebar } from "@/components/Sidebar";
import { BottomNav } from "@/components/BottomNav";
import { ToastProvider } from "@/components/Toast";
import { User } from "@/lib/types";

export function AppShell({
  children,
}: {
  children: ((user: User) => React.ReactNode) | React.ReactNode;
}) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";
  const isCliente = pathname.startsWith("/cliente");

  if (isLogin || isCliente) {
    return <ToastProvider>{children as React.ReactNode}</ToastProvider>;
  }

  return (
    <ToastProvider>
      <AuthGuard>
        {(user) => (
          <>
            <Sidebar role={user.role} />
            <BottomNav role={user.role} />
            <main className="flex-1 md:ml-56 pb-24 md:pb-0">
              <div className="max-w-6xl mx-auto px-4 py-6">
                {typeof children === "function" ? children(user) : children}
              </div>
            </main>
          </>
        )}
      </AuthGuard>
    </ToastProvider>
  );
}
```

- [ ] **Step 5: Create permissions.ts**

```typescript
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface PermissionsMap {
  role: string;
  all_allowed?: boolean;
  permissions?: Record<string, boolean>;
}

let cachedPermissions: PermissionsMap | null = null;

export async function loadPermissions(): Promise<PermissionsMap> {
  if (cachedPermissions) return cachedPermissions;
  const perms = await apiFetch<PermissionsMap>("/api/permisos/mi-rol");
  cachedPermissions = perms;
  return perms;
}

export function clearPermissionsCache() {
  cachedPermissions = null;
}

export function usePermission(module: string, action: string): boolean | null {
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    loadPermissions().then((perms) => {
      if (perms.all_allowed) {
        setAllowed(true);
      } else {
        setAllowed(perms.permissions?.[`${module}.${action}`] ?? false);
      }
    });
  }, [module, action]);

  return allowed;
}
```

- [ ] **Step 6: Create PermissionGate.tsx**

```tsx
"use client";

import { usePermission } from "@/lib/permissions";

interface Props {
  module: string;
  action: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function PermissionGate({ module, action, children, fallback }: Props) {
  const allowed = usePermission(module, action);
  if (allowed === null) return null;
  if (!allowed) return fallback ?? null;
  return <>{children}</>;
}
```

- [ ] **Step 7: Create PinPad.tsx**

```tsx
"use client";

import { useState } from "react";

interface Props {
  onSubmit: (pin: string) => void;
  error?: string;
}

export function PinPad({ onSubmit, error }: Props) {
  const [pin, setPin] = useState("");

  const handleDigit = (digit: string) => {
    const next = pin + digit;
    setPin(next);
    if (next.length === 4) {
      onSubmit(next);
      setPin("");
    }
  };

  const handleDelete = () => setPin((p) => p.slice(0, -1));

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="flex gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`w-4 h-4 rounded-full border-2 border-brot transition-colors ${
              i < pin.length ? "bg-brot" : "bg-transparent"
            }`}
          />
        ))}
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <div className="grid grid-cols-3 gap-3">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "←"].map(
          (key) =>
            key === "" ? (
              <div key="empty" />
            ) : (
              <button
                key={key}
                onClick={() =>
                  key === "←" ? handleDelete() : handleDigit(key)
                }
                className="h-16 w-16 rounded-full bg-white border border-cream-dark text-xl font-medium text-text active:scale-[0.98] active:bg-cream touch-manipulation"
              >
                {key}
              </button>
            )
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Create login/page.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import { PinPad } from "@/components/PinPad";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

interface LoginUser {
  id: number;
  name: string;
}

export default function LoginPage() {
  const [users, setUsers] = useState<LoginUser[]>([]);
  const [selected, setSelected] = useState<LoginUser | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/auth/users`)
      .then((r) => r.json())
      .then(setUsers);
  }, []);

  const handlePin = async (pin: string) => {
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected!.name, pin }),
      });
      if (!res.ok) {
        setError("PIN incorrecto");
        return;
      }
      const data = await res.json();
      localStorage.setItem("brot_token", data.token);
      window.location.href = "/";
    } catch {
      setError("Error de conexión");
    }
  };

  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4">
      <h1 className="font-[family-name:var(--font-garamond)] text-4xl text-white mb-2">
        BROT
      </h1>
      <p className="text-white/60 mb-8">La Panadería</p>

      {!selected ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-md">
          {users.map((u) => (
            <button
              key={u.id}
              onClick={() => setSelected(u)}
              className="flex flex-col items-center gap-2 p-4 bg-white/10 rounded-xl hover:bg-white/20 transition-colors min-h-[80px]"
            >
              <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center text-white text-lg font-medium">
                {u.name[0]}
              </div>
              <span className="text-white text-sm">{u.name}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-2xl p-8 shadow-xl max-w-sm w-full">
          <div className="flex items-center justify-between mb-6">
            <button
              onClick={() => {
                setSelected(null);
                setError("");
              }}
              className="text-warm-gray text-sm"
            >
              ← Volver
            </button>
            <span className="font-medium text-text">{selected.name}</span>
          </div>
          <PinPad onSubmit={handlePin} error={error} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 9: Update layout.tsx to use AppShell**

```tsx
import type { Metadata, Viewport } from "next";
import { EB_Garamond, DM_Sans } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

const garamond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-eb-garamond",
});
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "BROT — La Panadería",
  description: "Sistema de gestión del obrador",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#004225",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={`${garamond.variable} ${dmSans.variable}`}>
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
```

- [ ] **Step 10: Update page.tsx (dashboard placeholder)**

```tsx
"use client";

export default function Home() {
  return (
    <div>
      <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-6">
        Panel de Control
      </h1>
      <p className="text-warm-gray">Bienvenido al sistema de gestión BROT.</p>
    </div>
  );
}
```

- [ ] **Step 11: Verify frontend with backend running**

```bash
# Terminal 1: Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8003

# Terminal 2: Frontend
cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8003 npm run dev -- -p 3003

# Visit http://localhost:3003 → should redirect to /login
# Visit http://localhost:3003/login → should show user grid with "Admin"
# Enter PIN 0000 → should redirect to dashboard
```

- [ ] **Step 12: Commit**

```bash
git add frontend/src/
git commit -m "feat: AppShell, AuthGuard, PIN login, Sidebar, BottomNav, RBAC permission gate"
```

---

## Task 12: Frontend — Ingredientes Pages

**Files:**
- Create: `frontend/src/app/ingredientes/page.tsx`
- Create: `frontend/src/app/ingredientes/[id]/page.tsx`
- Create: `frontend/src/app/ingredientes/nuevo/page.tsx`

**Interfaces:**
- Consumes: `api.ts`, `types.ts`, `format.ts`, `PermissionGate`
- Produces: Ingredient list, detail/edit, and create pages

Steps follow the same pattern as Task 11: create each page component with proper CRUD forms, tables, and filters. Implementation follows the exact Escandallos app patterns (inline editing for prices, category filter chips, search input).

- [ ] **Step 1: Create ingredientes list page** — table with search, category filter, cost per unit display, inline price editing
- [ ] **Step 2: Create nuevo page** — form with all ingredient fields, category dropdown, unit selectors
- [ ] **Step 3: Create [id] detail page** — view/edit mode toggle, price history chart, delete with confirmation
- [ ] **Step 4: Verify in browser** — CRUD flow works end-to-end
- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ingredientes/
git commit -m "feat: ingredientes pages — list, create, detail/edit with price history"
```

---

## Task 13: Frontend — Escandallos (Recipe) Pages

**Files:**
- Create: `frontend/src/app/escandallos/page.tsx`
- Create: `frontend/src/app/escandallos/[id]/page.tsx`
- Create: `frontend/src/app/escandallos/nuevo/page.tsx`

**Interfaces:**
- Consumes: `api.ts`, `types.ts`, `format.ts`, `PermissionGate`
- Produces: Recipe list with margins/multipliers, recipe detail with cost card, create recipe form with line item management

Steps follow the Escandallos app pattern: recipe list with margin badges, recipe detail showing full cost breakdown with line items, ingredient selector modal, sub-recipe support.

- [ ] **Step 1: Create escandallos list page** — table with category filter, margin badge, multiplier, cost/PVP columns
- [ ] **Step 2: Create nuevo page** — recipe form with dynamic line items (ingredient picker + quantity + unit)
- [ ] **Step 3: Create [id] detail page** — cost card view, edit mode, line management, sub-recipe links
- [ ] **Step 4: Verify in browser** — create recipe with ingredients, see cost calculation, edit lines
- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/escandallos/
git commit -m "feat: escandallos pages — recipe list, cost cards, line management"
```

---

## Task 14: Frontend — Admin Pages (Users + Permissions + Categories)

**Files:**
- Create: `frontend/src/app/admin/layout.tsx`
- Create: `frontend/src/app/admin/equipo/page.tsx`
- Create: `frontend/src/app/admin/permisos/page.tsx`
- Create: `frontend/src/app/admin/categorias/page.tsx`

- [ ] **Step 1: Create admin layout** — tab navigation for admin sections
- [ ] **Step 2: Create equipo page** — user CRUD (name, PIN, role toggle)
- [ ] **Step 3: Create permisos page** — permission matrix (modules × actions with toggle switches per staff role)
- [ ] **Step 4: Create categorias page** — category CRUD with type filter
- [ ] **Step 5: Verify in browser** — create user, toggle permissions, manage categories
- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/admin/
git commit -m "feat: admin pages — user management, RBAC config, categories"
```

---

## Task 15: Run All Tests + Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 2: Start both servers and verify full flow**

```bash
# Backend
cd backend && DATABASE_URL="sqlite:///data/app.db" uvicorn app.main:app --reload --port 8003

# Frontend
cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8003 npm run dev -- -p 3003
```

Verify:
1. Login page shows Admin user
2. PIN 0000 logs in
3. Dashboard shows
4. Ingredientes CRUD works
5. Escandallos CRUD works with cost calculation
6. Admin pages work (users, permissions, categories)
7. Bottom nav works on mobile viewport
8. Sidebar works on desktop

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix: final adjustments from integration testing"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```

---

## Future Phases (separate plans)

| Phase | Modules | Depends On |
|-------|---------|------------|
| Phase 2 | Stock Materia Prima, Inventario | Phase 1 (ingredientes) |
| Phase 3 | Proveedores, Pedidos Proveedores | Phase 1 (ingredientes) + Phase 2 (stock) |
| Phase 4 | Producción (calendario, tiempos, cantidades) | Phase 1 (recetas) |
| Phase 5 | Stock Congelado | Phase 4 (producción) |
| Phase 6 | Mermas | Phase 1 (ingredientes + recetas) |
| Phase 7 | Protocolos + Temperaturas | Independent |
| Phase 8 | Customer Portal (catalog, orders, recurring) | Phase 1 (recetas) |
| Phase 9 | Entregas B2B + Entregas Proveedores | Phase 3 + Phase 8 |
| Phase 10 | Data Import (CSV/Excel for all modules) | All modules |
| Phase 11 | Precio Competencia comparison dashboard | Phase 1 (recetas) |
| Phase 12 | Deploy (Vercel + Render + Neon setup) | All phases |
