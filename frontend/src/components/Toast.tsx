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
