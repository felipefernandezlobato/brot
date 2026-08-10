"use client";

import { usePermission } from "@/lib/permissions";

interface Props {
  module: string;
  action: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function PermissionGate({ module, action, children, fallback }: Props) {
  const allowed = usePermission(module, action);
  if (allowed === null) return null;
  if (!allowed) return fallback ?? null;
  return <>{children}</>;
}
