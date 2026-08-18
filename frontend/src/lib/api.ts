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
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") message = parsed.detail;
    } catch {
      // not JSON — use raw text as-is
    }
    throw new Error(message);
  }
  return res.json();
}
