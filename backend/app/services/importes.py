"""Cuánto vale una línea, en un solo sitio.

La multiplicación `cantidad × precio_unitario` estaba escrita a mano en cinco
lugares del proyecto. Son dos renglones de aritmética, así que duplicarlas
nunca pareció grave — el problema no es escribirlas, es que **diverjan sin que
nadie lo note**. Una pantalla que suma distinto a otra no se ve rota, se ve
rara, y para cuando alguien pregunta ya nadie sabe cuál de las dos miente.

Que empezaban a divergir se notaba en que **no todas protegían el `None`**:
`list_todas_entregas` multiplicaba a pelo y las otras cuatro usaban `or 0`.
Eso parecía un fallo esperando a pasar y resultó que no: `precio_unitario`
lleva `default=0` en el modelo y `= 0` en el esquema de entrada, así que un
`None` se convierte en 0 al insertar y nunca llega a la multiplicación
(comprobado además contra producción: 0 nulos en 303 líneas). Las guardas son
defensivas, no arreglan nada. Se conservan igualmente, porque cuestan nada y
quitarlas obligaría al siguiente a volver a razonar todo esto.

Un `precio_unitario` en 0 cuenta como 0 y no como un error: el obrador a veces
entrega algo sin facturarlo, y el formulario lo deja hacer después de avisar
("se registrarán como entregados sin facturar").

`PedidoCliente` no pasa por aquí a propósito: el portal guarda `subtotal` y
`total` ya calculados al crear el pedido, y son inmutables. Recalcularlos
sería desconfiar de un dato que es más fiable que el cálculo.
"""


def importe_linea(linea) -> float:
    """`cantidad × precio_unitario` de una `LineaEntregaB2B`, con los vacíos a 0."""
    return (linea.cantidad or 0) * (linea.precio_unitario or 0)


def total_entrega(entrega) -> float:
    """Lo que vale una `EntregaB2B` entera.

    No sale de ninguna columna: a diferencia de `PedidoCliente.total`, una
    entrega no guarda su importe en la base y hay que sumarlo cada vez.
    """
    return sum(importe_linea(l) for l in entrega.lineas)
