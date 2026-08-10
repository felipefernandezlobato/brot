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
