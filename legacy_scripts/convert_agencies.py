#!/usr/bin/env python3
"""
Convert raw Shalom API response to our app's agencias_peru.json format.
Also update app to call the real API directly.
"""
import json
import re

# Load raw data
with open("shalom_agencies_raw.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

data = raw["data"]
print(f"Total raw agencies from API: {len(data)}")

# Show all fields available
if data:
    print("Fields:", list(data[0].keys()))
    print("\nSample:", json.dumps(data[0], ensure_ascii=False, indent=2)[:600])

# Count by departamento
from collections import Counter
deps = Counter(a["departamento"] for a in data)
print(f"\nDepartamentos ({len(deps)}):")
for dep, count in sorted(deps.items(), key=lambda x: -x[1]):
    print(f"  {dep}: {count}")

# Convert to our format
agencies = []
for a in data:
    # Parse nombre: "CAJAMARCA / HUALGAYOC / BAMBAMARCA / BAMBAMARCA"
    # Format: DEPARTAMENTO / PROVINCIA / DISTRITO / NOMBRE_AGENCIA
    nombre_parts = a.get("nombre", "").split("/")
    
    dep_raw = a.get("departamento", "").strip().title()
    prov_raw = a.get("provincia", "").strip().title()
    zona_raw = a.get("zona", "").strip().title()
    
    # Nombre display-friendly
    nombre_agencia = nombre_parts[-1].strip().title() if nombre_parts else zona_raw
    
    # Normalize departamento names
    dep_map = {
        "Lima Provincias": "Lima",
        "Callao": "Callao",
    }
    dep = dep_map.get(dep_raw, dep_raw)
    
    lat = None
    lon = None
    try:
        if a.get("latitud") and a.get("longitud"):
            lat = float(a["latitud"])
            lon = float(a["longitud"])
    except:
        pass
    
    # Build Maps URL
    maps_url = None
    if lat and lon:
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
    
    agency = {
        "id": str(a.get("ter_id", "")),
        "codigo": a.get("ter_abrebiatura", ""),
        "nombre": nombre_agencia,
        "nombre_completo": a.get("nombre", "").strip(),
        "departamento": dep,
        "provincia": prov_raw,
        "distrito": zona_raw,
        "direccion": (a.get("direccion") or "").strip(),
        "referencia": "",
        "telefono": a.get("telefono", ""),
        "horario": a.get("hora_atencion", ""),
        "latitud": lat,
        "longitud": lon,
        "maps_url": maps_url,
        "estado": a.get("estadoAgencia", ""),
        "origen": bool(a.get("origen")),
        "destino": bool(a.get("destino")),
    }
    agencies.append(agency)

# Sort by departamento, provincia, distrito, nombre
agencies.sort(key=lambda x: (x["departamento"], x["provincia"], x["distrito"], x["nombre"]))

print(f"\nConverted agencies: {len(agencies)}")

# Save
with open("data/agencias_peru.json", "w", encoding="utf-8") as f:
    json.dump(agencies, f, ensure_ascii=False, indent=2)

print("Saved to data/agencias_peru.json")

# Also save a grouped version for fast lookup
grouped = {}
for a in agencies:
    dep = a["departamento"]
    prov = a["provincia"]
    dist = a["distrito"]
    
    if dep not in grouped:
        grouped[dep] = {}
    if prov not in grouped[dep]:
        grouped[dep][prov] = {}
    if dist not in grouped[dep][prov]:
        grouped[dep][prov][dist] = []
    grouped[dep][prov][dist].append(a)

with open("data/agencias_grouped.json", "w", encoding="utf-8") as f:
    json.dump(grouped, f, ensure_ascii=False, indent=2)

print("Saved to data/agencias_grouped.json")

# Stats
print(f"\nFinal stats:")
print(f"  Agencias: {len(agencies)}")
print(f"  Departamentos: {len(grouped)}")
print(f"  Provincias: {sum(len(v) for v in grouped.values())}")
print(f"  Distritos: {sum(len(d) for v in grouped.values() for d in v.values())}")
