#!/usr/bin/env python3
"""
Actualización del catálogo de agencias Shalom desde FUENTES AUTORIZADAS.

Ejemplos:
  # Vista previa (no modifica nada) de un archivo oficial entregado por Shalom
  python scripts/actualizar_agencias.py --archivo agencias_oficial.csv --fuente "Archivo Shalom Pro 2026-11" --dry-run

  # Aplicar el archivo
  python scripts/actualizar_agencias.py --archivo agencias_oficial.csv --fuente "Archivo Shalom Pro 2026-11"

  # Sincronizar con la API autorizada configurada en .env (SHALOM_API_URL / SHALOM_API_KEY)
  python scripts/actualizar_agencias.py --api

Programación sugerida (Windows): Programador de tareas ejecutando `--api` cada semana.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.shalom_service import ShalomService  # noqa: E402

TIPOS = ("archivo_oficial", "snapshot_inicial", "api_autorizada", "manual")


def imprimir(resultado: dict) -> None:
    rep = resultado.get("reporte", {})
    dif = resultado.get("diferencias", {})
    print("=" * 70)
    print(resultado.get("mensaje", ""))
    if rep:
        print(f"Recibidos: {rep.get('recibidos')} | Válidos: {rep.get('total')} | Activos: {rep.get('activas')} | "
              f"Disponibles para clientes: {rep.get('publicables')}")
        print(f"Descartados inválidos: {rep.get('descartados_invalidos')} | Duplicados (id): {rep.get('duplicados_id')} | "
              f"Duplicados (dirección): {rep.get('duplicados_ubicacion')} | Inactivas: {rep.get('inactivas')} | "
              f"Sin destino: {rep.get('sin_destino')} | Sin coordenadas: {rep.get('sin_coordenadas')}")
    if dif:
        print(f"Nuevas: {dif.get('nuevas')} | Modificadas: {dif.get('modificadas')} | Retiradas: {dif.get('retiradas')} | "
              f"Desactivadas: {dif.get('desactivadas')} | Reactivadas: {dif.get('reactivadas')} | "
              f"Baja: {dif.get('porcentaje_baja')}%")
    print("=" * 70)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--archivo", help="Ruta a un archivo JSON o CSV de agencias")
    origen.add_argument("--api", action="store_true", help="Sincronizar con SHALOM_API_URL")
    p.add_argument("--fuente", default="", help="Descripción de la fuente (quién la entregó y cuándo)")
    p.add_argument("--tipo", default="archivo_oficial", choices=TIPOS, help="Tipo de fuente del archivo")
    p.add_argument("--formato", default="auto", choices=("auto", "json", "csv"))
    p.add_argument("--dry-run", action="store_true", help="Solo mostrar diferencias, sin aplicar")
    p.add_argument("--forzar", action="store_true", help="Aplicar aunque supere el umbral de bajas")
    p.add_argument("--json", action="store_true", help="Imprimir el resultado completo en JSON")
    args = p.parse_args()

    if args.api:
        resultado = asyncio.run(ShalomService.sincronizar_proveedor_externo(
            dry_run=args.dry_run, forzar=args.forzar, usuario="cli"))
    else:
        ruta = Path(args.archivo)
        if not ruta.exists():
            print(f"No existe el archivo: {ruta}")
            return 2
        from app.services.agency_normalizer import parsear_contenido
        registros = parsear_contenido(ruta.read_text(encoding="utf-8-sig"), args.formato)
        resultado = ShalomService.aplicar_actualizacion(
            registros, args.fuente or f"Archivo {ruta.name}", args.tipo,
            usuario="cli", forzar=args.forzar, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    imprimir(resultado)
    return 0 if resultado.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
