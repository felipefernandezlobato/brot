import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface PermissionsMap {
  role: string;
  all_allowed?: boolean;
  permissions?: Record<string, boolean>;
}

let cachedPermissions: PermissionsMap | null = null;

export async function loadPermissions(): Promise<PermissionsMap> {
  if (cachedPermissions) return cachedPermissions;
  const perms = await apiFetch<PermissionsMap>("/api/permisos/mi-rol");
  cachedPermissions = perms;
  return perms;
}

export function clearPermissionsCache() {
  cachedPermissions = null;
}

export function usePermission(module: string, action: string): boolean | null {
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    loadPermissions().then((perms) => {
      if (perms.all_allowed) {
        setAllowed(true);
      } else {
        setAllowed(perms.permissions?.[`${module}.${action}`] ?? false);
      }
    });
  }, [module, action]);

  return allowed;
}
