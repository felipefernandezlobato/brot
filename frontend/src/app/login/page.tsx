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
