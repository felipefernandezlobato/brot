export interface User {
  id: number;
  name: string;
  role: "admin" | "staff";
}

export interface Cliente {
  id: number;
  email: string;
  nombre: string;
  telefono?: string;
  direccion?: string;
}

export interface Categoria {
  id: number;
  nombre: string;
  tipo: "ingrediente" | "receta";
  margen_objetivo?: number;
  orden?: number;
}

export interface Permission {
  id: number;
  role: string;
  module: string;
  action: string;
  allowed: boolean;
}
