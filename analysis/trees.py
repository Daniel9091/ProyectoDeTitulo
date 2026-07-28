"""
Questions answered:
  1. ¿Qué andén elige el junction para cada VM?                 → _routing_balance
  2. ¿Cuál es la razón de entrada al junction por estación?     → _reason_distribution
  3. ¿Cómo de lleno está el árbol cuando entra un VM?           → _load_at_entry
  4. ¿Qué margen de seguridad hay respecto al vecino más joven? → _entry_margin
  5. ¿Hay colisiones físicas en los árboles?                    → _collision_summary

Nota: no incluye gráfico de entradas forzadas por estación —
ese análisis ya existe en slot_labels (slot_labels_forced_entries.png).

Report:  trees.txt
Charts:
  trees_routing_balance.png  — stacked bar: entradas por andén y estación
  trees_reason_dist.png      — stacked bar: razón de entrada por estación
  trees_load_at_entry.png    — histograma por estación: ocupación del árbol al entrar
  trees_entry_margin.png     — histograma dual: distancia al vecino existente (normal vs forzada)

Required event types (SP5): tree_vm_entered
Optional: track_collision_started, track_collision_ended

Usage:
  python -c "from analysis.trees import run; run()"
"""

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from collections import defaultdict

from analysis._shared import resolve_run, connect, get_output_dir, save_fig, get_event_types, Reporter, station_x_ticks
from analysis._style  import setup, PALETTE, TITLE_SIZE, FIG_BAR, FIG_DUAL, BAR_KWARGS, fig_for_stations


_SP5_REQUIRED = {'tree_vm_entered'}

_REASON_COLORS = {
    'reserved':    PALETTE['azul'],
    'destination': PALETTE['verde'],
    'demand':      PALETTE['violeta'],
    'unplanned':   PALETTE['naranja'],
}
_TREE_COLORS = [
    PALETTE['azul'], PALETTE['verde'], PALETTE['naranja'], PALETTE['violeta'],
]


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "trees")
    setup()

    types = get_event_types(events_path, con)

    rep.print("\n=== ÁRBOLES Y JUNCTION ROUTING (SP5) ===")

    if not (_SP5_REQUIRED & types):
        rep.print("  [sin datos] No hay eventos SP5 en esta corrida.")
        rep.save()
        con.close()
        return

    _routing_balance(con, rep, out_dir)
    _reason_distribution(con, rep, out_dir)
    _load_at_entry(con, rep, out_dir)
    _entry_margin(con, rep, out_dir)
    _collision_summary(con, rep, types, out_dir)

    rep.save()
    con.close()


# ── 1. Balance de andenes ──────────────────────────────────────────────────────

def _routing_balance(con, rep, out_dir):
    """
    ¿Usa el junction un solo andén o balancea la carga entre varios?
    Ideal: distribución uniforme. Un andén dominante indica desbalance.
    """
    rows = con.execute("""
        SELECT station_id, tree_idx, COUNT(*) AS cnt
        FROM events
        WHERE type = 'tree_vm_entered'
        GROUP BY station_id, tree_idx
        ORDER BY station_id, tree_idx
    """).fetchall()

    stations = sorted({r[0] for r in rows})
    trees    = sorted({r[1] for r in rows})
    data     = defaultdict(lambda: defaultdict(int))
    for sid, tidx, cnt in rows:
        data[sid][tidx] = cnt

    rep.print("\n--- 1. Balance de andenes elegidos por junction ---")
    rep.print("    (ideal: cada estación distribuye entradas uniformemente entre andenes)")
    for sid in stations:
        total = sum(data[sid].values())
        parts = [
            f"andén {t}: {data[sid][t]} ({100 * data[sid][t] / total:.1f}%)"
            for t in trees if data[sid][t]
        ]
        rep.print(f"  Estación {sid}: {total} entradas | " + " | ".join(parts))

    fig, ax = plt.subplots(figsize=fig_for_stations(len(stations)))
    x       = range(len(stations))
    bottoms = [0] * len(stations)
    for i, tidx in enumerate(trees):
        vals  = [data[sid][tidx] for sid in stations]
        color = _TREE_COLORS[i % len(_TREE_COLORS)]
        ax.bar(x, vals, bottom=bottoms, label=f"Andén {tidx}", color=color, **BAR_KWARGS)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    station_x_ticks(ax, stations)

    ax.set_ylabel("Entradas al árbol UP")
    ax.set_title(
        "Distribución de andenes elegidos por junction\n"
        "(¿balancea la carga o favorece siempre el mismo andén?)",
        fontsize=TITLE_SIZE,
    )
    ax.legend(title="Andén (UP tree)")
    ax.yaxis.grid(True)
    save_fig("trees_routing_balance", out_dir)
    plt.close()


# ── 2. Razón de entrada ────────────────────────────────────────────────────────

def _reason_distribution(con, rep, out_dir):
    """
    ¿Por qué llega el VM al junction?
    'reserved'    → tenía reserva garantizada para esta estación (la más segura).
    'destination' → tenía destino fijado en este slot (baja pasajeros aquí).
    'demand'      → una demanda de pasajeros lo atrajo a esta estación.
    La razón refleja la rama del Brain que procesó el cruce — cada VM suma a una sola barra.
    """
    rows = con.execute("""
        SELECT station_id, reason, COUNT(*) AS cnt
        FROM events
        WHERE type = 'tree_vm_entered'
        GROUP BY station_id, reason
        ORDER BY station_id, reason
    """).fetchall()

    stations = sorted({r[0] for r in rows})
    reasons  = sorted({r[1] for r in rows})
    data     = defaultdict(lambda: defaultdict(int))
    for sid, reason, cnt in rows:
        data[sid][reason] = cnt

    rep.print("\n--- 2. Razón de entrada al junction ---")
    rep.print("    (cada VM suma a UNA sola razón — la rama del Brain que lo procesó)")
    for sid in stations:
        total = sum(data[sid].values())
        parts = [
            f"{r}: {data[sid][r]} ({100 * data[sid][r] / total:.1f}%)"
            for r in reasons if data[sid][r]
        ]
        rep.print(f"  Estación {sid}: " + " | ".join(parts))

    fig, ax = plt.subplots(figsize=fig_for_stations(len(stations)))
    x       = range(len(stations))
    bottoms = [0] * len(stations)
    for reason in reasons:
        vals  = [data[sid][reason] for sid in stations]
        color = _REASON_COLORS.get(reason, PALETTE['violeta'])
        ax.bar(x, vals, bottom=bottoms, label=reason, color=color, **BAR_KWARGS)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    station_x_ticks(ax, stations)

    ax.set_ylabel("Entradas al árbol UP")
    ax.set_title(
        "Razón de entrada al junction por estación\n"
        "(reserved = garantizado | destination = pasajeros bajan | demand = demanda activa)",
        fontsize=TITLE_SIZE,
    )
    ax.legend(title="Razón")
    ax.yaxis.grid(True)
    save_fig("trees_reason_dist", out_dir)
    plt.close()


# ── 3. Ocupación del árbol al entrar ──────────────────────────────────────────

def _load_at_entry(con, rep, out_dir):
    """
    ¿Cuántos VMs hay en el árbol UP cuando llega uno nuevo?
    Un árbol siempre lleno (cerca del máximo) indica que la capacidad del andén
    es el cuello de botella. Un árbol con pocos VMs tiene margen.
    Se muestra por estación para revelar diferencias entre andenes.
    """
    rows = con.execute("""
        SELECT station_id, vehicle_count_after, forced, COUNT(*) AS cnt
        FROM events
        WHERE type = 'tree_vm_entered'
        GROUP BY station_id, vehicle_count_after, forced
        ORDER BY station_id, vehicle_count_after
    """).fetchall()

    stations = sorted({r[0] for r in rows})

    rep.print("\n--- 3. Ocupación del árbol UP al momento de entrada ---")
    rep.print("    (vehicle_count_after = VMs en el árbol tras insertar el nuevo, por estación)")
    for sid in stations:
        vals_norm  = []
        vals_force = []
        for s, vc, forced, cnt in rows:
            if s != sid:
                continue
            lst = vals_force if forced else vals_norm
            lst.extend([vc] * cnt)
        if vals_norm:
            s = sorted(vals_norm); n = len(s)
            rep.print(
                f"  Estación {sid} normal  (n={n}): "
                f"mediana={s[n//2]} | P90={s[int(n*.9)]} | max={s[-1]}"
            )
        if vals_force:
            s = sorted(vals_force); n = len(s)
            rep.print(
                f"  Estación {sid} FORZADA (n={n}): "
                f"mediana={s[n//2]} | max={s[-1]}"
            )

    # Subplots: uno por estación
    ncols = len(stations)
    fig, axes = plt.subplots(1, ncols, figsize=(5 * ncols, 4), sharey=False)
    if ncols == 1:
        axes = [axes]

    for ax, sid in zip(axes, stations):
        data_norm  = defaultdict(int)
        data_force = defaultdict(int)
        for s, vc, forced, cnt in rows:
            if s != sid:
                continue
            if forced:
                data_force[vc] = cnt
            else:
                data_norm[vc] = cnt

        counts       = sorted(set(data_norm) | set(data_force))
        norm_vals    = [data_norm[c]  for c in counts]
        forced_vals  = [data_force[c] for c in counts]

        ax.bar(counts, norm_vals,   label="Normal",  color=PALETTE['azul'],    **BAR_KWARGS)
        ax.bar(counts, forced_vals, bottom=norm_vals, label="Forzada",
               color=PALETTE['naranja'], **BAR_KWARGS)
        ax.set_xlabel("VMs en el árbol al entrar")
        ax.set_ylabel("Frecuencia")
        ax.set_title(f"Estación {sid}", fontsize=TITLE_SIZE - 1)
        ax.legend(fontsize=8)
        ax.yaxis.grid(True)

    fig.suptitle(
        "Ocupación del árbol UP al momento de entrada por estación\n"
        "(valores altos = andén casi lleno; forzadas ocurren en el extremo derecho)",
        fontsize=TITLE_SIZE,
    )
    plt.tight_layout()
    save_fig("trees_load_at_entry", out_dir)
    plt.close()


# ── 4. Margen de seguridad al entrar ──────────────────────────────────────────

def _entry_margin(con, rep, out_dir):
    """
    ¿Cuánto espacio hay entre el nuevo VM y el VM existente más joven?
    'nearest_existing_distance' = distancia del VM existente más cerca de la entrada
    en el momento en que llega el nuevo (lo que evalúa can_accept()).

    Entradas normales: el VM más joven existente debe estar suficientemente lejos
    (>= _min_safe_distance) para que can_accept() apruebe. El histograma debería
    estar desplazado a la derecha.

    Entradas forzadas: can_accept() devolvió False — el vecino estaba demasiado cerca.
    El histograma debería estar concentrado en valores pequeños.

    La línea vertical en 1m marca TRAIN_VM_LENGTH: si el vecino está a < 1m,
    hay colisión física en el eje del árbol.

    None = árbol vacío cuando llegó el VM (no hay vecino existente — sin riesgo).
    """
    rows = con.execute("""
        SELECT nearest_existing_distance, forced
        FROM events
        WHERE type = 'tree_vm_entered'
          AND nearest_existing_distance IS NOT NULL
    """).fetchall()

    normal_dists = [r[0] for r in rows if not r[1]]
    forced_dists = [r[0] for r in rows if r[1]]

    # Contar entradas sin vecino (árbol vacío)
    empty_rows = con.execute("""
        SELECT forced, COUNT(*) FROM events
        WHERE type = 'tree_vm_entered'
          AND nearest_existing_distance IS NULL
        GROUP BY forced
    """).fetchall()
    empty_normal = next((cnt for f, cnt in empty_rows if not f), 0)
    empty_forced = next((cnt for f, cnt in empty_rows if f), 0)

    rep.print("\n--- 4. Margen de seguridad al entrar (nearest_existing_distance) ---")
    rep.print("    (distancia del VM existente más joven cuando llega el nuevo)")
    rep.print(f"  Entradas a árbol vacío (sin vecino): normal={empty_normal} | forzada={empty_forced}")

    def stats(vals, label):
        if not vals:
            rep.print(f"  {label}: sin datos con vecino")
            return
        s = sorted(vals); n = len(s)
        rep.print(
            f"  {label} (n={n}): "
            f"min={s[0]:.2f}m | P10={s[n//10]:.2f}m | "
            f"mediana={s[n//2]:.2f}m | P90={s[int(n*.9)]:.2f}m | max={s[-1]:.2f}m"
        )

    stats(normal_dists, "Normal ")
    stats(forced_dists, "Forzada")
    if forced_dists:
        under1 = sum(1 for d in forced_dists if d < 1.0)
        rep.print(
            f"  Forzadas con vecino a < 1.0m (colisión física): "
            f"{under1}/{len(forced_dists)} ({100*under1/len(forced_dists):.1f}%)"
        )

    if not normal_dists and not forced_dists:
        rep.print("  [sin datos con vecino para graficar]")
        return

    fig, ax = plt.subplots(figsize=FIG_BAR)
    bins = 25
    if normal_dists:
        ax.hist(
            normal_dists, bins=bins, alpha=0.7,
            color=PALETTE['azul'], label=f"Normal (n={len(normal_dists)})",
            density=True,
        )
    if forced_dists:
        ax.hist(
            forced_dists, bins=bins, alpha=0.85,
            color=PALETTE['naranja'], label=f"Forzada (n={len(forced_dists)})",
            density=True,
        )
    ax.axvline(
        x=1.0, color=PALETTE['violeta'], linestyle='--', linewidth=1.5,
        label="TRAIN_VM_LENGTH = 1m\n(colisión física si vecino < 1m)",
    )
    ax.set_xlabel("Distancia del VM existente más joven al entrar el nuevo (m)")
    ax.set_ylabel("Densidad relativa")
    ax.set_title(
        "Margen de seguridad al entrar al árbol UP\n"
        "Entradas normales: vecino siempre lejos (can_accept ok) — "
        "Forzadas: vecino cercano (can_accept rechazó)",
        fontsize=TITLE_SIZE,
    )
    ax.legend()
    ax.yaxis.grid(True)
    save_fig("trees_entry_margin", out_dir)
    plt.close()


# ── 5. Colisiones en track ────────────────────────────────────────────────────

# ── 5. Colisiones en track ────────────────────────────────────────────────────

def _collision_summary(con, rep, types, out_dir):
    """
    Lista cada colisión física detectada: entre qué VMs, cuándo empezó,
    dónde (posición 3D), separación al inicio y al final, y cuándo paró.
    Si hay colisiones, genera un gráfico tipo Gantt (línea de tiempo).
    Si no hay colisiones pero SP5 está activo, lo confirma explícitamente.
    """
    rep.print("\n--- 5. Colisiones físicas en árboles (track_collision) ---")
    rep.print("    (colisión = dos VMs a < TRAIN_VM_LENGTH = 1m en el eje del árbol)")

    # Si SP5 no está implementado en esta corrida (no hay tree_vm_entered)
    if 'tree_vm_entered' not in types:
        rep.print("  [sin datos] SP5 no implementado en esta corrida.")
        return

    n_started = con.execute(
        "SELECT COUNT(*) FROM events WHERE type = 'track_collision_started'"
    ).fetchone()[0]

    if n_started == 0:
        rep.print("  Sin colisiones físicas detectadas.")
        rep.print("  (SP5 activo — MIN_VM_SEPARATION=2m mantiene separación > 1m"
                  " incluso en entradas forzadas)")
        return

    # ── Datos de inicio y fin ──────────────────────────────────────────────────
    starts = con.execute("""
        SELECT t, vm_id_1, vm_id_2, track_id, separation, pos_x, pos_y, pos_z
        FROM events
        WHERE type = 'track_collision_started'
        ORDER BY t
    """).fetchall()

    ends_raw = con.execute("""
        SELECT t, vm_id_1, vm_id_2, track_id, separation, reason
        FROM events
        WHERE type = 'track_collision_ended'
        ORDER BY t
    """).fetchall()

    # Indexar ends por (vm_id_1, vm_id_2, track_id) — misma clave que starts
    ends_map = {}
    for row in ends_raw:
        key = (row[1], row[2], row[3])
        ends_map[key] = row

    n_ended  = len(ends_raw)
    n_open   = n_started - n_ended

    rep.print(f"  Colisiones iniciadas:  {n_started}")
    rep.print(f"  Colisiones resueltas:  {n_ended}")
    rep.print(f"  Abiertas al cierre:    {n_open}")

    # ── Detalle por colisión ───────────────────────────────────────────────────
    rep.print("")
    rep.print("  Detalle por colisión:")

    gantt_rows = []   # (label, t_start, t_end, resolved, reason)

    for row in starts:
        t_start, vm1, vm2, track_id, sep_start, px, py, pz = row
        key = (vm1, vm2, track_id)
        end = ends_map.get(key)

        label = f"VM {vm1} ↔ VM {vm2}  (track {track_id})"

        pos_str = (
            f"({px:.1f}, {py:.1f}, {pz:.1f})"
            if px is not None else "posición desconocida"
        )
        sep_str = f"{sep_start:.3f}m" if sep_start is not None else "?"

        rep.print(f"    {label}")
        rep.print(f"      Inicio:    t={t_start:.1f}s | separación={sep_str} | pos={pos_str}")

        if end:
            t_end, _, _, _, sep_end, reason = end
            duration = t_end - t_start
            sep_end_str = f"{sep_end:.3f}m" if sep_end is not None else "?"
            rep.print(
                f"      Fin:       t={t_end:.1f}s | duración={duration:.2f}s"
                f" | separación final={sep_end_str} | motivo='{reason}'"
            )
            gantt_rows.append((label, t_start, t_end, True, reason))
        else:
            rep.print(f"      Fin:       sin resolver al cierre de la corrida")
            gantt_rows.append((label, t_start, None, False, ""))

    # ── Resumen de motivos de fin ──────────────────────────────────────────────
    if n_ended > 0:
        reasons = con.execute("""
            SELECT reason, COUNT(*) FROM events
            WHERE type = 'track_collision_ended'
            GROUP BY reason ORDER BY COUNT(*) DESC
        """).fetchall()
        rep.print("")
        rep.print("  Motivo de resolución:")
        for reason, cnt in reasons:
            rep.print(f"    '{reason}': {cnt}")

    # ── Gráfico Gantt ─────────────────────────────────────────────────────────
    if not gantt_rows:
        return

    t_max = con.execute("SELECT MAX(t) FROM events").fetchone()[0] or 1.0

    xs      = [r[1] / 60 for r in gantt_rows]
    t_ends  = [(r[2] if r[2] is not None else t_max) for r in gantt_rows]
    durs    = [(t_ends[i] - gantt_rows[i][1]) for i in range(len(gantt_rows))]
    colors  = [PALETTE['verde'] if r[3] else PALETTE['naranja'] for r in gantt_rows]
    n       = len(gantt_rows)

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 6),
                                          gridspec_kw={'height_ratios': [2, 1]})

    # Panel superior: scatter inicio vs duración
    ax_top.scatter(xs, durs, c=colors, s=40, alpha=0.8, zorder=3)
    ax_top.set_ylabel("Duración (s)")
    ax_top.set_title(
        f"Colisiones físicas en árboles  ({n} total)\n"
        f"cada punto = una colisión | eje X = cuándo empezó | eje Y = cuánto duró",
        size=TITLE_SIZE,
    )
    ax_top.yaxis.grid(True)
    ax_top.xaxis.grid(True)
    ax_top.set_axisbelow(True)

    # Panel inferior: histograma de inicios
    ax_bot.hist([x for x in xs], bins=30,
                color=PALETTE['azul'], alpha=0.85, edgecolor=PALETTE['azul'])
    ax_bot.set_xlabel("Tiempo de inicio (min)")
    ax_bot.set_ylabel("Cantidad")
    ax_bot.set_title("Distribución temporal de inicio de colisiones", size=TITLE_SIZE - 1)
    ax_bot.yaxis.grid(True)
    ax_bot.set_axisbelow(True)

    ax_top.legend(handles=[
        Line2D([0], [0], marker='o', color='w', markerfacecolor=PALETTE['verde'],
               markersize=8, label=f"Resuelta ({sum(r[3] for r in gantt_rows)})"),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=PALETTE['naranja'],
               markersize=8, label=f"Abierta al cierre ({sum(not r[3] for r in gantt_rows)})"),
    ], fontsize=9)

    plt.tight_layout()
    save_fig("trees_collisions_timeline", out_dir)
    plt.close()
