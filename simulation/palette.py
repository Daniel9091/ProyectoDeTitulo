DARK = {
    "bg":            (  8,  12,  18),
    "text_bright":   (220, 230, 245),
    "text_dim":      (165, 180, 200),
    "hud_bg":        (  8,  12,  20, 220),
    "panel_bg":      (  8,  12,  20, 220),
    "track_glow":    (  0,  20,  80),
    "junction_dot":  (255, 220,   0),
    "vm_default":    (190, 225, 250),   # sky blue — VM sin etiqueta activa
    "vm_default_gl": ( 40,  70,  70),   # glow — halo de VMs en tránsito
    "vm_demand":     (255, 225,   0),   # amarillo — etiqueta de demanda
    "vm_boarding":   (255,  50, 200),   # fucsia neón — pasajeros subiendo activamente
    "vm_reserved":   (215, 175, 250),   # violeta — etiqueta de reserva de slot
    "vm_dest":       ( 40, 255, 120),   # verde — etiqueta de destino confirmado
    "vm_collision":  (255,   0,   0),   # rojo — choque: 2+ VMs en el mismo slot
    "vm_passengers": (255, 255, 255),   # blanco — indicador interior con pasajeros
}

LIGHT = {
    "bg":            (240, 242, 248),
    "text_bright":   ( 20,  25,  40),
    "text_dim":      ( 80,  95, 120),
    "hud_bg":        (225, 228, 238, 220),
    "panel_bg":      (225, 228, 238, 220),
    "track_glow":    (240, 242, 248),
    "junction_dot":  (160, 110,   0),
    "vm_default":    ( 10,  50, 140),   # azul profundo — VM sin etiqueta activa
    "vm_default_gl": (180, 200, 230),   # glow claro — halo de VMs en tránsito
    "vm_demand":     (255, 225,   0),   # amarillo — etiqueta de demanda
    "vm_boarding":   (160,   0, 130),   # fucsia oscuro — pasajeros subiendo activamente
    "vm_reserved":  (215, 175, 250),    # violeta intenso — etiqueta de reserva de slot
    "vm_dest":       ( 40, 255, 120),   # verde intenso — etiqueta de destino confirmado
    "vm_collision":  (200,   0,   0),   # rojo oscuro — choque: 2+ VMs en el mismo slot
    "vm_passengers": ( 10,  10,  10),   # casi negro — indicador interior con pasajeros
}


active = DARK


def toggle():
    global active
    active = LIGHT if active is DARK else DARK
