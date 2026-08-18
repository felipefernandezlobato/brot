# BROT_BASEL — Registro de la sesión "no cuadra la producción" (17-18/08/2026)

Documento de respaldo para no perder el hilo de todo lo investigado y corregido
en esta sesión (trabajada en paralelo por dos sesiones de Claude sobre el mismo
repo). Todo lo listado acá **ya está commiteado y pusheado a `origin/main`**
(verificado 18/08, `git status` limpio, `git log origin/main..HEAD` vacío).

Para el detalle técnico ya integrado como referencia permanente del proyecto,
ver `CLAUDE.md` (secciones actualizadas por el commit `ccec831`). Este archivo
es la crónica de la sesión — por qué se hizo cada cosa y en qué orden — no un
reemplazo de CLAUDE.md.

---

## Disparador

Felipe: "no cuadraba la producción con lo consumido de los ingredientes" —
el stock de materia prima (sobre todo Manteca) no cerraba contra lo que las
recetas deberían haber consumido.

## Cadena de commits (orden cronológico, `c5a7c73` = HEAD antes de empezar)

### 1. Bugs raíz de producción (antes de esta sesión de registro, mismo día)
- `a1786e8` — "1 receta" se leía como "1 porción" (Masa Croissant descontaba
  1/9 de la receta). Completar una tarea sin cantidad no descontaba nada.
  Producción pasó a ser atómica y reversible vía `services/produccion_registro.py`.
- `6e69664` — `start.sh` ahora falla el deploy si la migración falla
  (`set -e`), en vez de arrancar con el código nuevo contra el schema viejo.
- `c5a7c73` — mermas y entregas B2B devuelven stock al borrarse/editarse.

### 2. Visibilidad: por fin se puede ver "para qué" se consumió algo
- `9260066` — movimientos muestran "Consumido para Masa Croissant" en vez de
  "Consumido" a secas (`describir_referencia()` resuelve `registro_produccion:{id}`
  → nombre de receta/producto). **Esto es lo que permitió encontrar el resto.**
- `82c0a92` — se ocultan los pares revertido+compensación de las listas de
  actividad reciente (quedaban como ruido "-13.5 / +13.5" en cada edición).

### 3. Masa Madre: de ingrediente inventado a subreceta real
- `3bf754f` — Masa Madre estaba modelada como Ingrediente comprado con precio
  fijo adivinado ($400/kg); en realidad se amasa con harina+agua y no tiene
  stock propio. `producir_producto()` ahora resuelve subrecetas sin stock
  propio a sus ingredientes reales en el momento (`_consumir_ingredientes_subreceta`).
- `7022861` — esa consumición aparece como su propio movimiento
  ("Consumido para Masa Madre"), separado del movimiento del padre.

### 4. El doble conteo de Manteca Laminado (el bug original que se reportó)
**Diagnóstico:** `Manteca Laminado` (bloque de 20kg manteca + 2kg harina 000
para laminar) se producía como tarea aparte, pero **nada la consumía después**.
Mientras tanto, `Masa de Croissant` y `Masa de Medialuna` tenían una segunda
línea de "Manteca" cruda (9kg y 6kg) que representaba ese mismo laminado, pero
cargada como ingrediente crudo duplicado. Confirmado con Felipe: 1 masa de
croissant → 9 bastones, 1kg de manteca laminada por bastón (9kg÷9, 6kg÷6).

- `5b3fb12` — Arregla el motor: `producir_producto()` ahora descuenta el
  stock propio de **cualquier** subreceta que lo tenga, no solo la que ya
  está cubierta por `producto_padre_id`. Cuidado importante:
  `_es_ancestro_congelado()` camina toda la cadena de padres (no solo el
  padre directo) para no descontar dos veces el bastón cuando un terminado
  (Croissant, Napolitana, Cruffin, Pan Suizo, Moño...) lo referencia para
  costeo pero su padre físico real es un "crudo" intermedio que ya desciende
  de ese bastón. 2 tests nuevos cubren exactamente ese caso.
  - `backend/scripts/corregir_manteca_laminado.py`: saca las líneas de
    manteca duplicada de las masas, agrega 1kg Manteca Laminado (subreceta)
    a cada receta de bastón, recalcula los registros del 14-15/08 afectados.
  - Resultado: demanda de manteca del 14/08 bajó de 46,6kg (imposible) a
    **27,1kg contra un conteo real de 28kg**. Manteca Laminado pasó de 23kg
    sentados sin tocar a **5kg** tras laminar 18 bastones reales.
- `1ec4d94` — movimientos de bastón muestran "bastones producidos" en vez de
  "Producido" a secas ("u" no dice nada).

### 5. Incidente de producción: deploy roto (detectado a mitad de sesión)
Felipe pegó un log de deploy de Render fallando con
`ModuleNotFoundError: No module named 'app'` en `alembic upgrade head`.

- `2a01729` — `alembic.ini` no tenía `prepend_sys_path`. El comando `alembic`
  (a diferencia de `python -m alembic`) no agrega el directorio actual a
  `sys.path`, así que `env.py` no podía importar `app.database`. Reproducido
  local exactamente con el mismo traceback, arreglado con
  `prepend_sys_path = .`, confirmado que desaparece.
- **Sospecha:** esto probablemente venía fallando en silencio desde que se
  agregó `set -e` (`6e69664`, mismo día ~16:57) — antes fallaba callado y
  arrancaba con el código viejo. Verificar en el dashboard de Render que el
  deploy post-`2a01729` haya quedado en verde.

### 6. Unidad de stock de "masa" mal escalada (encontrado después, en paralelo)
- `04165a6` — Para una receta de masa, "u" de stock DEBE ser un lote (1.5
  lotes = 1.5u en el estante), no inflado por `porciones_por_lote`. Antes
  `cantidad_en_porciones()` multiplicaba antes de pasarlo a
  `producir_producto`, lo que sin querer arreglaba el descuento de
  ingredientes pero también inflaba el stock propio de la masa (1.5 lotes
  quedaban registrados como 13.5u). Separa `lotes` (para escalar
  ingredientes/subrecetas) de `cantidad_producida` (cantidad física real
  agregada al stock del producto). Este commit es la explicación de por qué
  "Masa de Croissant" mostraba 12,17u en pantalla — quedó resuelto acá.
  - También corrige `deducir_congelado_fifo()`: no tenía clamp de faltante
    (a diferencia de la versión de materia prima), así que una salida mayor
    al stock disponible registraba el pedido completo en vez de lo que
    realmente salió.
  - `scripts/corregir_lotes_masa.py` recalcula los registros reales de Masa
    Croissant/Medialuna. `scripts/reconciliar_ledger_congelado.py` rellena
    movimientos `carga_inicial` para ~20 productos cuyo stock histórico se
    cargó directo (vía `load_historical.py`) sin movimiento que lo respalde
    (por eso Croissant llegó a mostrar -134 en vez de 7).
- `05f4056` — consolida filas de ajuste sobrantes en Masa Croissant/Medialuna
  que quedaron de dos rondas de corrección el mismo día (verificado: el
  total neto no cambia).

### 7. Ledger calculado vs. conteo manual (feature nueva, no bug)
- `ca1c612` / `ce0a225` — Stock Congelado y Stock Materia Prima ahora
  muestran el saldo **calculado** (acumulado desde el ledger de
  `MovimientoStock`) al lado del conteo manual, en vez de solo sumar filas
  crudas de `StockCongelado`/`InventarioRegistro` (que se editan in-place y
  no reflejan producción/consumo real). `historial_movimientos_acumulado()`
  generaliza la lógica para ambos tipos de stock. Celdas con diferencia >0.5
  entre calculado y conteo real se marcan.
- `42ac994` — el gráfico de evolución usa esos mismos valores calculados
  (antes casi todos los productos tenían un solo punto manual y Recharts no
  podía dibujar una línea).

### 8. Focaccia (trabajo nuevo, no relacionado al bug de manteca)
- `0db51db`, `479ac97`, `4337b70` — receta de Focaccia rehecha con cantidades
  reales, nueva subreceta "Pure" (papa deshidratada + agua), tareas de
  calendario agregadas (antes no existían), precio de Papa Deshidratada
  cargado (estaba en $0), y un bug de unidades (litro vs. gramos) en la
  línea de agua de "Pure" que rompía la producción de Focaccia siempre (no
  solo en fechas pasadas).

### 9. Documentación
- `392151a`, `6f4e03c`, `ccec831` — todo lo de arriba (patrón de subreceta sin
  stock, ledger calculado, Focaccia, `movimiento_no_revertido`) documentado
  en `CLAUDE.md` para que quede como referencia permanente del proyecto.

---

## Estado al cierre de esta sesión

- **Todo commiteado y pusheado.** `git log origin/main..HEAD` vacío.
- Pendiente sin resolver de esta sesión: **ninguno conocido** — la pregunta
  de por qué Masa de Croissant mostraba 12,17u quedó respondida por `04165a6`
  (unidad de stock mal escalada, ya corregido).

## Cosas para verificar la próxima vez que se entre

1. **Confirmar en el dashboard de Render** que el deploy después de `2a01729`
   quedó verde (no se pudo verificar desde acá por falta de acceso al panel).
2. **Harina Pastelera está en 0kg** — Pan Suizo la necesita (1,5kg/lote). No es
   un bug, es una alerta de reposición real.
3. Después de tantas correcciones de ledger el mismo día, vale la pena un
   vistazo rápido a `/api/dashboard/reconciliacion` con un rango que incluya
   un conteo manual real antes y después (el rango por defecto de 7 días no
   sirve si no hay un conteo previo al lunes).
4. Revisar visualmente en el navegador el nuevo flujo de Focaccia (calendario
   + producción) ya que se reescribió la receta y las tareas el mismo día que
   se escribió esto.

## Aprendizajes de arquitectura (por si hace falta tocar `stock.py` de nuevo)

- **Dos grafos distintos, no intercambiables:** `lineas_receta.subreceta_id`
  es el grafo de **costeo** (puede saltar niveles, ej. un terminado referencia
  el bastón directo para el costo aunque físicamente pase por un "crudo"
  intermedio). `producto_padre_id`/`cantidad_por_padre` es el grafo de
  **stock físico**, un nivel a la vez. Antes de hacer que una línea de
  subreceta descuente stock, hay que chequear toda la cadena de
  `producto_padre_id` (no solo el padre directo) para no descontar dos veces
  — ver `_es_ancestro_congelado()`.
- **"u" de stock de una masa = 1 lote de receta**, no porciones. Ver `04165a6`.
- **Nunca editar filas de `MovimientoStock` a mano** — es un ledger append-only,
  las reversiones agregan filas compensatorias y retaggean, no borran.
- El stock "actual" de materia prima sale del **último conteo manual**
  (`InventarioRegistro`), no de una suma automática — por eso un bug en el
  ledger no corrompe el número que ve el usuario, pero sí rompe la
  reconciliación y los gráficos hasta que se corrige.
