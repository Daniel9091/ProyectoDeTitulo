import pygame

# Dibuja los panesles de informacion  en la pantalla
def draw_info_panel(screen, simulation, camera):
    # Fuentes de texto
    font = pygame.font.SysFont(None, 24)
    small_font = pygame.font.SysFont(None, 18)
    
    # Obtener información de los controles principales de la camara
    cam_info = camera.get_info()
    pos_x, pos_y, pos_z = cam_info['position']
    rot_theta, rot_alpha = cam_info['rotation']
    
    # Información principal del estado de la simulacion
    main_info = [
        f"FPS: {pygame.time.Clock().get_fps():.0f}",
        f"Tiempo: {simulation.time_scale:+.1f}x",
        f"Vehículos: {len(simulation.vehicles)}",
        f"Estaciones: {len(simulation.stations)}",
        f"Rutas: {len(simulation.connectors)}",
        f"Pos: ({pos_x:.0f}, {pos_y:.0f}, {pos_z:.0f})",
        f"Rot: ({rot_theta:.0f}°, {rot_alpha:.0f}°)",
        f"Zoom: {cam_info['zoom']:.1f}x",
    ]
    
    # Información de velocidades
    speed_info = [
        f"Vel. Mov: {cam_info['move_speed']:.1f}",
        f"Vel. Vert: {cam_info['vertical_speed']:.1f}",
        f"Vel. Rot: {cam_info['rotation_speed']:.1f}",
        f"Vel. Zoom: {cam_info['zoom_speed']:.2f}",
    ]
    
    # Dibujar información principal (esquina superior derecha)
    for i, line in enumerate(main_info):
        text = font.render(line, True, (255, 255, 255))
        screen.blit(text, (screen.get_width() - text.get_width() - 20, 20 + i * 30))
    
    # Dibujar información de velocidades de controles (esquina superior izquierda)
    for i, line in enumerate(speed_info):
        text = small_font.render(line, True, (200, 200, 255))
        screen.blit(text, (20, 20 + i * 22))
    
    # Información de los botones que controlan(esquina inferior izquierda)
    controls_info = [
        "CONTROLES:",
        "WASD - Movimiento horizontal",
        "QE - Movimiento vertical", 
        "Flechas - Rotar cámara",
        "Z/X - Zoom | Rueda - Zoom",
        "+/- - Velocidad tiempo",
        "Backspace - Rebobinar",
        "P - Pausa/Play",
        "0 - Reinicio TOTAL",
        "R - Reset cámara",
        "I - Mostrar/ocultar info",
        "",
        "AJUSTES VELOCIDAD:",
        "1/2 - Vel. Movimiento",
        "3/4 - Vel. Vertical",
        "5/6 - Vel. Rotación",
        "7/8 - Vel. Zoom",
    ]
    
    # Dibujar controles
    for i, line in enumerate(controls_info):
        if ":" in line:  # Títulos
            color = (255, 255, 0)
        else:  # Items normales
            color = (200, 200, 200)
        
        text = small_font.render(line, True, color)
        screen.blit(text, (20, screen.get_height() - 20 - (len(controls_info) - i) * 22))