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
