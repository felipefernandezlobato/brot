# BROT — App Obrador (Bakery Management System)

## Project Overview

**BROT La Panadería** is a comprehensive bakery workshop (obrador) management app for a single-location artisan bakery in Argentina. It covers the full operational cycle: ingredient procurement, recipe costing, production planning, stock management, waste tracking, customer ordering, supplier deliveries, and daily protocols.

- **Currency:** Argentine Pesos (ARS), formatted as `$1.234,56` (dot for thousands, comma for decimals)
- **Language:** Spanish (all UI, labels, domain terms)
- **Location:** Single bakery (one obrador) — no multi-location complexity
- **Users:** Two types — employees (staff/admin) and customers (B2C portal)

---

## Tech Stack

### Frontend
- Next.js (App Router) + TypeScript + Tailwind CSS 4
- React 19
- Recharts (line charts for stock evolution)
- Mobile-first, PWA-enabled
- Deploy to Vercel (free tier)
- Root directory: `frontend/`

### Backend
- FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic
- Python 3.12
- Deploy to Render (free tier)
- Root directory: `backend/`
- Start script: `start.sh` (runs `alembic upgrade head` + uvicorn)

### Database
- Neon PostgreSQL (free tier)
- `DATABASE_URL` env var controls connection
- Falls back to SQLite if `DATABASE_URL` not set
- Pool config: `pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=300`

### Project Structure
```
brot/
  frontend/         # Next.js app
  backend/          # FastAPI app
  design/           # Logo and branding assets
  CLAUDE.md         # This file
  render.yaml       # Render deploy config
```

---

## Branding

- **Name:** BROT La Panadería
- **Logo:** `design/image (1).png` — white text + wheat icon on black
- **Primary color:** British Racing Green — `#004225` (dark green)
- **Palette:** Green primary, cream/warm white backgrounds, dark text
- **Fonts:** EB Garamond (headings/display) + DM Sans (body/UI) — Google Fonts
- **Tone:** Artisan, warm, professional

---

## Authentication

### Employee Auth (Pattern B — PIN login with roles)
- Staff picks name from a grid, enters 4-digit PIN
- PIN hashed with bcrypt, stored in DB
- JWT token (HS256) with 30-day expiry
- Two roles: `admin` (full access) and `staff` (restricted)
- Default admin user seeded on first run: name="Admin", PIN="0000"
- Token stored in `localStorage` key: `brot_token`

### Role-Based Access Control (RBAC)
- **Admin:** Full access to all modules, all CRUD operations, all views
- **Staff:** Restricted access — exact permissions TBD (will be configured after app is built)
- **Implementation:** Build a configurable permission system so staff access can be toggled per module/action without code changes
- **Permission model:** `Permission` table with `role`, `module`, `action` (view/create/edit/delete) columns
- **Frontend:** `usePermission(module, action)` hook that checks the current user's role against allowed permissions. Hide/disable UI elements the user can't access.
- **Backend:** `require_permission(module, action)` FastAPI dependency that checks role permissions on each endpoint. Returns 403 if denied.
- **Admin settings page:** UI for admin to configure which modules/actions staff can access

### Customer Auth (Email + Password)
- Customers register with email + password
- Password hashed with bcrypt
- JWT token (HS256) with 30-day expiry
- Customer-specific views: product catalog, order placement, order history
- Token stored in `localStorage` key: `brot_customer_token`
- Separate login page from employee login (`/cliente/login`)

### View Routing
- Employee routes: `/` (dashboard), `/stock`, `/produccion`, `/escandallos`, `/pedidos`, `/mermas`, `/protocolos`, `/admin/*`
- Customer routes: `/cliente/` (catalog), `/cliente/pedidos` (my orders), `/cliente/login`
- `AuthGuard` checks token type and redirects to correct login page

---

## Modules (11 total)

### 1. Stock Materia Prima / Ingredientes
Raw material and ingredient inventory management.

**Features:**
- CRUD for ingredients with categories
- Dual-unit system: purchase unit (how you buy) vs. use unit (how recipes consume)
- Current stock levels with location tracking (almacén, cámara fría, obrador)
- Stock snapshots: periodic inventory counts
- Stock alerts: ingredients below minimum level
- Par level calculation based on consumption patterns

**Data model reference:** Based on Escandallos' `Ingrediente` + `InventarioRegistro` pattern.

### 2. Stock Producto Congelado
Frozen product inventory — tracks finished/semi-finished products stored in freezer.

**Features:**
- Separate stock tracking for frozen goods (breads, doughs, pre-shaped items)
- Shelf life tracking with expiry date alerts
- FIFO (first in, first out) management
- Link to production records (what was frozen, when)

### 3. Mermas (Waste/Shrinkage)
Track product and ingredient losses.

**Features:**
- Log waste by ingredient OR finished product
- Categorize by reason: `caducado` (expired), `dañado` (damaged), `produccion` (production loss), `otro` (other)
- Cost calculation at time of logging (snapshot, not recalculated)
- Analysis dashboard: waste by category, by reason, by time period, top wasted items
- Date range filtering

**Data model reference:** Based on Escandallos' `MermaRegistro`.

### 4. Calendario Producción (Production Calendar)
Production planning and tracking.

**Features:**
- **Production plan:** 4-week rotating schedule (like Checklists' `ProductionPlan`) defining what to produce each day
- **Production log:** Record actual quantities produced per product per day
- **Cantidades producidas:** Track planned vs. actual quantities with variance analysis
- **Tiempo de producción:** Track machine time (oven hours, mixer hours, etc.) and human labor hours per production run — for **capacity planning** (not cost allocation)
- Calendar view: visual weekly/monthly calendar showing planned production
- Production schedule templates for recurring production cycles

**Sub-modules:**
- `cantidades producidas` — planned vs actual quantity tracking
- `tiempo de producción (maquinaria, humana)` — machine and labor time logging per production batch

### 5. Escandallos (Recipe Cost Cards)
Recipe management with full cost breakdown.

**Features:**
- **Costo:** Total recipe cost calculated from ingredient costs + sub-recipe costs
- **PVP (Precio Venta al Público):** Retail selling price
- **Multi (Multiplicador):** Cost multiplier = PVP / cost per portion — traffic light badges (green/yellow/red based on target margin)
- **Precio competencia:** Competitor price tracking with manual entry + side-by-side comparison view
- Recipe lines can reference ingredients OR sub-recipes (recursive costing with cycle detection)
- Porciones por lote (portions per batch)
- Unit conversion system (kg/g/mg, litro/ml/cl)
- Merma % (shrinkage) factored into ingredient cost
- Price history tracking when ingredient costs change

**Data model reference:** Based on Escandallos app's `Receta`, `LineaReceta`, cost calculation engine. Add competitor price model.

**New model: `PrecioCompetencia`**
- `receta_id`, `competidor_nombre`, `precio`, `fecha_registro`, `notas`
- Dashboard comparing BROT prices vs. competitor prices per product

### 6. Ingredientes con Precios e Historial de Precios
Ingredient price management with full audit trail.

**Features:**
- All ingredients have purchase price + supplier association
- Automatic price history recording on every price change
- Price trend charts per ingredient
- Multi-supplier price comparison (same ingredient from different suppliers)
- Auto-switch to cheapest supplier option
- PDF invoice import: extract → preview → confirm (like Escandallos' import flow)

**Data model reference:** Based on Escandallos' `HistorialPrecio`, `Proveedor`, `PrecioProveedor`.

### 7. Pedidos Materia Prima Proveedores (Supplier Purchase Orders)
Raw material ordering from suppliers.

**Features:**
- Order lifecycle: `borrador` → `enviado` → `recibido`
- Order lines with ingredient, quantity, unit, expected price
- On reception: auto-update stock levels
- Order recommendations based on par levels minus current stock
- Group recommendations by supplier
- Order history pivot view (weeks × suppliers)
- Supplier CRUD with lead time and order cycle settings

**Data model reference:** Based on Escandallos' `Pedido`, `LineaPedido`.

### 8. Customer Portal Orders
Customer-facing ordering system for B2C sales.

**Features:**
- **Customer registration:** email + password, name, phone, address
- **Product catalog:** Browse available products with photos, descriptions, prices (ARS)
- **Order placement:** Select products + quantities, choose delivery date
- **Delivery days:** Only Wednesday and Saturday available for delivery selection
- **Order lifecycle:** `pendiente` → `confirmado` → `en_preparacion` → `listo` → `entregado`
- **Customer order history:** View past orders and their status
- **Admin view:** See all customer orders, filter by date/status, manage order status transitions
- **No online payment:** Customers pay upon delivery/pickup
- **Recurring orders:** Customers can set up a weekly standing order with default products/quantities. Each week the system auto-generates an order from the template for the next available delivery day. The customer can edit (add/remove items, change quantities) or skip any specific week before a cutoff time. Admin can also view and manage all recurring orders.

**New models:**
- `Cliente` — email, password_hash, nombre, telefono, direccion, is_active
- `PedidoCliente` — cliente_id, fecha_pedido, fecha_entrega (Wed/Sat only), estado, notas, total, pedido_recurrente_id (nullable, links back to the template that generated it)
- `LineaPedidoCliente` — pedido_cliente_id, producto_id, cantidad, precio_unitario_snapshot, subtotal
- `ProductoCatalogo` — nombre, descripcion, precio, categoria, imagen_url, disponible, posicion
- `PedidoRecurrente` — cliente_id, dia_entrega (wed/sat), activo, fecha_inicio, notas
- `LineaPedidoRecurrente` — pedido_recurrente_id, producto_id, cantidad_default

**Recurring order flow:**
1. Customer creates a recurring order template: picks delivery day (Wed or Sat), adds products with default quantities
2. System auto-generates a `PedidoCliente` from the template each week (e.g., on Monday for Wed delivery, on Thursday for Sat delivery)
3. Customer receives notification and can edit the generated order (change quantities, add/remove items) or skip the week entirely before a cutoff
4. If not edited, the default order stands as-is
5. Admin dashboard shows all recurring templates + upcoming auto-generated orders

### 9. Entregas de Pedidos por Proveedor (Supplier Delivery Tracking)
Track incoming supplier deliveries.

**Features:**
- Record when each supplier delivers goods
- Match deliveries to purchase orders
- Track delivery accuracy (ordered vs. received quantities)
- Delivery history per supplier
- Flag discrepancies (missing items, wrong quantities, quality issues)

### 10. Volumen de Entregas Colectivo (Outbound Delivery Volume)
Track outgoing deliveries to B2B clients.

**Features:**
- Aggregate delivery volumes for Wed/Sat delivery days
- Route planning view: what goes where
- Delivery confirmation tracking
- Volume analysis: deliveries per period, per client, per product
- B2B client management (separate from B2C customer portal)

**New model:**
- `ClienteB2B` — nombre, direccion, telefono, contacto, notas, dia_entrega_preferido
- `EntregaB2B` — cliente_b2b_id, fecha_entrega, estado, notas
- `LineaEntregaB2B` — entrega_id, producto_id, cantidad, precio_unitario

### 11. Protocolos (Operational Protocols/Checklists)
Daily/weekly/monthly operational task tracking.

**Features:**
- Template → Completion pattern (like Checklists app)
- Single location (no multi-area rotation needed)
- Four frequencies: `apertura` (opening), `cierre` (closing), `semanal` (weekly), `mensual` (monthly)
- Task completion tracking with user attribution
- Undo within 1 hour (staff), anytime (admin)
- Quality review / flag system (admin can mark tasks as unsatisfactory)
- Temperature tracking for fridges/freezers (is_alert when above max_temp)
- History and reporting: daily/weekly/monthly completion summaries
- CSV export of completion history

**Data model reference:** Based on Checklists' `ChecklistTemplate`, `ChecklistCompletion`, `Fridge`, `TemperatureReading`. Simplified to single area. Production tracking is NOT in this module — it lives in Calendario Producción.

---

## Key Patterns (replicated from existing apps)

### Backend Patterns
- **CRUD structure:** `_to_out()` helper → list/get/create/update/delete with existence checks and referential integrity guards
- **Price history:** Auto-record `HistorialPrecio` on every ingredient price change
- **Snapshot pricing:** Freeze prices on order lines at creation time — future price changes don't affect historical records
- **Import flow:** Three-step extract → preview → confirm for PDF invoice imports
- **Idempotent seed:** `seed_data()` called on startup, checks existence before inserting
- **Alembic migrations:** Run automatically on deploy via `start.sh`

### Frontend Patterns
- **AppShell:** `ToastProvider` → `AuthGuard` → `AppShellInner` (header + nav)
- **Navigation:** Sidebar on desktop, bottom tab bar on mobile
- **API client:** `apiFetch<T>()` wrapper with token injection + 401 redirect
- **Optimistic updates:** Fake completion → API call → replace with real data or revert
- **Draft persistence:** Save form state to `sessionStorage`, restore on page load
- **Window focus refresh:** Re-fetch data on `window.addEventListener("focus")`
- **Mobile-first:** 44px touch targets, `touch-manipulation`, `env(safe-area-inset-bottom)`, `inputMode="decimal"` for number fields, comma→dot conversion for decimal input
- **No `router.push()` for tabs:** Use `useState` + `window.history.replaceState()` for in-page navigation

### UI Conventions
- **Color palette:**
  - Primary: `#004225` (British Racing Green), hover: darker shade
  - Background: warm cream/off-white
  - Cards: white with subtle border
  - Input focus: green ring
  - Text: dark near-black
  - Muted text: warm gray
- **Inline editing:** Click value → replace with input → save on Enter/blur
- **Toast notifications:** Auto-dismiss 3s, stacked, bottom-right, green for success, red for error
- **Loading state:** Simple `Cargando...` centered text
- **Filters:** Client-side `.filter()` on fetched data, with search + category chips
- **Stock/inventory input pattern (card grid):**
  - Category filter chips at top, search bar + counter ("0 / 23") on same row
  - Items grouped by category (header in green uppercase)
  - Grid of cards: 1 col mobile, 2 tablet, 3 desktop
  - Each card: product name (green), "hace Xd" subtitle, number input + unit
  - Filled cards get highlighted border/bg (`border-brot/40 bg-brot/5`)
  - Sticky submit bar at bottom with count + "Registrar Stock" button
  - Draft persistence via sessionStorage
- **History/historial pattern (pivot table + chart):**
  - Two-level chart selector: category chips → expand to show individual items
  - "Todos" button to select all items across categories
  - Recharts LineChart for evolution over time
  - Pivot table below: items as rows (sticky left), dates as columns (most recent left), horizontal scroll
  - Compact text (`text-xs`), unit in own column, zebra striping, zero values in red
  - Default date range: 90 days
- **Tab navigation within pages:** Use `useState` + `window.history.replaceState()` for in-page tabs (e.g., Registrar | Historial)

### Multi-level Production Chain
Products have 4 levels tracked in `ProductoCongelado.nivel`:
- `masa` → Masas base (consume ingredientes from Stock MP)
- `semi` → Bastones, congelados (consume masas from Stock Congelado)
- `crudo` → Productos armados sin cocinar (consume bastones — manual input for bastones, auto for rest)
- `terminado` → Producto final listo para venta (consume crudos 1:1)

Each product has `producto_padre_id` (FK to parent) and `cantidad_por_padre` (how many from 1 parent).
Production via `POST /api/produccion/producir` with `producto_id`, `cantidad_producida`, `fecha`, optional `bastones_consumidos`.
Stock service: `services/stock.py` → `producir_producto()`.
Calendar tasks have `producto_congelado_id` and `necesita_bastones` for correct stock handling.
Stock effects ONLY via `/produccion/producir` (removed old `_aplicar_efectos_stock`).

### Subrecetas without their own stock (e.g. Masa Madre)
Most subrecetas (bastones, Masa Croissant/Medialuna/Hojaldre) have their own `ProductoCongelado` and are produced/stocked separately — their ingredients are deducted once, when THEY are produced, and the parent-chain consumption above just draws down that existing stock. Masa Madre is different: it's never produced/stocked on its own (no `ProductoCongelado` points at its `Receta`), it's fed daily and used inline wherever a recipe calls for it.
- `producir_producto()` only auto-deducts direct `ingrediente_id` lines by default. For a `subreceta_id` line, it checks `_tiene_stock_propio()` (does a `ProductoCongelado` reference that sub-recipe?) — if not, it recurses into that sub-recipe's own lines via `_consumir_ingredientes_subreceta()` and deducts the real ingredients right then. If the subreceta DOES have its own stock, the line is left alone (already handled by the parent-stock path) to avoid double-consuming.
- Gotcha: `SessionLocal` is `autoflush=False`. Deducting the same ingredient twice within one production (direct line + via a stockless subreceta) needs an explicit `db.flush()` after each `InventarioRegistro` write in `deducir_materia_prima()`, or the second deduction reads a stale balance.
- Masa Madre: Receta id=38, `es_subreceta=True`, `porciones_por_lote=1`, `unidad_rendimiento="kg"` = 0.5kg Harina 00 Pizza + 0.5L Agua. Used by Masa Pan Blanco/Negro, Amasar Focaccia, Barra Blanca/Integral 350g.
- Movement labeling: ingredients consumed via a stockless subreceta get their own movement labeled with the SUBRECETA's name, not the parent recipe's — see Movement Descriptions below.

### Recipe Cost Chain (3 levels)
Cost flows through: Masa (ingredients) → Baston (sub-recipe = masa) → Terminado (sub-recipe = baston).
- Bastones have their own recipes (id=29,30,31) with `porciones_por_lote=1` and `cantidad=1u` of masa.
- Motor calculates: `BastonCost = MasaTotalCost / MasaPorciones * 1`.
- Terminado recipes reference bastones (NOT masas directly).
- Pan products share masa proportionally by weight (0.6154 for 1kg, 0.3846 for 0.5kg).
- Barras (Blanca/Integral) have direct ingredient lines plus one subreceta line (Masa Madre).

### Movement Descriptions
All movement tables show context via `referencia_origen`, resolved by `describir_referencia()` (`services/produccion_registro.py`):
- `produccion_consumo` → "Consumido para Masa Croissant"
- `produccion_salida` → "Producido" (no "para X")
- `entrega_b2b` → "Entrega B2B Creme" (client name from ref format `entrega_b2b:{id}:{name}`)
Ingredient detail pages have movements via `GET /api/ingredientes/{id}/movimientos`.

Ingredients consumed via a stockless subreceta (Masa Madre) need a DIFFERENT label than the parent recipe, but must keep the SAME `referencia_origen` as the rest of that production event — `revertir_consumos()` matches on it exactly, so splitting it would break edit/delete reversal. The subreceta's name rides in `MovimientoStock.notas` instead (`"subreceta:{nombre}"`, set via `deducir_materia_prima(..., origen_subreceta=...)`), and `nombre_origen_movimiento()` (not `describir_referencia()`) reads that tag first before falling back to the recipe name. `GET /api/ingredientes/{id}/movimientos` uses `nombre_origen_movimiento()`; the congelado-facing endpoints (recetas.py, congelados.py) still use `describir_referencia()` directly since `tipo_stock="congelado"` movements never carry this tag.

### Unified Product Pages
- `/escandallos/[id]` — single page with recipe + costs + stock + chart + chain + movements
- `/congelados/[id]` — redirects to escandallos for terminados, shows full detail for crudos/semis/masas
- Endpoint: `GET /api/recetas/{id}/completo` returns everything in one call (handles recipes with or without ProductoCongelado)

### Stock Charts (FIXED)
Charts built from MovimientoStock (not StockCongelado). Shows cumulative running balance:
goes UP on production (+produccion_salida), DOWN on consumption (-produccion_consumo).
Both `/api/recetas/{id}/completo` and `/api/congelados/productos/{id}/detalle` use this.
Ingredient charts use InventarioRegistro snapshots, deduplicated by date (last entry per day).
`stock_actual` also calculated from MovimientoStock sum (fallback to StockCongelado for legacy data).

### End-to-End Traceability
All stock movements recorded in `MovimientoStock` table with tipo_movimiento and referencia_origen.
ALL functions in `services/stock.py` accept and propagate `fecha` — movements always get the correct date (production date from calendar, entrega date from delivery), never `date.today()` by default.
Dashboard at `/api/dashboard/flujo` and `/api/dashboard/reconciliacion`.
Reconciliation compares physical count vs calculated (anterior + recibido - consumido - merma).

### Entregas B2B
Nueva Entrega form on `/entregas` page (tab "Nueva") with client dropdown, date picker, product lines.
`referencia_origen` format: `entrega_b2b:{id}:{client_name}` — includes client name for display in movements.
Stock deduction uses `fecha_entrega` (not today) so backdated deliveries get correct movement dates.

### Customer Portal
Exists at `/cliente/login` (email+password auth). Features: registration, product catalog with prices, order placement (Wed/Sat delivery), recurring orders. Token stored in `brot_customer_token`.
Catalog prices from `ProductoCatalogo.precio` — must be kept in sync with recipe PVPs.

---

## API Design

All API routes under `/api/` prefix.

### Auth Routes
```
POST /api/auth/login              # Employee PIN login
GET  /api/auth/me                 # Current employee info
GET  /api/auth/users              # Public: employee names for login grid

POST /api/auth/cliente/registro   # Customer registration
POST /api/auth/cliente/login      # Customer email+password login
GET  /api/auth/cliente/me         # Current customer info
```

### Module Routes (all require employee auth unless noted)
```
# Stock / Ingredientes
CRUD /api/ingredientes
GET  /api/inventario/actual
POST /api/inventario              # Record stock snapshot
GET  /api/inventario/alertas

# Stock Congelado
CRUD /api/congelados
GET  /api/congelados/alertas-vencimiento

# Mermas
CRUD /api/mermas
GET  /api/mermas/analisis

# Producción
CRUD /api/produccion/productos
CRUD /api/produccion/plan
CRUD /api/produccion/log
GET  /api/produccion/calendario
POST /api/produccion/tiempos

# Escandallos
CRUD /api/recetas
GET  /api/recetas/{id}/costo
CRUD /api/competencia             # Competitor prices

# Proveedores & Pedidos
CRUD /api/proveedores
CRUD /api/pedidos
POST /api/pedidos/{id}/enviar
POST /api/pedidos/{id}/recibir
GET  /api/pedidos/recomendacion

# Customer Portal (customer auth)
GET  /api/catalogo                # Public: product catalog
POST /api/cliente/pedidos         # Place order
GET  /api/cliente/pedidos         # My orders
GET  /api/cliente/pedidos/{id}    # Order detail

# Customer Orders (admin view)
GET  /api/admin/pedidos-clientes
PUT  /api/admin/pedidos-clientes/{id}/estado

# Entregas proveedores
CRUD /api/entregas-proveedor

# Entregas B2B
CRUD /api/entregas-b2b
CRUD /api/clientes-b2b
GET  /api/entregas-b2b/volumen

# Protocolos
GET  /api/protocolos/hoy
GET  /api/protocolos/semanal
GET  /api/protocolos/mensual
POST /api/protocolos/completar
DELETE /api/protocolos/completar/{id}
PUT  /api/protocolos/completar/{id}/revision

# Temperaturas
POST /api/temperaturas/{turno}
GET  /api/temperaturas/historial

# Backup
GET  /api/backup/descargar
GET  /api/export/csv
```

---

## Deploy

**Production URLs:**
- Frontend: https://brot-bruteam.vercel.app
- Backend: https://brot-api.onrender.com

**Database:** Neon PostgreSQL (project: `BROT`, region: `aws-eu-central-1`)
- Connection: `postgresql://neondb_owner:npg_l2UDXiHuW7KJ@ep-noisy-star-b2b44bno.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require`

**Deploy Checklist:**
1. `git push` — triggers Vercel auto-deploy for frontend
2. Render auto-deploys backend on push to `main`
3. Wait ~2-3 min, then verify: `curl -s -o /dev/null -w "%{http_code}" https://brot-api.onrender.com/api/auth/users` (expect 200)

**IMPORTANT:** Always `git push` immediately after committing any change. Felipe only tests on production — if you don't push, he can't see the change. Never wait for him to ask you to push.

**Environment variables (already configured):**
- Render: `DATABASE_URL` (Neon URL), `SECRET_KEY`, `CORS_ORIGINS` (https://brot-bruteam.vercel.app)
- Vercel: `NEXT_PUBLIC_API_URL` = `https://brot-api.onrender.com`

**Render config:** Root directory `backend`, build `pip install -r requirements.txt`, start `bash start.sh`

Render start command runs `alembic upgrade head` + uvicorn — migrations auto-apply on every deploy.

---

## Local Development

Two options for local dev:
1. **Connect to Neon (recommended)** — same data as production:
   ```bash
   DATABASE_URL="postgresql://neondb_owner:npg_l2UDXiHuW7KJ@ep-noisy-star-b2b44bno.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require" uvicorn app.main:app --reload --port 8003
   ```
2. **Use local SQLite** — no env var needed, isolated dev database (data lost on restart if in-memory)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="postgresql://neondb_owner:npg_l2UDXiHuW7KJ@ep-noisy-star-b2b44bno.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require" uvicorn app.main:app --reload --port 8003

# Frontend
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8003 npm run dev -- -p 3003
```

- Backend port: 8003
- Frontend port: 3003
- Employee token key: `brot_token`
- Customer token key: `brot_customer_token`

---

## Data Import / Historical Data Entry

The bakery has existing operational data that needs to be imported into the app. Every module should support bulk data entry:

### Import Methods
- **CSV/Excel upload:** Upload spreadsheets with historical data (stock counts, mermas, production logs, ingredient lists with prices)
- **Bulk form entry:** Multi-row forms for entering data in batch (e.g., paste a list of ingredients with prices)
- **PDF import:** Extract ingredient prices from supplier invoices (same extract → preview → confirm pattern as Escandallos)

### Modules that need import support
| Module | Import Data |
|--------|------------|
| Ingredientes | Ingredient list with names, categories, units, prices, suppliers |
| Escandallos | Recipes with ingredient lines and quantities |
| Stock Materia Prima | Historical stock count snapshots by date |
| Mermas | Historical waste records |
| Calendario Producción | Production calendar/schedule with planned quantities |
| Precios | Historical ingredient price data for trend analysis |
| Proveedores | Supplier list with contact info and lead times |

### Import UX Pattern
1. User uploads CSV or enters data in a multi-row form
2. System validates and shows a **preview** with matched/unmatched items highlighted
3. User reviews and **confirms** the import
4. System applies the data and shows a summary of what was imported

---

## Implementation Priority

Build in this order to establish foundations first:

1. **Auth + AppShell** — Employee PIN login, customer email login, navigation, AuthGuard
2. **Ingredientes + Categorías** — Base ingredient/category CRUD (foundation for everything)
3. **Escandallos** — Recipe costing engine (depends on ingredients)
4. **Stock Materia Prima** — Inventory tracking (depends on ingredients)
5. **Proveedores + Pedidos** — Supplier orders (depends on ingredients + stock)
6. **Producción** — Production planning and logging
7. **Stock Congelado** — Frozen product tracking (depends on production)
8. **Mermas** — Waste tracking (depends on ingredients + recipes)
9. **Protocolos** — Checklists + temperature tracking
10. **Customer Portal** — Catalog + ordering (depends on recipes for product catalog)
11. **Entregas B2B** — Outbound delivery tracking
12. **Entregas Proveedores** — Inbound delivery tracking
13. **Precio Competencia** — Competitor price comparison (depends on recipes)
