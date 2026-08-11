"""
Extrae la configuración completa de una corrida desde los objetos ya construidos.
Funciona para cualquier escenario sin modificarlo.
"""
import config.constants as C


def extract_run_config(brain, stations: dict) -> dict:
    """
    Extrae la configuración completa de una corrida a un dict JSON-serializable.
    Accede a brain._train directamente para leer el estado del belt.
    """
    train = brain._train

    vm_capacity = None
    for slot in train.slots:
        if slot['vm'] is not None:
            vm_capacity = slot['vm'].capacity
            break

    belt = {
        "total_length_m":  round(train.total_length, 2),
        "max_slots":       train.max_slots,
        "density":         train.density,
        "vm_capacity":     vm_capacity,
        "junction_points": {
            str(sid): round(bx, 2)
            for sid, bx in sorted(train.junction_points.items())
        },
    }

    station_list = []
    for sid in sorted(stations):
        st = stations[sid]
        station_list.append({
            "station_id":                st.station_id,
            "x":                         round(st.origin.x, 2),
            "y":                         round(st.origin.y, 2),
            "z":                         round(st.origin.z, 2),
            "num_andenes":               st.num_platforms,
            "passenger_rate":            st.passenger_rate,
            "vm_request_rate":           st.vm_request_rate,
            "destination_probabilities": {
                str(k): v for k, v in st.destination_probabilities.items()
            },
        })

    constants = {
        "GRAVITY":                       C.GRAVITY,
        "ACCEL_RANGE_MIN":               C.ACCEL_RANGE_MIN,
        "ACCEL_RANGE_MAX":               C.ACCEL_RANGE_MAX,
        "BOARDING_LANE_SPEED":           C.BOARDING_LANE_SPEED,
        "BOARDING_COMMIT_PROGRESS":      C.BOARDING_COMMIT_PROGRESS,
        "PASSENGER_WALK_SPEED":          C.PASSENGER_WALK_SPEED,
        "TRAIN_SPEED":                   C.TRAIN_SPEED,
        "TRAIN_VM_LENGTH":               C.TRAIN_VM_LENGTH,
        "TRAIN_GAP":                     C.TRAIN_GAP,
        "TRAIN_SPACING":                 C.TRAIN_SPACING,
        "TREE_DZ":                       round(C.TREE_DZ, 4),
        "MIN_VM_SEPARATION":             C.MIN_VM_SEPARATION,
        "TREE_LENGTH":                   C.TREE_LENGTH,
        "SLOT_SEARCH_RANGE_RESERVATION": C.SLOT_SEARCH_RANGE_RESERVATION,
        "SLOT_SEARCH_RANGE_DEMAND":      C.SLOT_SEARCH_RANGE_DEMAND,
        "SLOT_SEARCH_RANGE":             C.SLOT_SEARCH_RANGE,
        "BURST_WINDOW_SAFETY_MARGIN":    C.BURST_WINDOW_SAFETY_MARGIN,
        "SNAPSHOT_INTERVAL":             C.SNAPSHOT_INTERVAL,
        "FPS":                           C.FPS,
        "SCREEN_WIDTH":                  C.SCREEN_WIDTH,
        "SCREEN_HEIGHT":                 C.SCREEN_HEIGHT,
    }

    return {
        "belt":      belt,
        "stations":  station_list,
        "constants": constants,
    }
