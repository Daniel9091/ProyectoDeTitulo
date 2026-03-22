from objects.base import Vector3


class ContinuousTrain:
    """
    TREN CONTINUO - Gestiona todos los VMs del carril inferior como un tren único.

    Modelo:
    - Una "cola" (tail) avanza a velocidad constante (20 m/s) en 1D.
    - Los VMs ocupan slots discretos. Posición del slot i = (tail_x + i * spacing) % total_length.
    - spacing = vm_length + gap (default 2m = 1m VM + 1m gap).
    - Los slots se almacenan en un diccionario {slot_index: ModularVehicle}.
    - Slots vacíos simplemente no existen en el diccionario.

    Coordenada 1D (belt_x):
    - Va de 0 a total_length (loop cerrado, aritmética modular).
    - Se mapea a posición 3D recorriendo los tracks en orden.

    Responsabilidades:
    - Avanzar la cola cada frame (un solo cálculo mueve todo el tren).
    - Insertar/remover VMs en slots discretos.
    - Convertir belt_x → posición 3D para rendering.
    - Predecir colisiones cuando un VM baja de un árbol de aceleración.
    """

    def __init__(self, track_order, speed=20.0, vm_length=1.0, gap=1.0):
        """
        Args:
            track_order: Lista de tracks (StationConnector) en orden del loop.
                         Ejemplo: [track_7, track_8, track_9, track_10, track_11, track_12]
            speed: Velocidad constante del tren en m/s.
            vm_length: Longitud de un VM en metros.
            gap: Espaciamiento mínimo entre VMs en metros.
        """
        self.tracks = track_order
        self.speed = speed
        self.vm_length = vm_length
        self.gap = gap
        self.spacing = vm_length + gap  # Distancia total entre centros de VMs consecutivos

        # Calcular longitud total del loop
        self.total_length = sum(t.length for t in self.tracks)

        # Número máximo de slots
        self.max_slots = int(self.total_length / self.spacing)

        # Posición 1D de la cola (slot 0). Avanza con el tiempo.
        self.tail_x = 0.0

        # Diccionario de slots ocupados: {slot_index: list[ModularVehicle]}
        # Usa listas para soportar doble ocupación sin perder VMs
        self.slots = {}

        # Pre-calcular la tabla de segmentos para conversión belt_x → 3D
        # Cada entrada: (accumulated_start, accumulated_end, track)
        self._segment_table = []
        accumulated = 0.0
        for track in self.tracks:
            self._segment_table.append((accumulated, accumulated + track.length, track))
            accumulated += track.length

        # Pre-calcular coordenadas belt_x de las junctions (inicio de cada track)
        # Útil para saber dónde se conectan los árboles de aceleración
        self.junction_belt_x = {}
        acc = 0.0
        for track in self.tracks:
            self.junction_belt_x[track.track_id] = acc
            acc += track.length
        # También guardar el belt_x del FINAL de cada track (= inicio del siguiente)
        self.junction_end_belt_x = {}
        acc = 0.0
        for track in self.tracks:
            acc += track.length
            self.junction_end_belt_x[track.track_id] = acc % self.total_length

        print(f"🚂 ContinuousTrain inicializado:")
        print(f"   Longitud total: {self.total_length:.2f}m")
        print(f"   Spacing: {self.spacing:.2f}m")
        print(f"   Max slots: {self.max_slots}")
        print(f"   Velocidad: {self.speed} m/s")
        print(f"   Tracks: {[t.track_id for t in self.tracks]}")

    # ========== MOVIMIENTO ==========

    def advance(self, dt):
        """
        Avanza la cola del tren por dt segundos.
        ÚNICO cálculo de movimiento por frame para todos los VMs del carril inferior.

        Fórmula MRU: x = x₀ + v * t
        """
        self.tail_x = (self.tail_x + self.speed * dt) % self.total_length

        # Actualizar posición 3D de todos los VMs en el tren
        for slot_index, vm_list in self.slots.items():
            belt_x = self.get_slot_belt_x(slot_index)
            position_3d = self.belt_x_to_3d(belt_x)
            for vm in vm_list:
                vm.current_position = position_3d

    # ========== POSICIONES ==========

    def get_slot_belt_x(self, slot_index):
        """
        Calcula la coordenada 1D (belt_x) del slot dado.

        Fórmula: belt_x = (tail_x + slot_index * spacing) % total_length
        """
        return (self.tail_x + slot_index * self.spacing) % self.total_length

    def belt_x_to_3d(self, belt_x):
        """
        Convierte una coordenada 1D (belt_x) a posición 3D real.
        Recorre la tabla de segmentos para encontrar en qué track cae.

        Este es EL MISMO cálculo usado para movimiento y rendering.
        No hay modelos separados.
        """
        # Normalizar por si acaso
        belt_x = belt_x % self.total_length

        for seg_start, seg_end, track in self._segment_table:
            if seg_start <= belt_x < seg_end:
                # Progreso dentro de este track (0 a 1)
                local_distance = belt_x - seg_start
                progress = local_distance / track.length if track.length > 0 else 0.0
                return track.calculate_position_at_progress(progress)

        # Fallback: si belt_x == total_length exacto, es el inicio del primer track
        return self.tracks[0].calculate_position_at_progress(0.0)

    def belt_x_to_slot_index(self, belt_x):
        """
        Dado un belt_x, calcula el slot_index más cercano.
        Retorna el índice del slot cuya posición teórica está más cerca de belt_x.
        """
        # Distancia desde la cola hasta belt_x (en dirección del tren)
        delta = (belt_x - self.tail_x) % self.total_length
        # Slot más cercano
        slot_index = round(delta / self.spacing)
        # Wrap-around: si excede max_slots, corresponde al slot 0 (la cola)
        if slot_index >= self.max_slots:
            slot_index = 0
        return slot_index

    # ========== GESTIÓN DE VMs ==========

    def add_vm(self, vm, slot_index):
        """
        Inserta un VM en un slot específico.
        Permite doble ocupación (dos VMs en mismo slot) para demostrar el problema.

        Args:
            vm: ModularVehicle a insertar.
            slot_index: Índice del slot donde se inserta.

        Returns:
            bool: True si se insertó correctamente.
        """
        if slot_index < 0 or slot_index >= self.max_slots:
            print(f"ERROR ContinuousTrain: slot_index {slot_index} fuera de rango [0, {self.max_slots})")
            return False

        if slot_index in self.slots:
            existing_ids = [v.vehicle_id for v in self.slots[slot_index]]
            print(f"⚠️  ContinuousTrain: Slot {slot_index} ya ocupado por {existing_ids}. "
                  f"Insertando VM {vm.vehicle_id} de todas formas (doble ocupación permitida para demo).")
            self.slots[slot_index].append(vm)
        else:
            self.slots[slot_index] = [vm]

        # Actualizar posición 3D y velocidad del VM
        belt_x = self.get_slot_belt_x(slot_index)
        vm.current_position = self.belt_x_to_3d(belt_x)
        vm.velocity = Vector3(self.speed, 0, 0)
        vm.current_track = None  # Gestionado por ContinuousTrain, no por un track individual
        vm.current_station = None  # Limpiar referencia a estación
        vm.state = "moving"
        vm._in_train = True
        vm._train_slot = slot_index

        return True

    def remove_vm(self, vm):
        """
        Remueve un VM del tren continuo (cuando sube a un árbol de aceleración).

        Args:
            vm: ModularVehicle a remover.

        Returns:
            int or None: slot_index que ocupaba, o None si no estaba en el tren.
        """
        target_slot = None
        for slot_index, vm_list in self.slots.items():
            for v in vm_list:
                if v.vehicle_id == vm.vehicle_id:
                    target_slot = slot_index
                    break
            if target_slot is not None:
                break

        if target_slot is not None:
            self.slots[target_slot] = [v for v in self.slots[target_slot] if v.vehicle_id != vm.vehicle_id]
            if not self.slots[target_slot]:
                del self.slots[target_slot]
            vm._in_train = False
            vm._train_slot = None
            return target_slot

        print(f"WARNING ContinuousTrain: VM {vm.vehicle_id} no encontrado en el tren.")
        return None

    def find_first_free_slot(self, start_slot=0):
        """
        Busca el primer slot libre comenzando desde start_slot.

        Returns:
            int or None: Índice del slot libre, o None si todos están ocupados.
        """
        for i in range(start_slot, self.max_slots):
            if i not in self.slots:
                return i
        # Wrap-around: buscar desde el inicio
        for i in range(0, start_slot):
            if i not in self.slots:
                return i
        return None

    def find_slot_at_junction(self, junction_belt_x):
        """
        Encuentra el slot que está pasando por una junction en este instante.
        Usado cuando un VM baja de un árbol y necesita reincorporarse.

        Args:
            junction_belt_x: Coordenada 1D de la junction.

        Returns:
            int: Índice del slot más cercano a la junction.
        """
        return self.belt_x_to_slot_index(junction_belt_x)

    def is_slot_occupied(self, slot_index):
        """Verifica si un slot está ocupado."""
        return slot_index in self.slots and len(self.slots[slot_index]) > 0

    def get_vm_at_slot(self, slot_index):
        """Retorna el primer VM en un slot, o None si está vacío."""
        vm_list = self.slots.get(slot_index, [])
        return vm_list[0] if vm_list else None

    def get_vms_at_slot(self, slot_index):
        """Retorna todos los VMs en un slot (para doble ocupación)."""
        return self.slots.get(slot_index, [])

    def get_vm_slot(self, vm):
        """Retorna el slot_index de un VM, o None si no está en el tren."""
        for slot_index, vm_list in self.slots.items():
            for v in vm_list:
                if v.vehicle_id == vm.vehicle_id:
                    return slot_index
        return None

    # ========== PREDICCIÓN DE COLISIÓN ==========

    def predict_collision_at_junction(self, junction_belt_x, time_to_arrival):
        """
        Predice si habrá colisión cuando un VM baje de un árbol de aceleración.

        Lógica (misma fórmula MRU que usa el tren):
        1. En 'time_to_arrival' segundos, el tren habrá avanzado d = speed * time_to_arrival.
        2. La cola estará en: future_tail_x = (tail_x + d) % total_length.
        3. Calculamos qué slot estará en la junction en ese momento futuro.
        4. Si ese slot está ocupado → colisión.

        Args:
            junction_belt_x: Coordenada 1D donde el VM llegará al carril inferior.
            time_to_arrival: Tiempo en segundos hasta que el VM llegue a la junction.

        Returns:
            dict or None: Info de colisión si la hay, None si es seguro.
        """
        # Posición futura de la cola (MRU: x = x₀ + v*t)
        future_tail_x = (self.tail_x + self.speed * time_to_arrival) % self.total_length

        # ¿Qué slot estará en la junction en ese momento?
        delta = (junction_belt_x - future_tail_x) % self.total_length
        future_slot_index = round(delta / self.spacing)

        if future_slot_index >= self.max_slots:
            future_slot_index = 0

        # Verificar si ese slot está ocupado AHORA
        # (asumimos que ningún VM entra/sale del tren en el intervalo — simplificación válida)
        if self.is_slot_occupied(future_slot_index):
            conflicting_vm = self.get_vm_at_slot(future_slot_index)
            return {
                'slot_index': future_slot_index,
                'conflicting_vm': conflicting_vm,
                'future_tail_x': future_tail_x,
                'junction_belt_x': junction_belt_x,
                'time_to_arrival': time_to_arrival
            }

        # También verificar slots adyacentes (margen de seguridad)
        for offset in [-1, 1]:
            adjacent_slot = future_slot_index + offset
            if 0 <= adjacent_slot < self.max_slots and self.is_slot_occupied(adjacent_slot):
                conflicting_vm = self.get_vm_at_slot(adjacent_slot)
                # Calcular distancia real entre el VM y la junction (con wrap-around)
                adjacent_belt_x = (future_tail_x + adjacent_slot * self.spacing) % self.total_length
                raw_distance = abs(junction_belt_x - adjacent_belt_x)
                distance = min(raw_distance, self.total_length - raw_distance)
                # Si están a menos de spacing/2, hay riesgo
                if distance < self.spacing * 0.5:
                    return {
                        'slot_index': adjacent_slot,
                        'conflicting_vm': conflicting_vm,
                        'future_tail_x': future_tail_x,
                        'junction_belt_x': junction_belt_x,
                        'time_to_arrival': time_to_arrival,
                        'note': 'slot adyacente, riesgo de proximidad'
                    }

        return None  # Seguro, no hay colisión

    # ========== REINCORPORACIÓN DESDE ÁRBOL ==========

    def reincorporate_vm(self, vm, junction_belt_x):
        """
        Reincorpora un VM al tren cuando baja de un árbol de aceleración.

        Reglas:
        - Busca el slot más cercano a la junction.
        - Si está libre, lo ocupa.
        - Si está ocupado, se permite doble ocupación (para demostrar el problema al profesor).

        Args:
            vm: ModularVehicle que se reincorpora.
            junction_belt_x: Coordenada 1D de la junction.

        Returns:
            int: Slot index donde se insertó.
        """
        slot_index = self.find_slot_at_junction(junction_belt_x)

        if self.is_slot_occupied(slot_index):
            existing_ids = [v.vehicle_id for v in self.slots[slot_index]]
            print(f"\n{'='*40}")
            print(f"⚠️  DOBLE OCUPACIÓN EN SLOT {slot_index}")
            print(f"   VMs existentes: {existing_ids}")
            print(f"   VM entrando:  {vm.vehicle_id}")
            print(f"   Junction belt_x: {junction_belt_x:.2f}")
            print(f"{'='*40}\n")
            self.slots[slot_index].append(vm)
        else:
            self.slots[slot_index] = [vm]

        belt_x = self.get_slot_belt_x(slot_index)
        vm.current_position = self.belt_x_to_3d(belt_x)
        vm.velocity = Vector3(self.speed, 0, 0)
        vm.current_track = None
        vm.current_station = None
        vm.state = "moving"
        vm._in_train = True
        vm._train_slot = slot_index

        return slot_index

    # ========== SPAWN ==========

    def spawn_vm_in_slot(self, vm, slot_index=None):
        """
        Coloca un VM recién creado en el tren continuo.

        Args:
            vm: ModularVehicle recién creado.
            slot_index: Slot específico, o None para buscar el siguiente libre.

        Returns:
            int or None: Slot donde se colocó, o None si no hay espacio.
        """
        if slot_index is None:
            slot_index = self.find_first_free_slot()

        if slot_index is None:
            print(f"ERROR ContinuousTrain: No hay slots libres para spawn de VM {vm.vehicle_id}")
            return None

        self.add_vm(vm, slot_index)
        return slot_index

    # ========== CONSULTAS ==========

    def get_occupied_slots_count(self):
        """Retorna el número de slots ocupados."""
        return len(self.slots)

    def get_all_vms(self):
        """Retorna lista de todos los VMs en el tren."""
        result = []
        for vm_list in self.slots.values():
            result.extend(vm_list)
        return result

    def get_total_vms_count(self):
        """Retorna el total de VMs en el tren (incluyendo dobles ocupaciones)."""
        return sum(len(vm_list) for vm_list in self.slots.values())

    def is_vm_in_train(self, vm):
        """Verifica si un VM está en el tren."""
        return any(v.vehicle_id == vm.vehicle_id for vm_list in self.slots.values() for v in vm_list)

    # ========== DEBUG ==========

    def debug_print(self):
        """Imprime estado completo del tren para diagnóstico."""
        print(f"\n{'='*50}")
        print(f"🚂 ESTADO DEL TREN CONTINUO")
        print(f"   tail_x: {self.tail_x:.2f}m")
        total_vms = self.get_total_vms_count()
        print(f"   VMs en tren: {total_vms} en {len(self.slots)} slots / {self.max_slots}")
        print(f"   Velocidad: {self.speed} m/s")

        if self.slots:
            sorted_slots = sorted(self.slots.items())
            for slot_idx, vm_list in sorted_slots:
                belt_x = self.get_slot_belt_x(slot_idx)
                for vm in vm_list:
                    double = " [DOBLE]" if len(vm_list) > 1 else ""
                    print(f"   Slot {slot_idx:4d}: VM {vm.vehicle_id:<15s} belt_x={belt_x:8.2f}m  pos=({vm.current_position.x:.1f}, {vm.current_position.y:.1f}, {vm.current_position.z:.1f}){double}")
        else:
            print("   (sin VMs)")
        print(f"{'='*50}\n")
