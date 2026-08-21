"use client";

import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import MermaForm from "../MermaForm";

export default function NuevaMermaPage() {
  const router = useRouter();
  const { toast } = useToast();

  async function handleSubmit(body: Record<string, unknown>) {
    await apiFetch("/api/mermas", {
      method: "POST",
      body: JSON.stringify(body),
    });
    toast("Merma registrada correctamente");
    router.push("/mermas");
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/mermas")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Registrar Merma
        </h1>
      </div>

      <MermaForm
        submitLabel="Registrar Merma"
        onCancel={() => router.push("/mermas")}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
