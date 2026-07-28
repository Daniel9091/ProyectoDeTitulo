"""
generate_linea_1_scenario.py — Genera los parámetros y bloques de código de linea_1.py
a partir de la Matriz Origen-Destino del Metro de Santiago Línea 1.

Uso:
    python simulation_builder/generate_linea_1_scenario.py

Input:  Matriz_Origen_Destino_Linea_1_Metro_Santiago.csv  (misma carpeta)
Output: simulation_builder/linea_1_generated.txt

El archivo de salida tiene dos secciones para copiar y pegar en linea_1.py:
    1. Parámetros (X_Sn, DEST_FROM_n, RATE_Sn, VM_RATE_Sn)
    2. Bloques build() (create_station, belt_end_x, junction_points)

Unidades del CSV: pasajeros/hora
Unidades de salida: RATE en pasajeros/segundo (dividido entre 3600)
"""

import csv
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
# Path(__file__).parent resuelve la carpeta donde vive este script,
# sin importar desde dónde lo ejecutes. Así el CSV siempre se busca relativo
# al archivo, no al directorio de trabajo del terminal.

SCRIPT_DIR  = Path(__file__).parent
CSV_PATH    = SCRIPT_DIR / "Matriz_Origen_Destino_Linea_1_Metro_Santiago.csv"
OUTPUT_PATH = SCRIPT_DIR / "linea_1_generated.txt"

SECONDS_PER_HOUR = 3600

# ─── Parámetro de diseño ──────────────────────────────────────────────────────
# Debe coincidir con VM_CAPACITY en linea_1.py.
# Se usa para calcular VM_RATE = RATE / VM_CAPACITY, que es el número de VMs
# por segundo que la estación necesita solicitar asumiendo que cada VM sale lleno.
# En la práctica los VMs no siempre salen llenos, así que este valor es el piso
# mínimo teórico — un punto de partida para calibrar.

VM_CAPACITY = 6


# ─── Lectura ──────────────────────────────────────────────────────────────────

def read_od_matrix(csv_path: Path) -> tuple[list[str], list[list[float]]]:
    """
    Lee la matriz OD desde el CSV y retorna nombres de estaciones y valores.

    El CSV tiene formato:
        - Primera fila: encabezado — primera celda es label, resto son nombres de destinos
        - Cada fila siguiente: nombre de origen + 27 valores float separados por ';'

    Abrimos con utf-8-sig para que Python elimine automáticamente el BOM
    (Byte Order Mark) que agrega Excel al guardar como CSV UTF-8. Sin esto,
    el nombre de la primera estación llevaría caracteres basura adelante.
    """
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")

        header = next(reader)
        # header[0] es la etiqueta de la esquina ("Estación/Estación") — la descartamos
        # header[1:] son los 27 nombres de estaciones destino, en el mismo orden que las filas
        station_names = header[1:]

        matrix = []
        for row in reader:
            # row[0] es el nombre de la estación origen — ya lo tenemos de station_names
            values = [float(v) for v in row[1:]]
            matrix.append(values)

    return station_names, matrix


# ─── Cálculo ──────────────────────────────────────────────────────────────────

def compute_params(
    station_names: list[str],
    matrix: list[list[float]],
) -> list[dict]:
    """
    Calcula RATE y DEST para cada estación a partir de la matriz OD.

    La matriz OD tiene un significado claro: matrix[i][j] = pasajeros/hora
    que viajan desde la estación i hasta la estación j.

    De cada fila i se extraen dos cosas:

    ── TASA DE GENERACIÓN (RATE) ────────────────────────────────────────────
    La suma de toda la fila i da el total de pasajeros que SALEN de i por hora,
    independientemente de a dónde vayan:

        row_sum = sum(matrix[i][j] for all j ≠ i)

    Dividir por 3600 convierte de pasajeros/hora a pasajeros/segundo,
    que es la unidad que usa el simulador:

        RATE[i] = row_sum / 3600

    Ejemplo real — San Pablo (i=0):
        row_sum = 2047.25 pax/hora
        RATE    = 2047.25 / 3600 = 0.5687 pax/seg  (~1 pax cada 1.76 s)

    Ejemplo real — U. de Chile (i=12):
        row_sum = 5414.73 pax/hora
        RATE    = 5414.73 / 3600 = 1.504 pax/seg   (~1 pax cada 0.66 s)

    ── PROBABILIDADES DE DESTINO (DEST) ─────────────────────────────────────
    El simulador no trabaja con flujos absolutos sino con probabilidades:
    dado que nació un pasajero en i, ¿con qué probabilidad va a j?

    Esto es una probabilidad condicional. Se obtiene dividiendo cada celda
    de la fila por el total de la fila:

        P(destino=j | origen=i) = matrix[i][j] / row_sum

    Ejemplo real — San Pablo → U. de Chile:
        P = 280.56 / 2047.25 = 0.1371  (el destino más popular desde San Pablo)

    La diagonal siempre es 0.0 en la OD (nadie viaja a su propia estación),
    pero la excluimos explícitamente con j != i por robustez.
    Solo incluimos destinos con flujo > 0 para no llenar el dict con ceros.

    Los IDs son 1-indexed (j+1) para coincidir con la convención del simulador.
    """
    n = len(station_names)
    params = []

    for i, row in enumerate(matrix):
        station_id = i + 1  # El simulador usa IDs base-1

        # Suma de todos los flujos salientes, excluyendo la diagonal explícitamente
        row_sum = sum(v for j, v in enumerate(row) if j != i)

        # Pasajeros/hora → pasajeros/segundo
        rate = row_sum / SECONDS_PER_HOUR

        # Probabilidad condicional P(destino=j | origen=i) para cada j válido.
        # Redondeamos a 4 decimales: la suma puede quedar en 0.9999 por redondeo,
        # lo cual es irrelevante para el simulador.
        dest = {
            j + 1: round(row[j] / row_sum, 4)
            for j in range(n)
            if j != i and row[j] > 0
        }

        params.append({
            "id":   station_id,
            "name": station_names[i],
            "rate": rate,
            "dest": dest,
        })

    return params


# ─── Formateo de parámetros ───────────────────────────────────────────────────

def format_params(params: list[dict]) -> str:
    """
    Genera el bloque de parámetros para pegar en la sección superior de linea_1.py.

    Produce:
        X_Sn        — posición en metros (espaciado uniforme 1000 m entre estaciones)
        DEST_FROM_n — dict de probabilidades de destino (sin la propia estación)
        RATE_Sn     — tasa en pasajeros/segundo
        VM_RATE_Sn  — tasa de vehículos/segundo = RATE_Sn / VM_CAPACITY

    VM_RATE es el piso teórico: asume que cada VM sale completamente lleno.
    En la práctica el sistema necesitará más VMs (VMs no siempre salen llenos),
    así que este valor es un punto de partida para calibrar, no el valor final.

    El espaciado uniforme de 1000 m es también un punto de partida.
    Si consigues las distancias reales entre estaciones de la L1, reemplázalos.
    """
    lines = []

    lines.append("# ── Posición X de cada estación (metros) ────────────────────────────────────")
    lines.append("# Espaciado uniforme 1000 m; S1 parte en 500 para dejar margen al inicio del belt")
    for p in params:
        x = (p["id"] - 1) * 1000 + 500
        lines.append(f"X_S{p['id']} = {x}.0   # {p['name']}")
    lines.append("")

    lines.append("# ── Probabilidades de destino por estación ──────────────────────────────────")
    for p in params:
        lines.append(f"DEST_FROM_{p['id']} = {p['dest']}  # {p['name']}")
    lines.append("")

    lines.append("# ── Tasas de generación ─────────────────────────────────────────────────────")
    lines.append("# RATE     = pasajeros/seg que genera la estación (del CSV, convertido de hora a segundo)")
    lines.append("# VM_RATE  = VMs/seg que la estación solicita = RATE / VM_CAPACITY")
    lines.append("#            Piso teórico: asume VMs llenos al salir. Ajusta si ves muchos VMs vacíos.")
    for p in params:
        rate_rounded = round(p["rate"], 6)
        lines.append(f"RATE_S{p['id']}    = {rate_rounded}   # {p['name']}")
        lines.append(f"VM_RATE_S{p['id']} = RATE_S{p['id']} / VM_CAPACITY")
        lines.append("")

    return "\n".join(lines)


# ─── Formateo de bloques build() ─────────────────────────────────────────────

def format_build_blocks(params: list[dict]) -> str:
    """
    Genera los bloques de código para pegar dentro de build() en linea_1.py.

    Produce:
        1. Los 27 bloques create_station / connect_station_to_network
        2. El cálculo de belt_end_x con max() sobre todos los j_dn_N
        3. El dict junction_points para ContinuousTrain

    Cada estación queda en su propio bloque explícito (sin for) para que
    puedas cambiar num_lanes u otros parámetros individualmente más adelante.
    num_lanes=1 es el valor por defecto — ajústalo estación por estación.
    """
    lines = []

    # Bloques create_station
    for p in params:
        n = p["id"]
        separator = "─" * max(1, 48 - len(p["name"]))
        lines.append(f"    # ── Estación {n} — {p['name']} {separator}")
        lines.append(f"    s{n}, up{n}, l{n}, dn{n}, j_up_{n}, j_dn_{n} = create_station(")
        lines.append(f"        station_id={n},")
        lines.append(f"        station_origin=Vector3(X_S{n}, STATION_Y, STATION_Z),")
        lines.append(f"        num_lanes=1,               # ajusta para esta estación")
        lines.append(f"        passenger_rate=RATE_S{n},")
        lines.append(f"        destination_probabilities=DEST_FROM_{n},")
        lines.append(f"        vm_request_rate=VM_RATE_S{n},")
        lines.append(f"        rng=rng, id_generator=pid_gen, id_alloc=alloc,")
        lines.append(f"        recorder=recorder,")
        lines.append(f"    )")
        lines.append(f"    connect_station_to_network(network, up{n}, l{n}, dn{n}, j_up_{n}, j_dn_{n})")
        lines.append(f"    stations[{n}] = s{n}")
        lines.append("")

    # belt_end_x
    dn_refs = ", ".join(f"j_dn_{p['id']}.belt_x" for p in params)
    lines.append("    # ── Belt ─────────────────────────────────────────────────────────────────")
    lines.append(f"    belt_end_x = max({dn_refs}) + BELT_MARGIN")
    lines.append("")

    # junction_points
    lines.append("    # ── junction_points para ContinuousTrain ────────────────────────────────")
    lines.append("    junction_points = {")
    for p in params:
        n = p["id"]
        lines.append(f"        {n}: j_up_{n}.belt_x,")
    lines.append("    }")

    return "\n".join(lines)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    station_names, matrix = read_od_matrix(CSV_PATH)

    if len(station_names) != 27 or len(matrix) != 27:
        raise ValueError(
            f"Se esperaban 27 estaciones, se encontraron {len(station_names)} columnas "
            f"y {len(matrix)} filas. Revisa el CSV."
        )

    params = compute_params(station_names, matrix)

    separator = "=" * 80

    output = "\n".join([
        "# " + separator,
        "# SECCIÓN 1 — Pegar en la zona de parámetros (arriba del build())",
        "# " + separator,
        "",
        format_params(params),
        "",
        "# " + separator,
        "# SECCIÓN 2 — Pegar dentro de build(), reemplazando los bloques de estaciones",
        "# " + separator,
        "",
        format_build_blocks(params),
    ])

    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Generado: {OUTPUT_PATH}")
    print(f"Estaciones procesadas: {len(params)}")


if __name__ == "__main__":
    main()
