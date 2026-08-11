"""
Slot label analysis (SP4) — reservas, demanda, destinos y entradas al junction.

Questions answered:
  1. How many labels of each type did each station place?      → _label_activity_by_station
  2. How healthy is the reservation range search?              → _reservation_health
  3. How well does the demand system fulfill its promises?     → _demand_health
  4. How are VM destinations being set?                        → _destination_flow
  5. How often does the system force a junction entry?         → _forced_entries
  6. Cross-check: are all reservations/demands accounted for? → _integrity_checks

Report:  slot_labels.txt
Charts:
  slot_labels_activity.png               — grouped bars: label counts per station
  slot_labels_reservation_priority.png   — pie: reservation priority breakdown
  slot_labels_reservation_offset.png     — bar: slot_offset distribution (−5 to +5)
  slot_labels_demand_health.png          — stacked bar + pie: fulfillment + priorities
  slot_labels_destination_flow.png       — stacked bars: destination source per station
  slot_labels_forced_entries.png         — stacked bars: forced vs normal per station

Required event types (SP4): slot_reserved, slot_demand_set, slot_destination_set,
  junction_vm_entered, junction_commitment_broken, slot_demand_cleared,
  slot_reservation_cleared

Usage:
  python -c "from analysis.slot_labels import run; run()"
"""

import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

from analysis._shared import resolve_run, connect, get_output_dir, save_fig, get_event_types, station_x_ticks, Reporter
from analysis._style  import setup,fig_for_stations, PALETTE, TITLE_SIZE, FIG_SQUARE, FIG_BAR, FIG_DUAL, BAR_KWARGS, PIE_KWARGS

_SP4_REQUIRED = {
    'slot_reserved', 'slot_demand_set',
    'slot_destination_set', 'junction_vm_entered',
}

def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "slot_labels")
    setup()

    types = get_event_types(events_path, con)

    rep.print("\n=== ETIQUETAS DE SLOT (SP4) ===")

    if not (_SP4_REQUIRED & types):
        rep.print("  [sin datos] No hay eventos SP4 en esta corrida.")
        rep.save()
        con.close()
        return

    _label_activity_by_station(con, rep, out_dir)
    _reservation_health(con, rep, out_dir, types)
    _demand_health(con, rep, out_dir, types)
    _destination_flow(con, rep, out_dir, types)
    _forced_entries(con, rep, out_dir, types)
    _integrity_checks(con, rep, types)
    _search_priority_distribution(con, rep, out_dir, types)
    _search_skip_reasons(con, rep, out_dir, types)
    _fallback_analysis(con, rep, out_dir, types)

    rep.save()
    con.close()


# ── 1. Actividad por estación ─────────────────────────────────────────────────

def _label_activity_by_station(con, rep, out_dir):
    """
    Grouped bar chart: label events per station.

    Questions: Which station dominates the labeling system? Is demand balanced?
    Text: event counts per station per label type.
    Chart: slot_labels_activity.png
    """
    rows = con.execute("""
        SELECT
            station_id,
            SUM(CASE WHEN type = 'slot_reserved'       THEN 1 ELSE 0 END) AS reservas,
            SUM(CASE WHEN type = 'slot_demand_set'      THEN 1 ELSE 0 END) AS demanda,
            SUM(CASE WHEN type = 'slot_destination_set' THEN 1 ELSE 0 END) AS destinos,
            SUM(CASE WHEN type = 'junction_vm_entered'  THEN 1 ELSE 0 END) AS entradas
        FROM events
        WHERE type IN (
            'slot_reserved', 'slot_demand_set',
            'slot_destination_set', 'junction_vm_entered'
        )
        GROUP BY station_id
        ORDER BY station_id
    """).fetchall()

    rep.print("\n[ Actividad de etiquetas por estación ]")
    rep.print(f"  {'Estación':<10} {'Reservas':>10} {'Demanda':>10} {'Destinos':>10} {'Entradas':>10}")
    for sid, res, dem, dst, ent in rows:
        rep.print(f"  S{sid:<9} {res:>10} {dem:>10} {dst:>10} {ent:>10}")



    stations_ids = [r[0] for r in rows]
    x = np.arange(len(stations_ids))
    w = 0.2
    fig, ax = plt.subplots(figsize=fig_for_stations(len(stations_ids)))
    ax.bar(x - 1.5*w, [r[1] for r in rows], w, label="Reservas",  color=PALETTE["azul"],    **BAR_KWARGS)
    ax.bar(x - 0.5*w, [r[2] for r in rows], w, label="Demanda",   color=PALETTE["verde"],   **BAR_KWARGS)
    ax.bar(x + 0.5*w, [r[3] for r in rows], w, label="Destinos",  color=PALETTE["violeta"], **BAR_KWARGS)
    ax.bar(x + 1.5*w, [r[4] for r in rows], w, label="Entradas",  color=PALETTE["naranja"], **BAR_KWARGS)
    station_x_ticks(ax, stations_ids)
    ax.set_title("Actividad de etiquetas por estación", size=TITLE_SIZE)
    ax.set_ylabel("Cantidad de eventos")
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_activity", out_dir)
    plt.close()


# ── 2. Salud de reservas ──────────────────────────────────────────────────────

_RESERVATION_PRIORITY_LABELS = {
    "dest_same_station":    "Destino = misma estación (mejor)",
    "demand_same_station":  "Demanda = misma estación",
    "empty_slot":           "Slot vacío",
    "clean_vm":             "VM sin destino conflictivo",
    "demand_other_station": "VM con demanda de otra estación",
    "dest_other_station":   "VM va a otra estación",
    "fallback_critical":    "Fallback crítico (saturación)",
}

_RESERVATION_PRIORITY_COLORS = {
    "dest_same_station":    PALETTE["verde"],
    "demand_same_station":  PALETTE["verde"],
    "empty_slot":           PALETTE["azul"],
    "clean_vm":             PALETTE["violeta"],
    "demand_other_station": "#5baee0",      
    "dest_other_station":   PALETTE["naranja"],
    "fallback_critical":    "#e6b800",      
}

def _reservation_health(con, rep, out_dir, types):
    """
    Priority pie + slot_offset histogram for slot_reserved events.

    Questions: How healthy is the range search? Is the system under stress
               (fallback_critical)? Where does it find slots relative to target?
    Charts: slot_labels_reservation_priority.png, slot_labels_reservation_offset.png
    """
    if 'slot_reserved' not in types:
        return

    stats = con.execute("""
        SELECT COUNT(*), ROUND(AVG(T_total),2), ROUND(AVG(accel),4),
               ROUND(MAX(ABS(accel)),4), ROUND(STDDEV(accel),4)
        FROM events WHERE type = 'slot_reserved'
    """).fetchone()
    total, avg_T, avg_a, max_a, std_a = stats

    pri_rows = con.execute("""
        SELECT priority, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_reserved'
        GROUP BY priority ORDER BY cnt DESC
    """).fetchall()

    rep.print("\n[ Salud del sistema de reservas ]")
    rep.print(f"  Total reservas: {total}")
    rep.print(f"  T_total prom: {avg_T} s  |  accel prom: {avg_a}  |  max |accel|: {max_a}  |  std: {std_a}")
    rep.print("  Prioridades:")
    for pri, cnt in pri_rows:
        label = _RESERVATION_PRIORITY_LABELS.get(pri, pri)
        rep.print(f"    {label:<45} {cnt:>6}  ({cnt/total*100:.1f}%)")

    # Pie de prioridades
    labels  = [_RESERVATION_PRIORITY_LABELS.get(p, p) for p, _ in pri_rows]
    values  = [c for _, c in pri_rows]
    colors  = [_RESERVATION_PRIORITY_COLORS.get(p, PALETTE["azul"]) for p, _ in pri_rows]

    fig, ax = plt.subplots(figsize=FIG_SQUARE)
    total = sum(values)
    legend_labels = [f"{l}  ({v/total*100:.1f}%)" for l, v in zip(labels, values)]
    wedges, _ = ax.pie(
        values, labels=None, colors=colors,
        **PIE_KWARGS,
    )
    ax.legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.45),
              fontsize=8, framealpha=0)

    ax.set_title("Prioridades de reserva", size=TITLE_SIZE)
    plt.tight_layout()
    save_fig("slot_labels_reservation_priority", out_dir)
    plt.close()

    # Histograma de offset
    off_rows = con.execute("""
        SELECT slot_offset, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_reserved'
        GROUP BY slot_offset ORDER BY slot_offset
    """).fetchall()

    offsets = [r[0] for r in off_rows]
    counts  = [r[1] for r in off_rows]
    colors_off = [
        PALETTE["naranja"] if o < 0 else PALETTE["verde"] if o == 0 else PALETTE["azul"]
        for o in offsets
    ]

    fig, ax = plt.subplots(figsize=FIG_BAR)
    ax.bar(offsets, counts, color=colors_off, **BAR_KWARGS)
    ax.axvline(0, color=PALETTE["verde"], linewidth=1.5, linestyle="--", alpha=0.8, label="Target exacto")
    ax.set_xlabel("Offset del slot elegido vs target (nº de slots)")
    ax.set_ylabel("Cantidad de reservas")
    ax.set_title("Distribución de offset de reserva", size=TITLE_SIZE)
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_reservation_offset", out_dir)
    plt.close()


# ── 3. Salud de demanda ───────────────────────────────────────────────────────

_DEMAND_PRIORITY_LABELS = {
    "reserved_same_station": "Slot ya reservado para esta estación",
    "dest_same_station":     "VM con destino = esta estación",
    "clean_vm":              "VM sin destino",
}

def _demand_health(con, rep, out_dir, types):
    """
    Stacked bar (fulfillment per station) + pie (priority breakdown).

    Questions: What fraction of demand promises are kept? Which stations have
               high breakage? Under what priority does the system find demand slots?
    Chart: slot_labels_demand_health.png
    """
    if 'slot_demand_set' not in types:
        return

    total_set = con.execute(
        "SELECT COUNT(*) FROM events WHERE type = 'slot_demand_set'"
    ).fetchone()[0]

    cleared_map = {
        r[0]: r[1]
        for r in con.execute("""
            SELECT reason, COUNT(*) FROM events
            WHERE type = 'slot_demand_cleared'
            GROUP BY reason
        """).fetchall()
    }
    fulfilled    = cleared_map.get("vm_entered_tree", 0)
    broken       = cleared_map.get("commitment_broken", 0)
    still_active = total_set - fulfilled - broken

    rep.print("\n[ Salud del sistema de demanda ]")
    rep.print(f"  Total demandas marcadas: {total_set}")
    rep.print(f"  Cumplidas (vm_entered_tree):  {fulfilled:>5}  ({fulfilled/total_set*100:.1f}%)")
    rep.print(f"  Rotas (commitment_broken):    {broken:>5}  ({broken/total_set*100:.1f}%)")
    rep.print(f"  Activas al cierre simulación: {still_active:>5}  ({still_active/total_set*100:.1f}%)")

    pri_rows = con.execute("""
        SELECT priority, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_demand_set'
        GROUP BY priority ORDER BY cnt DESC
    """).fetchall()
    rep.print("  Prioridades de búsqueda:")
    for pri, cnt in pri_rows:
        label = _DEMAND_PRIORITY_LABELS.get(pri, pri)
        rep.print(f"    {label:<45} {cnt:>6}  ({cnt/total_set*100:.1f}%)")

    if 'junction_commitment_broken' in types:
        broken_rows = con.execute("""
            SELECT station_id, COUNT(*) FROM events
            WHERE type = 'junction_commitment_broken'
            GROUP BY station_id ORDER BY station_id
        """).fetchall()
        if broken_rows:
            rep.print("  Promesas rotas por estación:")
            for sid, cnt in broken_rows:
                rep.print(f"    S{sid}: {cnt}")

    # Fulfillment stacked bar por estación
    stn_set = {
        r[0]: r[1]
        for r in con.execute("""
            SELECT station_id, COUNT(*) FROM events
            WHERE type = 'slot_demand_set'
            GROUP BY station_id ORDER BY station_id
        """).fetchall()
    }
    cleared_by_s = {
        r[0]: (r[1], r[2])
        for r in con.execute("""
            SELECT station_id,
                SUM(CASE WHEN reason = 'vm_entered_tree'   THEN 1 ELSE 0 END),
                SUM(CASE WHEN reason = 'commitment_broken' THEN 1 ELSE 0 END)
            FROM events WHERE type = 'slot_demand_cleared'
            GROUP BY station_id
        """).fetchall()
    }
    all_stations = sorted(stn_set.keys())

    s_set  = [stn_set.get(s, 0)                          for s in all_stations]
    s_ful  = [cleared_by_s.get(s, (0, 0))[0]             for s in all_stations]
    s_brk  = [cleared_by_s.get(s, (0, 0))[1]             for s in all_stations]
    s_act  = [s - f - b for s, f, b in zip(s_set, s_ful, s_brk)]

    x = np.arange(len(all_stations))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

    ax1.bar(x, s_ful, label="Cumplidas",         color=PALETTE["verde"],   **BAR_KWARGS)
    ax1.bar(x, s_brk, bottom=s_ful,              color=PALETTE["naranja"], label="Rotas", **BAR_KWARGS)
    ax1.bar(x, s_act, bottom=[f+b for f,b in zip(s_ful, s_brk)],
            color=PALETTE["azul"], label="Activas al cierre", **BAR_KWARGS)
    station_x_ticks(ax1, all_stations, xlabel_base="Estaciones")

    ax1.set_title("Promesas de demanda por estación", size=TITLE_SIZE)
    ax1.set_ylabel("Cantidad")
    ax1.legend()
    ax1.yaxis.grid(True)
    ax1.set_axisbelow(True)

    pri_labels = [_DEMAND_PRIORITY_LABELS.get(p, p) for p, _ in pri_rows]
    pri_vals   = [c for _, c in pri_rows]
    pri_colors = [PALETTE["verde"], PALETTE["azul"], PALETTE["violeta"]][:len(pri_rows)]
    ax2.pie(pri_vals, labels=None, colors=pri_colors,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            **PIE_KWARGS)
    ax2.legend(pri_labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
               fontsize=8, framealpha=0)
    ax2.set_title("Prioridades de demanda", size=TITLE_SIZE)

    plt.tight_layout()
    save_fig("slot_labels_demand_health", out_dir)
    plt.close()


# ── 4. Flujo de destinos ──────────────────────────────────────────────────────

_SOURCE_LABELS = {
    "boarding_commit":   "Commit de embarque",
    "reservations_pass": "Pase de reservas",
    "redirect":          "Redirección",
}
_SOURCE_COLORS = {
    "boarding_commit":   PALETTE["azul"],
    "reservations_pass": PALETTE["violeta"],
    "redirect":          PALETTE["naranja"],
}

def _destination_flow(con, rep, out_dir, types):
    """
    Stacked bar: how VM destinations are assigned per station.

    Questions: What fraction of VMs get their destination from each source?
               Is the redirect rate high (routing stress)?
    Chart: slot_labels_destination_flow.png
    """
    if 'slot_destination_set' not in types:
        return

    total = con.execute(
        "SELECT COUNT(*) FROM events WHERE type = 'slot_destination_set'"
    ).fetchone()[0]

    source_rows = con.execute("""
        SELECT source, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_destination_set'
        GROUP BY source ORDER BY cnt DESC
    """).fetchall()

    rep.print("\n[ Flujo de destinos de VM ]")
    rep.print(f"  Total slot_destination_set: {total}")
    for src, cnt in source_rows:
        rep.print(f"  {_SOURCE_LABELS.get(src, src):<35} {cnt:>6}  ({cnt/total*100:.1f}%)")

    # Stacked bar per station
    stn_src_rows = con.execute("""
        SELECT station_id, source, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_destination_set'
        GROUP BY station_id, source ORDER BY station_id, source
    """).fetchall()

    matrix = defaultdict(lambda: defaultdict(int))
    all_stations = sorted({r[0] for r in stn_src_rows})
    for sid, src, cnt in stn_src_rows:
        matrix[sid][src] = cnt

    x = np.arange(len(all_stations))
    fig, ax = plt.subplots(figsize=fig_for_stations(len(all_stations)))
    bottoms = np.zeros(len(all_stations))
    for src in ["boarding_commit", "reservations_pass", "redirect"]:
        vals = np.array([matrix[sid][src] for sid in all_stations], dtype=float)
        ax.bar(x, vals, bottom=bottoms,
               label=_SOURCE_LABELS.get(src, src),
               color=_SOURCE_COLORS[src], **BAR_KWARGS)
        bottoms += vals
    station_x_ticks(ax, all_stations)
    ax.set_title("Origen de destinos de VM por estación", size=TITLE_SIZE)
    ax.set_ylabel("Cantidad")
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_destination_flow", out_dir)
    plt.close()


# ── 5. Entradas forzadas ──────────────────────────────────────────────────────

def _forced_entries(con, rep, out_dir, types):
    """
    Stacked bar: forced vs normal junction entries per station.

    Questions: How often does force_add_vm trigger? Is any station under high pressure?
    Chart: slot_labels_forced_entries.png
    """
    if 'junction_vm_entered' not in types:
        return

    rows = con.execute("""
        SELECT
            station_id,
            SUM(CASE WHEN forced = true  THEN 1 ELSE 0 END) AS forced_count,
            SUM(CASE WHEN forced = false THEN 1 ELSE 0 END) AS normal_count
        FROM events WHERE type = 'junction_vm_entered'
        GROUP BY station_id ORDER BY station_id
    """).fetchall()

    total_f = sum(r[1] for r in rows)
    total_n = sum(r[2] for r in rows)
    total   = total_f + total_n

    rep.print("\n[ Entradas forzadas al junction ]")
    rep.print(f"  Total entradas: {total}  |  Normales: {total_n} ({total_n/total*100:.1f}%)  |  Forzadas: {total_f} ({total_f/total*100:.1f}%)")
    rep.print(f"  {'Estación':<10} {'Normal':>8} {'Forzada':>8} {'% Forzada':>10}")
    for sid, forced, normal in rows:
        tot = forced + normal
        pct = forced / tot * 100 if tot else 0
        rep.print(f"  S{sid:<9} {normal:>8} {forced:>8} {pct:>9.1f}%")

    x = np.arange(len(rows))
    station_ids = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=fig_for_stations(len(station_ids)))
    normals = [r[2] for r in rows]
    forceds = [r[1] for r in rows]
    ax.bar(x, normals, label="Normal",   color=PALETTE["azul"],    **BAR_KWARGS)
    ax.bar(x, forceds, bottom=normals,   color=PALETTE["naranja"], label="Forzada", **BAR_KWARGS)
    station_x_ticks(ax, station_ids)
    ax.set_title("Entradas al junction: normales vs forzadas", size=TITLE_SIZE)
    ax.set_ylabel("Cantidad de entradas")
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_forced_entries", out_dir)
    plt.close()


# ── 6. Cross-checks ───────────────────────────────────────────────────────────

def _integrity_checks(con, rep, types):
    """
    Text-only cross-checks: are all reservations/demands accounted for?

    Questions: Are there unbalanced event pairs? Any slot collisions?
               What is the real demand breakage rate?
    """
    rep.print("\n[ Cross-checks de integridad ]")

    if 'slot_reserved' in types and 'slot_reservation_cleared' in types:
        n_res = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_reserved'"
        ).fetchone()[0]
        n_clr = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_reservation_cleared'"
        ).fetchone()[0]
        in_flight = n_res - n_clr
        status = "OK" if in_flight >= 0 else "⚠ ALERTA doble-limpieza"
        rep.print(f"  slot_reserved: {n_res}  |  cleared: {n_clr}  |  en vuelo al cierre: {in_flight}  [{status}]")

    if 'slot_demand_set' in types and 'slot_demand_cleared' in types:
        n_set = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_demand_set'"
        ).fetchone()[0]
        n_clr = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_demand_cleared'"
        ).fetchone()[0]
        silent = n_set - n_clr
        pct    = silent / n_set * 100 if n_set else 0
        rep.print(f"  slot_demand_set: {n_set}  |  cleared: {n_clr}  |  sin evento de cierre: {silent} ({pct:.1f}%)")
        rep.print("    (limpiados silenciosamente por remove_vm — normal si hay demandas activas al cierre)")

    if 'slot_collision' in types:
        n_col = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_collision'"
        ).fetchone()[0]
        status = "OK — sin colisiones" if n_col == 0 else f"⚠ ALERTA: {n_col} colisiones"
        rep.print(f"  slot_collision: {n_col}  → {status}")

    if 'junction_commitment_broken' in types and 'slot_demand_set' in types:
        n_brk = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'junction_commitment_broken'"
        ).fetchone()[0]
        n_dem = con.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'slot_demand_set'"
        ).fetchone()[0]
        pct = n_brk / n_dem * 100 if n_dem else 0
        rep.print(f"  commitment_broken: {n_brk} / {n_dem} demandas = {pct:.1f}% tasa de rotura")


# ── 7. Prioridades de búsqueda de slots ───────────────────────────────────────

def _search_priority_distribution(con, rep, out_dir, types):
    """
    Grouped bar: qué prioridad eligió el sistema en demand vs reservation.
    Muestra si el sistema opera cómodo (P1-P3) o bajo estrés (P4-fallback).
    """
    if 'slot_search_completed' not in types:
        return

    rows = con.execute("""
        SELECT context, selected_priority, COUNT(*) AS cnt
        FROM events WHERE type = 'slot_search_completed'
        GROUP BY context, selected_priority
        ORDER BY context, cnt DESC
    """).fetchall()

    by_ctx = defaultdict(list)
    for ctx, pri, cnt in rows:
        by_ctx[ctx].append((pri, cnt))

    rep.print("\n[ Prioridades elegidas en búsqueda de slots ]")
    for ctx, items in sorted(by_ctx.items()):
        total = sum(c for _, c in items)
        rep.print(f"\n  Contexto: {ctx}  ({total} búsquedas)")
        for pri, cnt in items:
            rep.print(f"    {pri:<30} {cnt:>6}  ({cnt/total*100:.1f}%)")

    all_priorities = sorted({p for _, p, _ in rows})
    contexts = sorted(by_ctx.keys())
    x = np.arange(len(all_priorities))
    w = 0.35

    fig, ax = plt.subplots(figsize=FIG_BAR)
    ctx_colors = {"demand": PALETTE["azul"], "reservation": PALETTE["violeta"]}
    for i, ctx in enumerate(contexts):
        d = dict(by_ctx[ctx])
        vals = [d.get(p, 0) for p in all_priorities]
        offset = (i - len(contexts) / 2 + 0.5) * w
        ax.bar(x + offset, vals, w, label=ctx,
               color=ctx_colors.get(ctx, PALETTE["naranja"]), alpha=0.85, **BAR_KWARGS)

    ax.set_xticks(x)
    ax.set_xticklabels(all_priorities, rotation=25, ha='right', fontsize=8)
    ax.set_title("Prioridad elegida en búsqueda de slots", size=TITLE_SIZE)
    ax.set_ylabel("Búsquedas")
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_search_priorities", out_dir)
    plt.close()


# ── 8. Razones de descarte en ventana ────────────────────────────────────────

def _search_skip_reasons(con, rep, out_dir, types):
    """
    Grouped bar: por qué se descartaron candidatos en la ventana de búsqueda.
    Muestra qué limita la selección: saturación, falta de VM, conflictos de reserva.
    """
    if 'slot_search_completed' not in types:
        return

    rows = con.execute("""
        SELECT context, "window"
        FROM events WHERE type = 'slot_search_completed'
    """).fetchall()

    skip_counts = defaultdict(lambda: defaultdict(int))
    total_candidates = defaultdict(int)

    for ctx, window in rows:
        for entry in window:
            total_candidates[ctx] += 1
            reason = entry.get('skipped_reason')
            if reason is not None:
                skip_counts[ctx][reason] += 1

    rep.print("\n[ Razones de descarte de candidatos en ventana ]")
    for ctx in sorted(skip_counts):
        total = total_candidates[ctx]
        skipped = sum(skip_counts[ctx].values())
        rep.print(f"\n  Contexto: {ctx}  ({skipped}/{total} descartados = {skipped/total*100:.1f}%)")
        for reason, cnt in sorted(skip_counts[ctx].items(), key=lambda x: -x[1]):
            rep.print(f"    {reason:<25} {cnt:>6}  ({cnt/total*100:.1f}%)")

    all_reasons = sorted({r for ctx in skip_counts for r in skip_counts[ctx]})
    contexts = sorted(skip_counts.keys())
    x = np.arange(len(all_reasons))
    w = 0.35

    ctx_colors = {"demand": PALETTE["azul"], "reservation": PALETTE["violeta"]}
    fig, ax = plt.subplots(figsize=FIG_BAR)
    for i, ctx in enumerate(contexts):
        vals = [skip_counts[ctx].get(r, 0) for r in all_reasons]
        offset = (i - len(contexts) / 2 + 0.5) * w
        ax.bar(x + offset, vals, w, label=ctx,
               color=ctx_colors.get(ctx, PALETTE["naranja"]), alpha=0.85, **BAR_KWARGS)

    ax.set_xticks(x)
    ax.set_xticklabels(all_reasons, rotation=25, ha='right', fontsize=8)
    ax.set_title("Razones de descarte de candidatos en ventana", size=TITLE_SIZE)
    ax.set_ylabel("Candidatos descartados")
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_skip_reasons", out_dir)
    plt.close()


# ── 9. Análisis de fallback ───────────────────────────────────────────────────

def _fallback_analysis(con, rep, out_dir, types):
    """
    Timeline scatter de cuándo ocurren fallback_critical.
    Texto: qué había en la ventana cuando el sistema no encontró candidato normal.
    """
    if 'slot_search_completed' not in types:
        return

    fallback_rows = con.execute("""
        SELECT t, context, station_id, "window"
        FROM events
        WHERE type = 'slot_search_completed'
          AND (selected_priority = 'fallback_critical' OR selected_slot_idx IS NULL)
        ORDER BY t
    """).fetchall()

    if not fallback_rows:
        rep.print("\n[ Fallback en búsqueda ] Sin fallback_critical — sistema saludable.")
        return

    rep.print(f"\n[ Fallback en búsqueda ] {len(fallback_rows)} búsquedas en fallback_critical o sin resultado")

    skip_in_fallback = defaultdict(int)
    total_in_fallback = 0
    for _, _, _, window in fallback_rows:
        for entry in window:
            total_in_fallback += 1
            reason = entry.get('skipped_reason')
            if reason is not None:
                skip_in_fallback[reason] += 1

    rep.print(f"  Candidatos en ventanas de fallback: {total_in_fallback}")
    for reason, cnt in sorted(skip_in_fallback.items(), key=lambda x: -x[1]):
        rep.print(f"    {reason:<25} {cnt:>6}  ({cnt/total_in_fallback*100:.1f}%)")

    # Scatter: cuándo ocurren
    from matplotlib.lines import Line2D
    ctx_colors = {"demand": PALETTE["azul"], "reservation": PALETTE["violeta"]}
    ts = [r[0] / 60 for r in fallback_rows]
    colors = [ctx_colors.get(r[1], PALETTE["naranja"]) for r in fallback_rows]

    fig, ax = plt.subplots(figsize=FIG_BAR)
    ax.scatter(ts, [1] * len(ts), c=colors, s=50, alpha=0.7, zorder=3)
    handles = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=c, markersize=9, label=ctx)
        for ctx, c in ctx_colors.items()
    ]
    ax.legend(handles=handles)
    ax.set_xlabel("Tiempo (min)")
    ax.set_yticks([])
    ax.set_title("Búsquedas con fallback_critical en el tiempo", size=TITLE_SIZE)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("slot_labels_fallback_timeline", out_dir)
    plt.close()
