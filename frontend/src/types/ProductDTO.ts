export interface ProductDTO {
  id: number;
  titulo: string;
  precio: number;
  descripcion?: string;
  imagen?: string;
  imagenes?: {
    url: string;
    is_main: boolean;
  }[];
}