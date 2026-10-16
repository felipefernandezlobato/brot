const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

/** Lee el mensaje de error que mande el backend, sin vomitar JSON en pantalla.
 *
 * Este archivo nacio como copia de `lib/api.ts` y se quedo sin el parseo que
 * aquel si tiene: hacia `throw new Error(await res.text())`, asi que un 422 le
 * mostraba al cliente el volcado crudo de Pydantic
 * (`[{"type":"string_too_short","loc":...}]`) dentro de un toast. Un empleado
 * lo interpreta; un cliente de la panaderia, no.
 */
async function mensajeDeError(res: Response): Promise<string> {
  const texto = await res.text();
  try {
    const data = JSON.parse(texto);
    if (typeof data?.detail === "string") return data.detail;
    // Pydantic manda una lista de errores por campo.
    if (Array.isArray(data?.detail)) {
      const msg = data.detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join(". ");
      if (msg) return msg;
    }
  } catch {
    // no era JSON: nos quedamos con el texto tal cual
  }
  return texto || `Error ${res.status}`;
}

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
  if (!res.ok) throw new Error(await mensajeDeError(res));
  // 204 y demas respuestas sin cuerpo: res.json() reventaria.
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json();
}

/** Igual que `apiClienteFetch` pero sin token ni redireccion al login: para
 * las pantallas a las que se llega JUSTAMENTE por no poder entrar (recuperar
 * contrasena, establecerla desde el enlace del correo). Con la version de
 * arriba, un 401 ahi mandaria al login en bucle. */
export async function apiPublicoFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(await mensajeDeError(res));
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json();
}
