DARK = {
    "bg":            (  8,  12,  18),
    "text_bright":   (220, 230, 245),
    "text_dim":      (165, 180, 200),
    "vm_default":    (190, 225, 250),
    "vm_default_gl": ( 40,  70,  70),
    "track_glow":    (  0,  20,  80),
    "vm_passengers": (255, 255, 255),
    "junction_dot":  (255, 220,   0),
    "hud_bg":        (  8,  12,  20, 220),
    "panel_bg":      (  8,  12,  20, 220),
}

LIGHT = {
    "bg":            (240, 242, 248),
    "text_bright":   ( 20,  25,  40),
    "text_dim":      ( 80,  95, 120),
    "vm_default":    ( 40, 100, 200),
    "vm_default_gl": (240, 242, 248),
    "track_glow":    (240, 242, 248),
    "vm_passengers": ( 10,  10,  10),
    "junction_dot":  (180, 130,   0),
    "hud_bg":        (225, 228, 238, 220),
    "panel_bg":      (225, 228, 238, 220),
}

active = DARK


def toggle():
    global active
    active = LIGHT if active is DARK else DARK
