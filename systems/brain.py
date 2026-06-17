"""
Brain - Coordinador central de NSim

Brain es el único componente que conoce todos los subsistemas simultáneamente.
Su responsabilidad exclusiva es coordinar cuándo y cómo los VMs se mueven entre 
los distintos tracks. NO implementa física ni genera pasajeros - delega eso a los 
subsistemas y solo toma decisiones de routing.

Sistemas que Brain orquesta:
    ContinuosTrain  - carril circular (belt). Brain lo avanza y lee sus crossings.
    Network         - grafo de tracks superiores. Brain lo avanza y recibe completions.
    Station         - cada estación. Brain la actualiza y lee su demanda pendiente.

Los tres sistemas de etiquetas de slot que Brain gestiona:
    reserved_station_id         int|None        anticolición: el slot DEBE liberar su VM en esa estación
    destination_station_id      int|None        routing: el VM tiene pasajeros para esta estación
    demand_station_id           int|None        taza: la estación necesita un VM y reclama este slot

Invariante de dependencias:
    Brain importa de tracks/ y systems/ pero nada importa de Brain excepto simulacion/.
    Romper esta dirección crea importaciones circulares.
    
Responsabilidades:
    - Ejecutar el loop de la simulación en orden fijo cada frame
    - Gestionar las 3 etiquetas de slots (reserva, destino, demanda)
    - Prevenir colisiones mediante reserva anticipada de slots
    - Rutear VMs entre belt, boarding lanes y acceleration trees

Lo que NO hace:
    - No conoce la física de los tracks (AccelerationTree, BoardingLane lo hacen)
    - No gestiona generación de pasajeros (Station lo hace)
    - No modifica la topología de la red (Network lo hace)
"""
import logging
logger = logging.getLogger(__name__)

from tracks.boarding_lane import BoardingLane
from tracks.acceleration_tree import AccelerationTree
from systems.continuous_train import ContinuousTrain
from systems.network import Network
from config.constants import TRAIN_SPEED, BOARDING_LANE_SPEED, TRAIN_SPACING, SLOT_SEARCH_RANGE

class Brain:
    """
    Coordinador central: ejecuta el loop frame a frame y gestiona los 3 sistemas de etiquetas.

    Estado interno:
    _train              ContinuousTrain         el carril inferior circular
    _network            Network                 el grafo de tracks superiores
    _stations           dict[int, Station]      estaciones por station_id
    _reserved_slots     dict[int,int]           vm_id -> slot_idx
                                                Registra qué slot específico fue prometido a cada VM
                                                mientras el VM aún está en el DOWN tree. Se consume
                                                en _handle_belt_placements cuando el VM llega al belt.
    """

    def __init__(
        self,
        train: ContinuousTrain,
        network: Network,
        stations: dict,
    ):
        self._train =       train
        self._network =     network
        self._stations =    stations

        # (Promesas activas hasta que el VM aterriza en el belt)
        self._reserved_slots: dict[int, int] =  {} 

    # ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────

    def update(self, dt: float, current_time: float) -> None:
        """
        Ejecuta un frame completo de simulación. El orden de los 8 pasos es invariante
        y cualquier reordenamiento produce bugs sutiles.

        Por qué este orden:

        Pasos 1-3 (avance físico) van  ANTES que los pasos de routing (4-6):
            Si Brain transfiriera un VM a un árbol UP en el paso 4 y los tracks se
            avanzaran DESPUES, ese VM recibiría doble movimiento en el mismo frame
            (primero el leftover_dt al entrar al árbol y luego el dt completo del update).
            Avanzar todos los tracks PRIMERO  garantiza que los VMs transferidos este
            frame solo se muevan a partir del frame siguiente
        
        Paso 7 (station.update) va ANTES  que los pasos de etiquetas (8a, 8b):
            station.update acumula demanda. Brain necesita leer pending_demand ya
            actualizado al asignar etiquetas de taza. Si estuviera después, Brain
            estaría reaccionando a la demanda del frame anterior.
        
        
        Paso 8a (reservas) va ANTES que 8b (demanda):
            _range_search_demand filtra con 'if slot["reserved_station_id"] is not None: continue'.
            Si las reservas corren primero, la demanda ve los slots ya comprometidos y los
            omite automáticamente. Si la demanda corriera primero, podría marcar con
            demand_station_id = S el mismo slot que luego la reserva elige (priority 1).
            Esto causaría que on_vm_committed() se llame DOS veces para el mismo slot
            fisico: una al poner la etiqueta de demanda y otra al hacer la reserva.
            El acumulador de demanda de S quedaría demasiado bajo (under-demand counting).

        """

        # 1. Avanzar el belt: tail_x avanza, se detectan qué slots cruzaron juntions UP
        crossings = self._train.advance(dt)

        # 2. avanzar todos los tracks superiores (árboles y lanes): cada VM se mueve dt segundos.
        #   Los VMs que terminaron su track quedan en 'completitions'  para procesar despúes.
        completions = self._network.update_all_tracks(dt)

        # 3. Separar completions en dos categorías
        #   - decisions: adyacencia len>1, Brain elige el siguiente track
        #   - belt_placementes: track terminal (DOWN tree sin siguiente), VM va al belt
        decisions, belt_placements = self._network.process_transitions(completions)

        # 4. Para cada slot que cruzo una juntion UP este frame: decidir si el VM sube,
        #   y si el obligatorio (reserva) o condicional (destino, demanda).
        self._handle_crossings(crossings)

        # 5. Para cada VM en bifurcaciones (boarding lane con múltiples DOWN trees posibles):
        #   elegir el track menos cargado.
        self._handle_decisions(decisions)

        # 6. Para VMs que bajaron de un DOWN tree: colocarlos en su slot reservado en el belt.
        self._handle_belt_placements(belt_placements)

        # 7. Actualizar cada estación: genera  nuevos pasajeros, acumula demanda de VMs.
        for station in self._stations.values():
            station.update(dt, current_time)

        # 8a. Sistema de reserva: para VMs que hicieron barding_commit este frame, calcular
        #   y reservar el slot donde aterrizáran desde el DOWN tree.
        self._process_reservations()

        # 8b. Sistema de taza: marcar slots con demand_station_id para estaciones con demanda 
        self._process_demand()

    # ─── CROSSING HANDLER ────────────────────────────────────────────────────
    def _handle_crossings(self, crossings: list) -> None:
        """
        Procesa los slots que cruzaron una junction UP este frame.

        Cada crossing es (slot_idx, station_id, leftover_dt). Para cada uno, Brain
        lee las 3 etiquetas del slot y aplica el comportamiento correspondiente:

            Reserved_station_id == S -> FORZADO (anticolición)
                El slot fue reclamado para liberar espacio a un VM entrante. El VM 
                actual DEBE salir. Brain intenta add_vm primero; si la junction rechaza
                (árboles saturados), llama force_add_vm en el MISMO frame. No hay 
                siguiente oportunidad: la garantía anticolision no puede esperar.
                Si el VM tenía pasajeros para otra estación, se bajan aquí (log WARNING).
                Si había una promesa de demanda para otra estacion, se rompe.
      
            destination_station_id == S -> CONDICIONAL con redirección
                El VM tiene pasajeros comprometidos para S. Se intenta add_vm; si la
                junction rechaza (árboles saturados), el VM se redirige a la siguiente
                estación en dirección de avance del belt (no da la vuelta completa).
                Si el sistema tiene solo una estación, la vuelta completa es inevitable.
                Comportamiento circular: si S es la última estación del circuito, la
                "siguiente" es la primera (belt_x más bajo) — _next_station_id usa
                distancia modular para calcularlo correctamente.
                Cuando el VM entra al árbol en una estación, si sus pasajeros iban a
                otra (efecto de redireciones previas), se registra un WARNING.
            
            demand_station_id == S -> CONDICIONAL con penalidad
                La estacion S marcó este slot porque necesita VMs (taza). Se intenta
                add_vm; si rechaza: on_commitment_broken (restaura el contador de demanda)
                y clear_demand_supply (libera el slot para una nueva busqueda el frame
                siguiente). No se reintenta automáticamente.
            
        Las ramas son elif excluentes en orden de prioridad. Si un slot tiene
        reserved == S y tambien dest = S, solo corre la rama de reserva (más fuerte).

        INVARIANTE TOPOLÓGICO:
            Este código asume que set_reservation() nunca se llama con una station_id cuya
            junction_UP queda en el recorrido del belt DESPUÉS de la junction_UP de una
            estación que el slot tenga en demand_station_id. En otras palabras:
            la región [junction_DOWN(S) → junction_UP(S)] en el belt no debe contener
            las junctions de ninguna otra estación. Si esto se viola, el
            on_commitment_broken() puede romper una promesa que el slot todavía podría haber
            cumplido. Solución futura: al detectar crossing de S con reserved=S,
            verificar si demand_station_id ya fue irreversiblemente superado comparando
            posiciones belt_x de junction_UP del slot actual vs junction_UP del demand.
        """
        for slot_idx, station_id, leftover_dt in crossings:
            slot = self._train.slots[slot_idx]
            if slot['vm'] is None:
                continue
            
            reserved = slot['reserved_station_id']
            dest = slot['destination_station_id']
            demand = slot['demand_station_id']

            junction = self._network.get_junction_up(station_id)
            if junction is None:
                continue
            station = self._stations.get(station_id)
            if station is None:
                continue

            if reserved == station_id:
                # Romper la promesa de T es correcto SOLO si UP(S) llega antes que UP(T) en el belt.
                # Ver INVARIANTE TOPOLÓGICO en el docstring. Con el layout actual (estaciones contiguas)
                # esta condición siempre se cumple.
                if demand is not None and demand != station_id:
                    demand_station = self._stations.get(demand)
                    if demand_station:
                        demand_station.on_commitment_broken()
                vm = self._train.remove_vm(slot_idx)
                if dest != station_id and vm.has_destination:
                    logger.warning(f"VM {vm.vehicle_id} eviccionado en estación {station_id}, destino era {dest}")
                if demand != station_id:
                    station.on_unplanned_vm_at_tree()
                ok = junction.add_vm(vm,leftover_dt)
                if not ok:
                    junction.force_add_vm(vm,leftover_dt)            

            elif dest == station_id:
                ok = junction.add_vm(slot['vm'], leftover_dt)
                if ok:
                    vm = slot['vm']
                    if vm.has_destination and vm.destination_station_id != station_id:
                        logger.warning(f"Pasajeros de VM {vm.vehicle_id} iban a estación "
                            f"{vm.destination_station_id}, bajaron en estación {station_id}")
                    if demand != station_id:
                        station.on_unplanned_vm_at_tree()
                    self._train.remove_vm(slot_idx)
                # else:
                
                else:
                    if demand == station_id:
                        station.on_commitment_broken()
                        self._train.clear_demand_supply(slot_idx)
                    next_id = self._next_station_id(station_id)
                    if next_id is not None:
                        self._train.set_destination(slot_idx, next_id)
                        logger.warning(f"VM {slot['vm'].vehicle_id} no pudo entrar a estación "
                            f"{station_id} (árboles saturados). Redirigido a estación {next_id}")
                    else:
                        logger.warning(f"VM {slot['vm'].vehicle_id} no pudo entrar a estación "
                            f"{station_id}: sin estación alternativa (sistema monoestación).")
                        
            elif demand == station_id:
                ok = junction.add_vm(slot['vm'], leftover_dt)
                if ok:
                    self._train.remove_vm(slot_idx)
                else:
                    station.on_commitment_broken()
                    self._train.clear_demand_supply(slot_idx)
                
    # ─── DECISIONS ───────────────────────────────────────────────────────────

    def _handle_decisions(self, decisions: list) -> None:
        """
        Enruta VMs en bifurcaciones (adyacencia con len > 1)

        Con la topología actual (1 DOWN tree por boarding lane), decisions siempre
        llega vacía. El código existe para soportar la arquitectura de dos trenes
        paralelos, donde boarding lane conecta a múltiples DOWN trees. En ese
        caso, Brain elige el árbol con menos VMs para distribuir carga.

        (El metodo que se ocupe para elegir el mejor arbol puede cambiar)
        (ahora no hay problema pero lo mas correcto es que el vm se dirija 
        donde fue proyectado)
        """
        for vm, next_ids, leftover_dt in decisions:
            best_id = min(next_ids, key=lambda tid: self._network.get_track(tid).vehicle_count)
            self._network.get_track(best_id).add_vehicle(vm, leftover_dt=leftover_dt)

    # ─── BELT PLACEMENTS ─────────────────────────────────────────────────────
                    
    def _handle_belt_placements(self,belt_placements: list) -> None:
        """
        Coloca en el belt los VMs que terminaron de bajar por un DOWN tree.

        El flujo normal es: _make_reservation guardó vm_id -> slot_idx en _reserved_slots.
        Ahora el VM llegó, buscamos su slot y llamamos place_vm.
        place_vm limpia reserved_station_id y reserved_vm_id del slot.

        El fallback (sin reserva en _reserved_slots) indica un bug en el sistema de
        reserva: el VM bajó sin que Brain lo anticipara. Se usa find_neartest_slot_to belt_x
        como fallback de emergencia y se registra el error para diagnóstico.
        """
        for vm, leftover_dt, station_id in belt_placements:
            slot_idx = self._reserved_slots.pop(vm.vehicle_id, None)
            if slot_idx is None:
                logger.warning(f"VM {vm.vehicle_id} bajó sin reserva desde estación {station_id}")
                junction_down = self._network.get_junction_down(station_id)
                if junction_down is None:
                    logger.error(f"Sin junction DOWN para estación {station_id}")
                    continue
                slot_idx, _ = self._train.find_neartest_slot_to_belt_x(junction_down.belt_x)
            self._train.place_vm(vm, slot_idx)
    
    # ─── RESERVAS ────────────────────────────────────────────────────────────

    def _process_reservations(self) -> None:
        """
        Detecta VMs que hicieron boarding_commit este frame y les asigna un slot.
        Corre en dos pases por frame sobre cada BoardingLane:

        Pase 1 — boarding_committed recién activado:
            Condición: boarding_committed == True AND vm_id NO en _reserved_slots.
            Acción: _make_reservation — calcula slot, ajusta aceleración, registra promesa.
            Garantía: cada VM recibe reserva una sola vez aunque siga varios frames en la lane.

        Pase 2 — destino adquirido después del commit:
            Condición: vm_id YA en _reserved_slots AND vm.has_destination == True
                       AND el slot reservado todavía no tiene destination_station_id.
            Acción: train.set_destination — escribe la etiqueta que el Pase 1 no pudo.
            Cubre el caso donde el pasajero aborda DESPUÉS del commit. El subsistema de
            boarding no necesita llamar set_destination directamente — este pase lo detecta.
        """
        for track_id, track in self._network.tracks.items():
            if not isinstance(track, BoardingLane):
                continue
            down_tree = self._get_down_tree_for_lane(track_id)
            if down_tree is None or down_tree.station_id is None:
                continue
            station_id = down_tree.station_id
            for vm_id, data in list(track.vehicles.items()):
                vm = data['vehicle']
                if data['boarding_committed'] and vm.vehicle_id not in self._reserved_slots:
                    # Pase 1: reserva nueva para VM recién comprometido
                    self._make_reservation(vm, track, down_tree, station_id)
                elif vm.vehicle_id in self._reserved_slots and vm.has_destination:
                    # Pase 2: el VM ya tiene reserva pero adquirió destino después del commit
                    slot_idx = self._reserved_slots[vm.vehicle_id]
                    if self._train.slots[slot_idx]['destination_station_id'] is None:
                        self._train.set_destination(slot_idx, vm.destination_station_id)

    def _get_down_tree_for_lane(self, lane_id: int):
        """
        Busca el AccelerationTree DOWN conectado a una BoardingLane. en la adyacencia.

        La topología garantiza que toda BoardingLane conecta a al menos un DOWN tree.
        Si hay múltiples (arquitectura fuera de dos trenes), retorna el primero.
        Retorna None si la lane es terminal (error de configuración de la red).

        Para futura implementacion (multiples AccelerationTree DOWN), se debe considerar
        que el vm baje por el acceleration tree que que lo lleve al slot que previamente
        reservo.
        """
        for next_id in self._network.adjacency.get(lane_id, []):
            track = self._network.get_track(next_id)
            if isinstance(track,AccelerationTree):
                return track
        return None
    
    def _make_reservation(self, vm, lane: BoardingLane, down_tree: AccelerationTree, station_id: int) -> None:
        """
        Asigna un slot específico al VM y calibra su aceleración para llegar exactamente ahí.

        El problema que resuelve:
        El VM está bajando por un DOWN tree a BOARDING_LANE_SPEED. Acelerará  hasta
        TRAIN_SPEED y aterrizará en el belt cerca de junction_down de la estación.
        Queremos saber QUÉ SLOT estará exactamente en la junction_down cuando el VM llegue,
        reservarlo, y ajustar la aceleración del VM para que el timing sea exacto.

        Matemáticas en 4 pasos:

        Paso 1 - Tiempo total con aceleración estándar (T_total):
            T_lane  = distancia restante en lane / BOARDING_LANE_SPEED
            T_tree_std = (TRAIN_SPEED - BOARDING_LANE_SPEED) / base_acceleration
            T_total = T_lane + T_tree_std
            (Asume que el VM baja con base_acceleration; se ajusta después si el slot
            elegido difiere del target ideal.)

        Paso 2 - Slot objetivo (target_idx):
            El belt avanza TRAIN_SPEED metros/ segundo. En T_total segundos, tail_x
            habrá avanzado TRAIN_SPEED * T_total metros. El slot que estara en
            junction_down.belt_x en ese momento es target_idx.

        Paso 3 - Búsqueda en rango:
            El target_idx ideal puede estar ocupando o saturar la junction. Brain busca
            el mejor slot en ±(SLOT_SEARCH_RANGE//2) alrededor del target,
            usando una función de prioridad (ver _range_search_reservation).

        Paso 4 - Ajuste de aceleración (MRUA):
            Si el slot elegido (best_slot) difiere del target en raw_offset posiciones,
            el VM necesita llegar raw_offset * (TRAIN_SPACING / TRAIN_SPEED) segundos
            mas tarde o más temprano. La nueva aceleración se calcula de MRUA:
                d = v0*t + 0.5*a*t²  →  a = 2*(d - v0*t) / t²
            donde d = tree_length, v0 = BOARDING_LANE_SPEED, t = T_tree_adj.
            Esta aceleración se guarda en vm.reserved_tree_acceleration.
            AccelerationTree._insert_vehicle la consume automáticamente al insertar el VM.

        Precondición sobre vm.has_destination:
            Si el VM ya tiene pasajeros en el momento del commit, el destino se escribe
            aquí directamente. Si no, _process_reservations lo escribe en el Pase 2 cuando
            el pasajero aborde. No es necesario que el subsistema de boarding llame
            set_destination por separado.
        """
        progress = lane.get_progress(vm)
        remaining = (1.0 - progress) * lane.length
        T_lane = remaining / BOARDING_LANE_SPEED
        T_tree_std = (TRAIN_SPEED - BOARDING_LANE_SPEED) / down_tree.base_acceleration
        T_total = T_lane + T_tree_std

        junction_down = self._network.get_junction_down(station_id)
        if junction_down is None:
            logger.error(f"Sin junction DOWN para estación {station_id}")
            return
        
        future_tail_x = (self._train.tail_x + TRAIN_SPEED * T_total) % self._train.total_length
        relative = (junction_down.belt_x - future_tail_x + self._train.total_length) % self._train.total_length
        target_idx = round(relative / TRAIN_SPACING) % self._train.max_slots

        junction_up = self._network.get_junction_up(station_id)
        best_slot = self._range_search_reservation(target_idx, station_id, junction_up)
        if best_slot is None:
            logger.critical(f"Sin slot disponible para reserva de VM {vm.vehicle_id}")
            return
        
        half = self._train.max_slots // 2
        raw_offset = (best_slot - target_idx + half) % self._train.max_slots - half
        T_target = T_total + raw_offset * (TRAIN_SPACING / TRAIN_SPEED)
        T_tree_adj = max(T_target -T_lane, 0.01)
        a = 2.0 * (down_tree.length - BOARDING_LANE_SPEED * T_tree_adj) / T_tree_adj ** 2

        vm.reserved_tree_acceleration = a
        self._train.set_reservation(best_slot, vm_id=vm.vehicle_id, station_id=station_id)
        self._reserved_slots[vm.vehicle_id] = best_slot

        if vm.has_destination:
            self._train.set_destination(best_slot, vm.destination_station_id)
        

        # ─── DEMANDA ─────────────────────────────────────────────────────────────

    def _process_demand(self) -> None:
        """
        Marca slots con demand_station_id para estaciones con demanda pendiente.

        station.pending_demand es la parte entera del acumulador de demanda. Brain
        lo lee cada frame y, mientras sea positivo, busca slots candidatos hacia
        atrás desde junction_up para marcarlos.

        Contabilidad:
            on_vm_committed() se llama inmediatamente al marcar el slot (decrementa 
            el acumulador). Si la junction luego rechaza al VM en _handle_crossings,
            on_commitment_broken() lo restaura. Si no se encuentra ningún slot este
            frame, el contador no cambia y Brain reintenta el frame siguiente.
        """
        for station_id, stations in self._stations.items():
            junction_up = self._network.get_junction_up(station_id)
            if junction_up is None:
                continue
            while stations.pending_demand > 0:
                best_slot = self._range_search_demand(station_id, junction_up)
                if best_slot is None:
                    break
                self._train.set_demand_supply(best_slot, station_id)
                stations.on_vm_committed()

    def _next_station_id(self, current_station_id: int) -> int | None:
        """
        Retorna el ID de la siguiente estación en la dirección de avance del belt.

        Usa la posición belt_x de junction_up de cada estación. Calcula la distancia
        circular hacia adelante con módulo (x - current_x) % total_length. El resultado
        es la estación más cercana EN LA DIRECCIÓN DE AVANCE, no la geográficamente
        más cercana.

        Comportamiento circular: si S3 está en belt_x=90 y S1 en belt_x=10,
        con total_length=100, la distancia de S3 a S1 es (10 - 90) % 100 = 20.
        Correcto: S1 viene después de S3 dando la vuelta.

        Retorna None solo si el sistema tiene una única estación.
        """
        current_x = self._network.get_junction_up(current_station_id).belt_x
        total = self._train.total_length
        best_id = None
        best_dist = float('inf')
        for sid in self._stations:
            if sid == current_station_id:
                continue
            x = self._network.get_junction_up(sid).belt_x
            dist = (x - current_x) % total
            if dist < best_dist:
                best_dist = dist
                best_id = sid
        return best_id

    # ─── BÚSQUEDA EN RANGO ───────────────────────────────────────────────────

    def _range_search_reservation(self, target_idx: int, station_id: int, junction_up) -> int | None:
        """
        Busca el mejor slot para una reserva en ±(SLOT_SEARCH_RANGE//2) del target.

        Prioridades (de mejor a peor):
            1.  Slot que ya tiene etiqueta de esta estación (dest o demand == S).
                El VM ya iba a subir aquí de todos modos; la reserva no añade conflictos.
            2.  Slot vacío sin reserva activa.
                El caso ideal: no hay VM que evicionar.
            3.  VM sin destination_station_id
                Hay un VM pero no tiene destino comprometido; la eviccion es limpia.
            4.  VM con destination diferente.
                La eviccion forzará al VM a subir en la estación equivocada.
                Sus pasajeros se bajaran ahí (log WARNING en _handle_crossings).
            Fallback: si todos los candidatos saturarían la junction, se elige el que
            produce la menor saturación y se registra log CRITICO.

        Slot ya reservados para una estación DIFERENTE se omiten completamente:
            Sobreescribir una reserva rompería la garantía anticolición de esa reserva.
        """
        half = SLOT_SEARCH_RANGE // 2
        max_slots = self._train.max_slots
        candidates = [(target_idx+ offset) % max_slots for offset in range(-half,half +1)]

        best_priority = 6
        best_slot = None

        for candidate in candidates:
            slot = self._train.slots[candidate]
            res_lbl = slot['reserved_station_id']
            if res_lbl is not None and res_lbl != station_id:
                continue
            if self._would_saturate(junction_up, candidate, station_id):
                continue

            dest_lbl = slot['destination_station_id']
            dmd_lbl = slot['demand_station_id']

            if dest_lbl == station_id or dmd_lbl == station_id:
                priority = 1
            elif slot['vm'] is None and res_lbl is None:
                priority = 2
            elif slot['vm'] is not None and dest_lbl is None:
                priority = 3
            else:
                priority = 4
            
            if priority < best_priority:
                best_priority = priority
                best_slot = candidate
        if best_slot is None:
            best_sat = float('inf')
            for candidate in candidates:
                sat = self._saturation_count(junction_up, candidate, station_id)
                if sat < best_sat:
                    best_sat = sat
                    best_slot = candidate
            if best_slot is not None:
                logger.critical(f"Reserva en slot saturado (estación {station_id}, slot {best_slot})")

        if best_priority == 4 and best_slot is not None:
            dest = self._train.slots[best_slot]['destination_station_id']
            logger.warning(f"Reserva en slot con destino diferente (slot {best_slot}, dest={dest})")
        
        return best_slot

    def _range_search_demand(self, station_id: int, junction_up) -> int | None:
        """
        Busca un slot con VM para marcar con demanda, mirando hasta SLOT_SEARCH_RANGE
        posiciones HACIA ATRÁS desde junction_up (slots que aún no han cruzado).

        Solo considera slots CON VM: la demanda necesita un VM que suba, no un slot vacío
        Omite slots con reserved_station_id activo: ese VM sera eviccionado antes
        de llegar a esta junction, rompiendo la promesa de demanda.
        Omite slots con destination de otra estación: el VM ya tiene compromiso diferente.

        Prioridades
            1.  Slot que ya tiene etiqueta de esta estación (dest o demand == S).
            2.  Slot con VM sin etiquetas conflictivas
        """
        start_idx = self._train.find_neartest_slot_to_belt_x(junction_up.belt_x)[0]
        max_slots = self._train.max_slots
        best_priority = 3
        best_slot = None

        for offset in range(SLOT_SEARCH_RANGE+1):
            candidate = (start_idx - offset) % max_slots
            slot = self._train.slots[candidate]
            
            if slot['vm'] is None:
                continue
            if slot['reserved_station_id'] is not None:
                continue
            dest_lbl = slot['destination_station_id']
            if dest_lbl is not None and dest_lbl != station_id:
                continue
            if self._would_saturate(junction_up, candidate, station_id):
                continue

            dmd_lbl = slot['demand_station_id']
            if dest_lbl == station_id or dmd_lbl == station_id:
                priority = 1
            else:
                priority = 2

            if priority < best_priority:
                best_priority = priority
                best_slot = candidate

        return best_slot
    
    # ─── SATURACIÓN ──────────────────────────────────────────────────────────

    def _would_saturate(self, junction, candidate: int, station_id: int) -> bool:
        """
        Verifica si agregar el slot candidato como destino de S saturaría la junction.

        El 'Problema Destino Terminal': si muchos slots_saturation_count consecutivos van a la misma
        estacion, la junction UP no puede absorberlos y los VM se acumulan.

        Parámetros de la junction:
            burst_capacity (N): cuántos VMs puede absorber de corrido (= número de árboles UP)
            burst_window (G):   cuántos slots deben separar dos grupos consecutivos
                                (= min_slot_gap del árbol UP, derivado de física MRUA)

        Algoritmo de ventana deslizante O(G²)
            Para cada sub-ventana de tamaño G que contiene al candidato, cuenta cuántos
            slots ya tienen etiqueta de S (destination o demand). Si alguna ventana
            alcanza N (incluyendo el candidato), la junction saturaría.

        Para junctions DOWN: burst_window == 0 -> siempre retorna False (DOWN no satura).
        """
        N = junction.burst_capacity
        G = junction.burst_window
        if G == 0 or N == 0:
            return False
        
        max_slots = self._train.max_slots
        slots = self._train.slots
        
        for start_offset in range(-(G -1), 1):
            count = 1   # el candidato siempre cuenta
            for i in range(G):
                idx = (candidate + start_offset + i) % max_slots
                if idx != candidate and self._is_slot_marked_for(idx, station_id):
                    count += 1
            if count >= N:
                return True
        return False

    def _saturation_count(self, junction, candidate: int, station_id: int)-> int:
        """
        Cuenta cuántos slots ya marcados para S caerían en la misma ventana que candidate.

        Usando como criterio de desempate en el fallback de _range_search_reservation.
        cuando todos los candidatos saturarían la junction. Se elige el candidato con
        el menor conteo (el que menos empeora la saturación).
        """
        N = junction.burst_capacity
        G = junction.burst_window
        if G == 0 or N == 0:
            return 0
        
        max_slots = self._train.max_slots
        slots = self._train.slots
        
        max_count = 0
        for start_offset in range(-(G -1), 1):
            count = 1
            for i  in range(G):
                idx = (candidate + start_offset + i) % max_slots
                if idx != candidate and self._is_slot_marked_for(idx, station_id):
                    count += 1
            max_count = max(max_count, count)
        return max_count
    
    def _is_slot_marked_for(self, idx: int, station_id: int) -> bool:
        """Retorna si el slot s esta marcado con demanda o con destino"""
        s = self._train.slots[idx % self._train.max_slots]
        return s['destination_station_id'] == station_id or s['demand_station_id'] == station_id












## Preguntas luego de entender ##


# Pregunta 21:
# me quedeo muy claro como es que funciona el codigo completo de brain menos las funciones de saturacion, no las logro entender todavia y creo que esta es una de las genialidades mas grandes 
# de la sim asi que es presiso que lo entienda bien de ser nesestario dieme algun video o algo para aprender el algoridmo que estas ocupando, dieme como buscarlo en internet o algo 
# para saber como se hace
##
                    





 
# Preguntas abordadas:
# Pregunta 15:
# Quiero aclarar lo del contador de las estaciones, cuando cuenta cuando descuenta, etc, me parece que en el bucle no esta
# tan claro, incluso propenso a errores
# para aclarar;
# Las estaciones tienen un contador que acumula x cada segundo, cada vez que este numero llega a un numero entero, cada numero
# entero se debe combertir en una peticion a un vm para cumplir la demanda de la estacion, a este sistema que incluy eel contador
# y el sistema de peticion para suplir la demanda de la estacion se le conoce como sistema de taza
# el sistema de taza se encarga de etiquetar a los vms con muy baja prioridad para que suban a la estacion, la ida principal de este
# sistema es lograr que suban demanda vms a la estacion para que satisfaga la demanda.
# Es importante mencionar que a ojos de la estacion cualquier vm que este subiendo por la estacion esta aportando a suplir la demanda
# de la estacion, da lo mismo si tiene o no la etiqueta de demanda, cualquier vm que este subiendo debe estar contado en el contador
# por que esta ayudando a suplir la demanda, por lo tanto hay considerar un patron especial para que el contador contabilize bien
# los vms que estan entrando a la estacion.
# este patron conciste en;
# como dije anteriormente cualqueir el sistema de taza intenta etiquetar vms con baja prioridad para que suban a la estacion, una etiquta
# de taza hace que la juntion de manera no forzosa lo pueda incorporar a algun arbol de la estacion.
# existen distintas situaciones que deben estar cubirtas;
# la primera es que un vm tenga la etiqueta de taza, en tal caso cuando se va a poner la etiqueta, se descuenta uno del contador, vale decir
# estacion solictia sistema de taza y se descuenta 1, el sistema de taza intenta etiquetar a alguien, si no logra etiquetar vuleve a decirle
# a la estacion, no logre etiquetar por lo tanto voy a reponer la solicitud que no puede cumplir (de esta manera no se contabiliza una peticion 
# que no se pudo cumplir), si es que el vm es etiquetado, entonces ya desconto del contador por lo tanto cuano pase por junction y suba a un arbol
# no se debe contabilizar de nuevo en el contador (desconto cuando se puso la etiqueta), en el caso de que por algun motivo, no suba a ningun arbol
# como ya desconto al contador se tiene que reponer el contador por que falto a su promesa de que iba a ir a la estacion por lo tanto debe habisar
# a la estacion que recomponga su peticion (se debe revisar cada vm que pasa por la juntion y comprobar que no tenga o que si tenga etiqutea de taza
# para ver si hay que restaurar contador, restar al contador o mantener)
# para los casos de destino o de reserva, no se descuenta al contador cuando se agrega la etiqueta por lo tanto, en la junction si por algun motivo
# entran a algun arbol como van a una estacion, se debe considerar en la demana (si un vm que no tiene etiqueta de taza entra a la estacion, en ese mismo 
# momento debe descontar al contador por que no habia sido considerado), si por el contrario sigue de largo como nunca fue considerado en el contador de taza
# no se tiene la nesesidad de actualizar el contador por que no fue considerado y no entro#
# Preunta 1:
# En update me hace mas sentido que el paso 8b sea antes que el 8a, por que el sistema de reserva
# es SIEMPRE es mas urgente que el sistema de taza. Cabe destacar que ambos sistemas deben preferir
# slots con etiquetas previas tanto el de reserva como el de taza, pero el de taza se debe adaptar al
# de reserva, no al revez, comenta que te parece, dieme si hay algun problema con cambiar ese orden,
# o dieme si es que habria alguna consecuencia si te parece bien o mal.

# esta pregunta surge por el docstring de la la lienea 89, por que de hecho deberia ser al revez, los
# dos sistemas deberian buscar con mas prioridad a los que ya estan etiquetados de parte de la misma
# estacion
# Pregunta 2:
# En handle crossing tengo un punto con el parrafito 2 del docstring, dice que para 
# destination_station_id si el vm no entra a ningun arbol (vm con pasajeros que van a la estacion pero
# no pueden hacerlo por que los arboles estan saturados), dice que ese vm debe darse la vuelta compelta
# al circuito y despues volver a intentarlo en la misma estacion.
# no se si eso me parece correcto, lo correcto es que el vm continue y intente subir a la siguiente
# estacion eso equibala a que si una persona no se alcanza a subir en la estacion se baja en la siguiente
# tiene que caminar un par de cuadras de vuelta, pero lo que propones es que se de la vuelta completa que
# es demasiado. para arreglar este problema, creo que seria prudente camgiar la etiqueta de taza por el id
# de la siguente estacion y ponner un wraning que diga que como no subio este vm a la estacion a la que iba
# se le pueso la etiquta de la esacion que sigue y despues cuando los parsajesro lleguen a la estacion
# reviar si iban efectivamte a la estacion los pasajeros y si no es asi que salga un wuarnig de nuevo o no se
# como expersarlo, que diga se bajaron pasajerso que iban a esta estacion en la estacion tal, para eso es
# cosa de revisar a que estaicon iban lso pasajeros que llegan a sus destinos al llegar
# Pregunta 12:
# Veo muchos prints repartidos por ahi, no se si es buena practica, tengo entendido que ibamos a hacer un archvio en 
# algun momento donde van a estar todos los logs para que este mas ordenado y podamos modificar los prints en algun 
# lugar, no se si es correcto pero la ida es que los prints los podamos apagar y prender e pendiendo que estemos 
# debugeando de manera facil y ademas podeamos refactorizarlos facil tambien
# Pregunta 13:
# pregunto lo mismo que en seciones anteriores, por que se difinen funciones dentro de funciones, en la ultima funcion
# se ocupa dos veces una funcion con el mismo nombre, explicate 


## Preguntas de test ##
# Pregunta 10:
# Ahora que tenemos el circuto cerrado quiero revisar que no tengamos ningun bug silencioso, como lo puedo hacer
# me peudes decir como es que se hacen los test de integracion para revisar que todo funcione como deberia
# me gustaria revisar el ciclo de las etiquetas, saber cuando nacen y cuando mueren o se limpia cada una y todas
# las combinaciones posibles dignas de evaluar
# me gustaria testear el bucle pricipal para verificar que tan verdad es que debe comportarse de esa manera y que pasa
# si unna parte del ciclo se adelata a otra
# me gustaria testear que pasa en situaciones de saturacion, como se comportan las etiquetas y los VMs etc
# me gustaria testear los sistemas de demanda de destino y de reserva si funcionan bien en diferentes casos
# situaciones si son compatibles etc
# si hacern bien los calculos
# Pregunta 11:
# me gustan las prioridades que pusiste pero es sumamente importante tenerles un ojo espcial por que se nos pueden
# estar escapando algunos casos o estamos dejando pasar casos no optimos asi que vale la pena saber donde estan y como
# y como podemos mejorarlos y si hay algo mas que explorar, queiro  que me ayudes a ver posibilidades para todas las
# busquedas con rango y que nesesten de una priorisacion
# Pregunta 16:
# Nos falta testear las etiquetas de continous train para asegur la reserva (a que slot va a llegar el vm) y para la etiqueta
# de reserva (asegura reserva del vm)


## Preguntas de Explcaciones ##
# Pregunta 4:
# no entiendo que esta pasando en la funcion de handle crossing nesesito que me la expliques y debemos comentarla            
# Pregunta 5:
# cuando se utiliza handle desicions? estoy perdido el encargado en una juntion de ver a que arbol le llega el vm
# es junction no brain puede ser?, y si ese es el caso entonces por que esta funcion, es para un esenario distinto
# quien determino que el vm va por el camino menos saturado?
# Pregunta 7:
# yo se que ahora esta todo mucho mas documentado pero de todas maneras me cuesta entender que hace cada funcion
# y en que caso se ocupa, me encantaria repasar cada fucion y ver por que se estan haciendo asi las cosas
# Pregunta 9:
# Todavia no entiendo muy bien como es que el sistema entiene la ventana en la que hay que buscaer en rango para no
# saturar la junction, se que la ventana mira x cantidad de vms que corresponde a un calculo matematico que revisa
# para que no halla saturacion pero me esta constando ver como es que te das cuenta para que no se sature

# Pregunta 19:
# en la funcion make_reservation tengo una duda
# el pasajero aborda en la mitad de la lene, esta fucnion se ejecuta mas o menos al pricipio de la lane, como es que registra el destino si para que se suba un pasajero hay que
# esperar mucho tiempo mitad de la lene no al principio, esta fucion de definir el destino del vm no deberia impulsarla el pasajero al subirse al vm que le dice al vm para donde va
# y posteriormente el vm le dice al slot?

# Pregunta 17:
# en la funcion _handle crossings
# el punto 1 que se toca "Si había demanda para otra estación (demand != None and demand != S), esa promesa se rompe → on_commitment_broken() para la otra estación"
# para nuetro caso de uso sirve pero en verdad no esta bien pensado, por que claro, yo se que el up de la estacion siguiete est despues que el down de la estacion
# anterior por como puse yo las estaciones, pero en un futuro se podria pensar en poner el el UP de la siguiente antes del DOWN de la anteror, en tal caso eso que dices
# que quieres romper la promesa es super peligroso, asi que me gustria dejarlo super documentado como que siempre tiene que haber un UP - DOWN y no una cobinacion, por 
# que si no pueden pasar estas cosas, en el fondo esto se mantiene por que siempre una reserva se produce entre los arboles de la etacion, pero podria pasar que qeu enre
# los arboles hubiera otro arbol de otra estacion, la otra solucion a eso es "si una reserva de cierta estacion x continua vigente aunque el arbol DOWN de dicha estacion 
# ya paso quiere decir que esta reserva fue incumplida.
# no se si se entiende lo que digo pero por ultimo si es que no es posible implementar esto hay que dejarlo super documentado para que a nadie se le ocurra poner la situacion
# mencionada, y lo mejor en un futuro lo podemos arreglar con lo que te comente


