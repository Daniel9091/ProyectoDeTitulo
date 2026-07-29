import cProfile, pstats
import sys, os, time
import importlib
from setproctitle import setproctitle
sys.path.insert(0, os.path.dirname(__file__))

import json
from pathlib import Path
from datetime import datetime
from simulation.simulation import Simulation

from telemetry.recorder import Recorder, NullRecorder
from config.constants    import FPS, SCREEN_WIDTH, SCREEN_HEIGHT, TELEMETRY_ENABLED
import config.constants as C
from simulation.run_config import extract_run_config

import logging
logging.disable(logging.CRITICAL)

DT     = 1.0 / FPS
SPEEDS = [1, 2, 5, 10]

# ─── Configuración de corrida ────────────────────────────────────────────
SCENARIO_NAME = "linea_1_edit"
SEED          = 42
HEADLESS      = True    # True = sin render, tan rápido como el CPU
SIM_DURATION  = 300   # segundos simulados (solo si HEADLESS = True)
# ─────────────────────────────────────────────────────────────────────────

if not HEADLESS:
    import pygame
    from simulation.inspector import Inspector
    from simulation.camera   import Camera
    from simulation.renderer import Renderer


def main():

    seed = SEED
    scenario_name = SCENARIO_NAME

    scenario = importlib.import_module(f"simulation_builder.{scenario_name}")


    run_id  = f"{scenario_name}_seed{seed}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path("runs") / run_id
    recorder = Recorder(run_dir, run_id) if TELEMETRY_ENABLED else NullRecorder()


    print(f"Construyendo escenario... (run_id={run_id})")
    build_start = time.perf_counter()
    brain, stations = scenario.build(seed=seed, recorder=recorder)
    build_seconds = time.perf_counter() - build_start

    cfg = extract_run_config(brain, stations)
    cfg["run_id"] = run_id
    cfg["seed"] = seed
    cfg["scenario_name"] = scenario_name
    cfg["headless"] = HEADLESS
    cfg["sim_duration"] = SIM_DURATION if HEADLESS else None
    recorder.run_started(t=0.0, config=cfg)

    # brain._process_reservations = lambda: None   # ← LÍNEA TEMPORAL: apaga reservas para forzar choques
    
    sim   = Simulation(brain, stations)
    train = brain._train

    sim_wall_seconds = 0.0
    try:
        if HEADLESS:
            print(f"Modo headless — simulando {SIM_DURATION:.0f}s...")
            t0 = time.perf_counter()
            sim.run_headless(SIM_DURATION)

            ## -- TABLA CON FUNCIONES CUELLO DE BOTELLA --##

            # with cProfile.Profile() as pr:
            #     sim.run_headless(300)
            # stats = pstats.Stats(pr).sort_stats('cumulative')
            # stats.print_stats(20)

            ## --                                       --##
            
            sim_wall_seconds = time.perf_counter() - t0
            ratio = sim.current_time / sim_wall_seconds
            print(f"\n{'─'*44}")
            print(f"  Build:      {build_seconds:.2f}s")
            print(f"  Simulados:  {sim.current_time:.1f}s")
            print(f"  Loop pared: {sim_wall_seconds:.2f}s reales")
            print(f"  Ratio:      {ratio:.1f}x tiempo real")
            print(f"{'─'*44}")

        else:
            pygame.init()
            pygame.display.set_caption("NSim — Sistema de Transporte Modular")
            screen   = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
            clock    = pygame.time.Clock()
            font_sm  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 16)
            font_md  = pygame.font.SysFont("dejavusansmono,consolas,couriernew,monospace", 20, bold=True)


            is_fullscreen = False
            windowed_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

            z_belt   = train.start_pos.z
            camera   = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                            pos=[1500.0, -600.0, 250.0], yaw=90.0, pitch=-20.0)
            renderer = Renderer(font_sm, font_md)
            inspector = Inspector(font_sm, font_md)

            speed_idx = 0
            paused    = False

            print("Corriendo — Esc para salir (o cerrar fullscreen). F11 = pantalla completa.")
            running = True
            while running:
                dt_real = clock.tick(FPS) / 1000.0

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False

                    elif event.type == pygame.VIDEORESIZE:

                        if not is_fullscreen:
                            windowed_size = (event.w, event.h)
                            camera.on_resize(event.w, event.h)

                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if is_fullscreen:
                                is_fullscreen = False
                                pygame.display.toggle_fullscreen()
                                screen = pygame.display.get_surface()
                                camera.on_resize(*screen.get_size())
                            else:
                                running = False
                        elif event.key == pygame.K_F11:
                            is_fullscreen = not is_fullscreen
                            pygame.display.toggle_fullscreen()
                            screen = pygame.display.get_surface()
                            camera.on_resize(*screen.get_size())

                        elif event.key == pygame.K_SPACE: paused    = not paused
                        elif event.key == pygame.K_1:     speed_idx = 0
                        elif event.key == pygame.K_2:     speed_idx = 1
                        elif event.key == pygame.K_3:     speed_idx = 2
                        elif event.key == pygame.K_4:     speed_idx = 3

                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        inspector.handle_click(
                            event.pos, camera, train, brain._network, stations,
                            screen.get_width(),
                        )

                    camera.handle_event(event)



                camera.update(dt_real)

                if not paused:
                    for _ in range(SPEEDS[speed_idx]):
                        sim.step(DT)

                renderer.render(
                    screen, camera, train, brain._network, stations,
                    sim.current_time, clock.get_fps(),
                    SPEEDS[speed_idx], paused,
                )
                inspector.render(
                    screen, camera, train, brain._network, stations,
                    screen.get_width(),
                )

                pygame.display.flip()

            pygame.quit()
            print(f"Parado en t={sim.current_time:.1f}s")

    finally:
        train_laps = sim.current_time * C.TRAIN_SPEED / train.total_length
        summary = {
            "headless":           HEADLESS,
            "simulated_seconds":  sim.current_time,
            "build_seconds":      round(build_seconds, 3),
            "sim_wall_seconds":   round(sim_wall_seconds, 2),
            "total_wall_seconds": round(build_seconds + sim_wall_seconds, 2),
            "train_laps":         round(train_laps, 3),
        }
        if HEADLESS and sim_wall_seconds > 0:
            summary["ratio"] = round(sim.current_time / sim_wall_seconds, 1)

        brain.emit_vm_summaries(sim.current_time)
        recorder.run_ended(t=sim.current_time, summary=summary)
        recorder.close()

        if TELEMETRY_ENABLED:
            with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            index_path = Path("runs") / "index.jsonl"
            with open(index_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "run_id":        run_id,
                    "seed":          seed,
                    "scenario_name": scenario_name,
                    "events_path":   str(run_dir / "events.jsonl"),
                }) + "\n")


if __name__ == "__main__":
    setproctitle("nsim")
    main()





# documentacion pypy
# loggings citical (sacar y agregar a los logs reales)
