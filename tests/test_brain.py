#ahora quiero partir con los test, en primera instancia quiero que me digas si los test unitarios y los de integraion van en archivos diferentes, queiro que nos concentremos en los unitarios de brain, al igual que siempre ojala testear la mayoria de los casos y funciones importatnes (brain es uno de los archivos mas impportatnes de la simulacion asi que hay ser especialmente detallado)

#quiero evalues los casos bordes de cada funcion y luego revises el archivo de test_brian.py
#luego inveta los test junto con los que ya tenemos enfocate en los unitarios y luego miraremos los de integracion pero la idea es cubrir todo lo mejor posigle por que este archvo (brain, es uno de los mas importantes)

"""
Tests para Brain.

Responsabilidades documentadas:
    - TestBrainLoop:            el loop de 8 pasos corre en el orden correcto
    - TestCrossingHandler:      routing por etiqueta, contabilidad del counter
    - TestCounterAccounting:    Q15 — el counter se decrementa exactamente cuando corresponde
    - TestReservationMath:      cálculo de T_total, target_idx, aceleración ajustada
    - TestDemandSystem:         etiqueta de taza, on_vm_committed, commitment_broken
    - TestSaturationCheck:      ventana deslizante, burst_capacity, burst_window
    - TestBeltPlacement:        VM en slot reservado, fallback sin reserva

Convención de fixtures:
    make_brain_fixture(num_stations, train_length) → (brain, train, network, stations)
"""

# ─── COUNTER ACCOUNTING (Q15) ─────────────────────────────────────────────────

class TestCounterAccounting:
    """
    Q15: El counter de pending_demand solo se modifica en los momentos correctos.

    Regla del diseño:
        demand label     → on_vm_committed() al poner la etiqueta
        destination label → on_unplanned_vm_at_tree() cuando el VM entra al árbol
        reservation label → no toca el counter al ponerse;
                            on_unplanned_vm_at_tree() cuando el VM es eviccionado

    Tests unitarios: llaman _handle_crossings() directamente, sin correr el loop.
    Tests de integración: corren brain.update() varios frames y verifican el counter al final.
    """

    # ── UNITARIOS ────────────────────────────────────────────────────────────

    def test_reservation_does_not_change_counter(self):
        """
        Hacer una reserva (_make_reservation) no llama on_vm_committed().
        pending_demand debe ser idéntico antes y después de la reserva.
        Verifica que el fix de Q15 (eliminar línea 366) está en su lugar.
        """
        # TODO: implement

    def test_demand_label_decrements_counter_immediately(self):
        """
        _process_demand() llama on_vm_committed() al marcar el slot, ANTES del crossing.
        Verificar: pending_demand -= 1 en el mismo frame que se pone la etiqueta.
        """
        # TODO: implement

    def test_demand_vm_enters_tree_no_extra_decrement(self):
        """
        Un VM con demand == S que entra al árbol UP no llama on_unplanned_vm_at_tree().
        El counter ya fue decrementado cuando se puso la etiqueta.
        Verificar: counter == valor_inicial - 1 (exactamente uno, no dos).
        """
        # TODO: implement

    def test_demand_vm_rejected_restores_counter(self):
        """
        Si un VM con demand == S es rechazado en la junction, on_commitment_broken() restaura.
        Verificar: counter == valor_inicial (como si nunca se hubiera etiquetado).
        También verificar: demand_station_id del slot queda limpio.
        """
        # TODO: implement

    def test_destination_label_no_counter_change_before_crossing(self):
        """
        Poner destination_station_id en un slot no toca el counter.
        Verificar: counter idéntico antes y después de set_destination().
        """
        # TODO: implement

    def test_destination_vm_enters_tree_calls_on_unplanned(self):
        """
        VM con dest == S (sin demand label) que entra al árbol llama on_unplanned_vm_at_tree().
        Verificar: counter -= 1 al momento del crossing, no antes.
        """
        # TODO: implement

    def test_destination_vm_rejected_no_counter_change(self):
        """
        VM con dest == S rechazado en la junction no modifica el counter.
        No hay promesa que restaurar porque no se llamó on_vm_committed().
        Verificar: counter == valor_inicial después del crossing fallido.
        """
        # TODO: implement

    def test_eviction_calls_on_unplanned_exactly_once(self):
        """
        Cuando un slot reservado para S tiene un VM y cruza junction UP para S:
        - El VM es eviccionado (force_add_vm)
        - on_unplanned_vm_at_tree() se llama UNA sola vez
        Verificar: counter -= 1 (no -2, que sería el bug de Q15 sin el fix).
        """
        # TODO: implement

    def test_empty_reserved_slot_no_counter_change(self):
        """
        Un slot reservado para S que cruza junction UP mientras está vacío:
        - El crossing handler hace 'continue' (slot['vm'] is None)
        - No se llama ningún callback de counter
        Verificar: counter == valor_inicial.
        """
        # TODO: implement

    def test_vm_with_no_labels_passes_junction_no_change(self):
        """
        Un VM sin ninguna etiqueta que cruza junction UP para S pasa de largo.
        Ninguna rama del if/elif en _handle_crossings aplica.
        Verificar: counter == valor_inicial.
        """
        # TODO: implement

    def test_demand_eviction_broken_other_station(self):
        """
        Slot tiene demand == T (otra estación) y reserved == S.
        Al ser eviccionado para S:
        - T llama on_commitment_broken() (promesa de T rota)
        - S llama on_unplanned_vm_at_tree() (VM imprevisto para S)
        Verificar que ambas estaciones se actualizan correctamente.
        """
        # TODO: implement

    # ── INTEGRACIÓN ──────────────────────────────────────────────────────────

    def test_counter_end_to_end_demand_path(self):
        """
        INTEGRACIÓN: ciclo completo vía sistema de taza.
        1. Station S acumula demand = 1
        2. brain.update(): _process_demand etiqueta un slot → counter = 0
        3. belt avanza, VM cruza junction UP para S, entra al árbol
        4. brain.update(): crossing handler → counter no cambia (ya estaba en 0)
        Verificar: counter == 0 al final (no -1).
        El VM llegó, el contador está correcto.
        """
        # TODO: implement

    def test_counter_end_to_end_destination_path(self):
        """
        INTEGRACIÓN: ciclo completo vía sistema de destino.
        1. Station S tiene pending_demand = 1
        2. Un slot tiene destination == S (no demand)
        3. belt avanza, VM cruza junction UP para S, entra
        4. on_unplanned_vm_at_tree() decrementa al momento del crossing
        Verificar: counter == 0 exactamente al frame del crossing.
        No antes, no después.
        """
        # TODO: implement

    def test_counter_no_over_decrement_with_demand_and_destination_same_station(self):
        """
        INTEGRACIÓN: VM tiene demand == S Y destination == S simultáneamente.
        Caso: la demanda etiquetó el slot Y también tiene destino marcado.
        Al cruzar junction UP para S:
        - demand branch corre (prioridad sobre dest)
        - on_unplanned_vm_at_tree() NO se llama (demand != station_id es False)
        Verificar: counter decrementó exactamente UNA vez total (cuando se puso demand).
        """
        # TODO: implement

    def test_counter_self_regulates_after_excess_vms(self):
        """
        INTEGRACIÓN: más VMs de lo esperado llegan a S (ejemplo: evicción + demanda).
        - counter empieza en 1, demand etiqueta 1 VM
        - una evicción envía un segundo VM a S de manera imprevista
        - on_unplanned_vm_at_tree() lleva el counter a -1
        - brain deja de etiquetar (pending_demand <= 0 detiene el while)
        - el acumulador se recupera naturalmente con el tiempo
        Verificar que el while en _process_demand no corre cuando counter <= 0.
        """
        # TODO: implement


# ─── DESTINATION REDIRECT (Q2) ───────────────────────────────────────────────

class TestDestinationRedirect:
    """
    Q2: VM con destination_station_id que no puede entrar a su estación.

    Comportamiento correcto:
        - Si junction rechaza → redirigir a la siguiente estación (no vuelta completa)
        - Si sistema monoestación → warning, etiqueta sin cambio
        - Si VM entra en estación equivocada (por redirección previa) → warning de pasajeros
        - Redirección es circular: después de la última estación viene la primera

    Tests unitarios: llaman _handle_crossings() con junction mockeada que rechaza.
    Tests de integración: corren update() con múltiples frames y verifican el slot label.
    """

    # ── UNITARIOS ────────────────────────────────────────────────────────────

    def test_destination_label_changes_to_next_station_when_saturated(self):
        """
        VM tiene dest == S, junction rechaza (ok=False).
        Verificar: slot['destination_station_id'] cambia a next_station_id.
        NO queda en S (eso sería la vuelta completa).
        """
        # TODO: implement

    def test_no_redirect_in_single_station_system(self):
        """
        Sistema con solo una estación. VM tiene dest == S, junction rechaza.
        _next_station_id retorna None → etiqueta NO cambia, se emite WARNING.
        Verificar: slot['destination_station_id'] == S (sin cambio).
        """
        # TODO: implement

    def test_redirect_is_circular_last_station_goes_to_first(self):
        """
        Sistema con 3 estaciones: S1 (belt_x=10), S2 (belt_x=50), S3 (belt_x=90).
        _next_station_id(S3.id) debe retornar S1.id (distancia circular (10-90)%100 = 20).
        Verificar que el cálculo modular es correcto, no geográfico.
        """
        # TODO: implement

    def test_passenger_warning_when_vm_enters_wrong_station(self):
        """
        VM tiene dest == T (fue redirigido), llega a T, junction acepta (ok=True).
        Pero vm.destination_station_id (de los pasajeros reales) == S != T.
        Verificar: se emite WARNING con el station_id original de los pasajeros.
        """
        # TODO: implement

    def test_no_passenger_warning_when_station_matches(self):
        """
        VM entra normalmente a su estación correcta.
        vm.destination_station_id == station_id → NO se emite warning de pasajeros.
        """
        # TODO: implement

    def test_demand_counter_not_affected_by_redirect(self):
        """
        VM con dest == S (sin demand label) no pudo entrar. Se redirige a T.
        - Station S: counter sin cambio (el VM nunca entró, no había promesa)
        - Station T: on_unplanned_vm_at_tree() cuando finalmente entra
        Verificar que ningún contador cambia en el frame de la redirección.
        """
        # TODO: implement

    # ── INTEGRACIÓN ──────────────────────────────────────────────────────────

    def test_vm_exits_at_next_station_after_redirect(self):
        """
        INTEGRACIÓN: S3 saturada, S1 disponible.
        1. Frame 1: VM llega a S3 → junction rechaza → dest cambia a S1
        2. Belt avanza hasta S1
        3. Frame N: VM llega a S1 → junction acepta → VM sube
        Verificar: VM sale del belt en S1, no da vuelta completa.
        """
        # TODO: implement

    def test_cascade_redirect_finds_available_station(self):
        """
        INTEGRACIÓN: S3 saturada, S1 también saturada, S2 disponible.
        Frame 1: no entra S3 → dest = S1
        Frame 2: no entra S1 → dest = S2
        Frame 3: entra en S2 ✓
        Verificar que el cascade termina cuando encuentra capacidad.
        """
        # TODO: implement


# ─── LOOP ORDER (Q10) ────────────────────────────────────────────────────────

class TestBrainLoop:
    """
    Q10: El orden de los 8 pasos del loop no es intercambiable.
    Cada test viola un invariante específico para demostrar qué se rompe.

    Tests unitarios: usan spies/mocks para verificar el orden de llamadas.
    Tests de integración: ejecutan dos versiones del loop y comparan el resultado.
    """

    def test_tracks_advance_before_crossings_are_processed(self):
        """
        Si los tracks se avanzan DESPUÉS de procesar crossings, un VM transferido
        al UP tree en el paso 4 recibiría doble movimiento en el mismo frame
        (leftover_dt al entrar + dt completo del update).
        Verificar: VM que entra al árbol en el frame N solo se mueve a partir del frame N+1.
        Probar el negativo: si se invierten pasos 2 y 4, el VM avanza de más.
        """
        # TODO: implement

    def test_station_update_before_demand_labeling(self):
        """
        station.update() acumula demanda. Si _process_demand corre ANTES,
        Brain etiqueta slots basándose en la demanda del frame anterior.
        Verificar: etiqueta puesta en el frame N refleja la demanda del frame N,
        no la del frame N-1.
        Probar el negativo: invertir pasos 7 y 8b → etiqueta del frame equivocado.
        """
        # TODO: implement

    def test_reservations_before_demand_prevents_double_commit(self):
        """
        Si _process_demand corre ANTES que _process_reservations, la demanda puede
        marcar un slot que luego la reserva también elige (priority 1).
        Resultado: on_vm_committed() se llama dos veces para el mismo slot físico.
        Verificar con orden correcto: el slot reservado tiene reserved_station_id != None
        → _range_search_demand lo omite → no hay doble decremento.
        Probar el negativo: invertir 8a/8b → counter baja dos veces para un solo VM.
        """
        # TODO: implement

    def test_belt_placements_after_decisions(self):
        """
        _handle_belt_placements usa el slot reservado en _reserved_slots.
        Si corriera ANTES de _handle_decisions, los VMs que bajaron de DOWN trees
        no tendrían su slot asignado todavía.
        Verificar: VM aterriza en el slot reservado cuando belt_placements corre
        después de que la reserva ya fue guardada en _reserved_slots.
        """
        # TODO: implement


# ─── LABEL LIFECYCLE (Q10) ───────────────────────────────────────────────────

class TestCrossingHandler:
    """
    Q10: Las etiquetas nacen en pasos 8a/8b y mueren en el paso 4.
    Cada etiqueta tiene su momento exacto de nacimiento y muerte.

    Ciclo completo de cada etiqueta:
        demand_station_id:      nace en _process_demand → muere en remove_vm (si entra)
                                o en clear_demand_supply (si rechazado)
        destination_station_id: nace en _make_reservation o set_destination →
                                muere en remove_vm
        reserved_station_id:    nace en set_reservation → muere en place_vm (belt)
                                NO en remove_vm — persiste hasta que el VM aterriza

    Tests unitarios: verifican el estado del slot antes y después de cada acción.
    """

    def test_demand_label_cleared_after_vm_enters_tree(self):
        """
        VM con demand == S cruza junction, junction acepta.
        remove_vm() limpia demand_station_id.
        Verificar: slot['demand_station_id'] == None después del crossing exitoso.
        """
        # TODO: implement

    def test_demand_label_cleared_after_rejection(self):
        """
        VM con demand == S, junction rechaza.
        clear_demand_supply() limpia demand_station_id.
        Verificar: slot['demand_station_id'] == None después del crossing fallido.
        """
        # TODO: implement

    def test_destination_label_cleared_after_vm_enters_tree(self):
        """
        VM con dest == S cruza junction, junction acepta.
        remove_vm() limpia destination_station_id.
        Verificar: slot['destination_station_id'] == None después del crossing.
        """
        # TODO: implement

    def test_destination_label_survives_failed_crossing(self):
        """
        VM con dest == S, junction rechaza (sin redirección — caso monoestación o primera vez).
        La etiqueta cambia a next_station_id (Q2) o permanece si no hay alternativa.
        Verificar: después del crossing fallido el slot NO queda limpio — tiene nueva etiqueta.
        """
        # TODO: implement

    def test_reserved_label_NOT_cleared_by_remove_vm(self):
        """
        CRÍTICO: reserved_station_id NO se limpia cuando remove_vm saca el VM del belt.
        Solo se limpia en place_vm cuando el VM baja y aterriza.
        Verificar: después de una evicción, slot['reserved_station_id'] == None
        (place_vm lo limpia), pero SI se hace remove_vm SIN place_vm posterior,
        el slot queda correctamente limpio también (remove_vm limpia todos los labels).
        """
        # TODO: implement

    def test_slot_fully_clean_after_successful_crossing(self):
        """
        Después de cualquier crossing exitoso (enter tree), el slot queda
        completamente limpio: vm=None, todos los labels=None.
        Verificar los 5 campos del slot dict.
        """
        # TODO: implement


# ─── LABEL COMBINATIONS (Q10) ────────────────────────────────────────────────

class TestLabelCompatibility:
    """
    Q10: Qué pasa cuando un slot tiene múltiples etiquetas al mismo tiempo.
    Las ramas en _handle_crossings son elif — solo una corre. El orden importa.

    Combinaciones posibles y ganador:
        reserved=S + dest=S    → reserved gana (más fuerte)
        reserved=S + demand=S  → reserved gana, promesa de demanda se rompe
        reserved=S + dest=T    → reserved gana, WARNING pasajeros (evicción)
        reserved=S + demand=T  → reserved gana, on_commitment_broken para T
        dest=S + demand=S      → dest gana (elif); on_unplanned NO llamado (demand==S)
        dest=S + demand=T      → dest gana; on_unplanned SÍ llamado (demand!=S)
    """

    def test_reserved_wins_over_destination_same_station(self):
        """
        Slot: reserved=S, dest=S. Cruza junction UP para S.
        Solo corre la rama de reserva (if, no elif).
        Verificar: no se llama on_unplanned_vm_at_tree() (reserved branch no lo llama si demand==S... 
        wait — reserved branch llama on_unplanned si demand != station_id).
        Con demand=None: on_unplanned sí se llama. Verificar eso.
        """
        # TODO: implement

    def test_reserved_wins_over_demand_same_station(self):
        """
        Slot: reserved=S, demand=S. Cruza junction UP para S.
        Rama de reserva corre. demand==station_id → on_unplanned NO llamado.
        Verificar: counter no cambia en el crossing (ya contó cuando se puso demand).
        """
        # TODO: implement

    def test_reserved_breaks_demand_promise_other_station(self):
        """
        Slot: reserved=S, demand=T (T != S). Cruza junction UP para S.
        Rama de reserva: on_commitment_broken() para T, on_unplanned para S.
        Verificar: counter de T se restaura, counter de S baja.
        """
        # TODO: implement

    def test_destination_wins_over_demand_same_station(self):
        """
        Slot: dest=S, demand=S. Cruza junction UP para S.
        Rama de dest corre (elif dest == station_id). demand==S → on_unplanned NO llamado.
        Verificar: counter cambia exactamente una vez (cuando se puso demand).
        """
        # TODO: implement

    def test_destination_triggers_unplanned_when_demand_different(self):
        """
        Slot: dest=S, demand=T (T != S). Cruza junction UP para S.
        Rama de dest corre. demand != station_id → on_unplanned_vm_at_tree() para S.
        Verificar: counter de S baja en el momento del crossing.
        """
        # TODO: implement


# ─── SATURATION SCENARIOS (Q10) ──────────────────────────────────────────────

class TestSaturationCheck:
    """
    Q10: Saturación — qué pasa con etiquetas y VMs cuando la junction está al límite.

    Parámetros físicos: burst_capacity (N) = cuántos VMs puede absorber de corrido,
    burst_window (G) = cuántos slots debe cubrir la ventana de revisión.

    La ventana deslizante: para cada sub-ventana de G slots que contiene al candidato,
    si hay N o más slots ya marcados para S → saturaría.
    """

    def test_would_saturate_returns_false_below_capacity(self):
        """
        N=2, G=5. Solo 1 slot en el rango marcado para S.
        Candidato nuevo → 2 total, pero N=2 → debería ser exactamente en el límite.
        Verificar: returns False cuando count < N.
        """
        # TODO: implement

    def test_would_saturate_returns_true_at_capacity(self):
        """
        N=2, G=5. Ya hay 1 slot marcado en la ventana.
        Candidato nuevo → 2 total dentro de G → count >= N → saturaría.
        Verificar: returns True.
        """
        # TODO: implement

    def test_window_wraps_around_circular_belt(self):
        """
        El belt es circular. Candidato cerca del final del array, slots marcados
        cerca del principio. La ventana debe calcular correctamente con módulo.
        Verificar: would_saturate detecta saturación circular correctamente.
        """
        # TODO: implement

    def test_demand_skips_candidate_if_would_saturate(self):
        """
        _range_search_demand tiene un candidato válido que saturaría la junction.
        Verifica que se omite (continue) aunque sea el único candidato.
        Retorna None → demand no etiqueta → pending_demand sin cambio.
        """
        # TODO: implement

    def test_saturation_count_selects_minimum_in_fallback(self):
        """
        _range_search_reservation: todos los candidatos saturarían.
        _saturation_count elige el que tiene menor count.
        Verificar: best_slot es el que menos empeora la saturación.
        También verificar: se emite log CRÍTICO.
        """
        # TODO: implement

    def test_down_junction_never_saturates(self):
        """
        Las junctions DOWN tienen burst_window=0.
        _would_saturate retorna False inmediatamente (G==0 → return False).
        Verificar con junction DOWN real.
        """
        # TODO: implement


# ─── DEMAND SYSTEM (Q10) ─────────────────────────────────────────────────────

class TestDemandSystem:
    """
    Q10: El sistema de taza etiqueta slots según las prioridades correctas
    y respeta las restricciones de reserva, destino y saturación.
    """

    def test_demand_labels_slot_when_pending_demand_positive(self):
        """
        Station S tiene pending_demand = 1. Hay un slot con VM sin etiquetas.
        _process_demand debe marcar ese slot con demand_station_id = S.
        """
        # TODO: implement

    def test_demand_skips_empty_slots(self):
        """
        _range_search_demand requiere slot['vm'] is not None.
        Slot vacío cerca de junction_up → no se etiqueta.
        Solo slots CON VM son candidatos.
        """
        # TODO: implement

    def test_demand_skips_reserved_slots(self):
        """
        Slot tiene reserved_station_id != None → _range_search_demand lo omite.
        El VM será eviccionado antes de llegar a esta junction — etiquetarlo
        crearía una promesa de demanda que nunca se cumplirá.
        """
        # TODO: implement

    def test_demand_skips_slots_with_conflicting_destination(self):
        """
        Slot tiene destination_station_id = T (T != S).
        _range_search_demand omite este slot.
        El VM ya tiene compromiso con T — ponerle demand=S crearía conflicto.
        """
        # TODO: implement

    def test_demand_labels_multiple_slots_for_multiple_demand(self):
        """
        Station S tiene pending_demand = 3. Hay suficientes slots candidatos.
        _process_demand debe etiquetar 3 slots distintos.
        Verificar: 3 slots tienen demand_station_id = S al final del frame.
        """
        # TODO: implement

    def test_demand_stops_when_no_candidates(self):
        """
        Station S tiene pending_demand = 2. Solo hay 1 slot candidato.
        _process_demand etiqueta el 1 disponible, rompe el while en la segunda iteración.
        Verificar: pending_demand == 1 (no == 2, no == 0).
        NOTA: on_vm_committed se llama para el primero, pero el segundo intento
        retorna None → break (sin on_commitment_broken — no había promesa).
        """
        # TODO: implement


# ─── RESERVATION MATH (Q16) ──────────────────────────────────────────────────

class TestReservationMath:
    """
    Q16: Las etiquetas de reserva aseguran que el VM aterriza en el slot correcto.

    Dos garantías a verificar:
        1. El slot calculado es el que estará en junction_down cuando el VM llegue
        2. La aceleración ajustada hace que el VM llegue exactamente a tiempo

    Tests con números conocidos para verificar la matemática exacta.
    """

    def test_T_total_calculated_correctly(self):
        """
        Con valores conocidos: lane.length=20, progress=0.5, base_acceleration=2.5
        T_lane = (1 - 0.5) * 20 / BOARDING_LANE_SPEED = 5.0
        T_tree_std = (TRAIN_SPEED - BOARDING_LANE_SPEED) / 2.5 = 7.2
        T_total = 12.2
        Verificar que _make_reservation calcula exactamente estos valores.
        """
        # TODO: implement

    def test_target_slot_correct_with_known_belt_state(self):
        """
        Con T_total conocido, belt_speed conocido, tail_x conocido:
        future_tail_x = (tail_x + TRAIN_SPEED * T_total) % total_length
        target_idx = round((junction_down.belt_x - future_tail_x + total_length) % total_length / TRAIN_SPACING)
        Verificar que target_idx coincide con el cálculo manual para valores simples.
        """
        # TODO: implement

    def test_adjusted_acceleration_mrua_formula(self):
        """
        Si best_slot está 2 posiciones DESPUÉS del target (raw_offset=2):
        T_target = T_total + 2 * (TRAIN_SPACING / TRAIN_SPEED)
        T_tree_adj = T_target - T_lane
        a = 2 * (tree_length - BOARDING_LANE_SPEED * T_tree_adj) / T_tree_adj**2
        Verificar que vm.reserved_tree_acceleration queda con este valor exacto.
        """
        # TODO: implement

    def test_vm_lands_in_reserved_slot_end_to_end(self):
        """
        INTEGRACIÓN Q16: ciclo completo de reserva.
        1. VM hace boarding_commit en la lane
        2. _make_reservation calcula y reserva slot X
        3. VM baja por DOWN tree con aceleración ajustada
        4. VM llega al belt → place_vm en slot X
        Verificar: vm termina en slot X (el reservado), no en otro.
        Este es el test que da confianza en TODO el sistema de reserva.
        """
        # TODO: implement

    def test_reserved_slots_dict_cleaned_after_placement(self):
        """
        _handle_belt_placements hace .pop(vm.vehicle_id) de _reserved_slots.
        Después del placement, _reserved_slots no contiene el vm_id.
        Verificar: no hay leak de entradas viejas en _reserved_slots.
        """
        # TODO: implement


# ─── RANGE SEARCH PRIORITIES (Q11) ───────────────────────────────────────────

class TestRangeSearchPriorities:
    """
    Q11: Las prioridades de las búsquedas en rango pueden tener casos edge
    que no son óptimos o que se escapan.

    _range_search_reservation (para reservas):
        P1: slot ya etiquetado para S (dest=S o demand=S)
        P2: slot vacío sin reserva
        P3: VM sin destination label
        P4: VM con destination diferente (WARNING, evicción)
        Fallback: todos saturarían → menor saturación (CRÍTICO)

    _range_search_demand (para taza):
        P1: slot ya etiquetado para S
        P2: slot con VM sin etiquetas conflictivas
    """

    def test_reservation_prefers_already_labeled_slot(self):
        """
        En el rango hay: un slot vacío (P2) y un slot con dest=S (P1).
        _range_search_reservation debe elegir el de dest=S.
        El VM ya iba a subir ahí — la reserva no introduce conflictos nuevos.
        """
        # TODO: implement

    def test_reservation_prefers_empty_over_vm_without_destination(self):
        """
        En el rango hay: un slot con VM sin dest (P3) y un slot vacío (P2).
        Debe elegir el vacío (P2). No hay VM que evicionar.
        """
        # TODO: implement

    def test_reservation_skips_slot_reserved_for_other_station(self):
        """
        Un slot tiene reserved_station_id = T (T != S).
        _range_search_reservation lo ignora completamente (no lo evalúa).
        Sobreescribir esa reserva rompería la garantía anticolición de T.
        """
        # TODO: implement

    def test_reservation_chooses_eviction_with_warning(self):
        """
        Solo hay slots con VM con destination diferente (P4 es la mejor opción).
        _range_search_reservation elige uno y emite WARNING.
        Verificar: se elige el slot, se emite el warning correcto.
        """
        # TODO: implement

    def test_demand_prefers_slot_already_labeled_for_station(self):
        """
        Hay un slot con dest=S (P1) y otro con VM sin etiquetas (P2).
        _range_search_demand elige el de dest=S.
        El VM ya iba a subir — sumar demand no crea conflicto.
        """
        # TODO: implement

    def test_demand_does_not_choose_slot_labeled_for_other_station(self):
        """
        Slot tiene dest=T (T != S). _range_search_demand lo omite.
        Verificar que ese slot no aparece como candidato elegido.
        """
        # TODO: implement

    def test_range_wraps_around_circular_belt(self):
        """
        target_idx está cerca de 0. El rango ±SLOT_SEARCH_RANGE//2 necesita
        acceder a índices negativos → % max_slots los envuelve correctamente.
        Verificar que los candidatos no fallan con IndexError y el rango es correcto.
        """
        # TODO: implement


# ─── BELT PLACEMENT (Q16) ────────────────────────────────────────────────────

class TestBeltPlacement:
    """
    Q16: El VM aterriza en el slot correcto y _reserved_slots queda limpio.
    """

    def test_vm_placed_in_reserved_slot(self):
        """
        _reserved_slots tiene vm_id → slot_idx.
        _handle_belt_placements hace place_vm en ese slot exacto.
        Verificar: vm termina en slot slot_idx, no en otro.
        """
        # TODO: implement

    def test_fallback_placement_when_no_reservation(self):
        """
        VM llegó al belt sin entrada en _reserved_slots (bug upstream).
        Fallback: find_neartest_slot_to_belt_x cerca de junction_down.
        Verificar: VM aterriza en algún slot (no crash), se emite WARNING.
        """
        # TODO: implement

    def test_reserved_slots_entry_removed_after_placement(self):
        """
        Después de place_vm, _reserved_slots.pop() remueve la entrada.
        Verificar: _reserved_slots vacío después del placement.
        """
        # TODO: implement

