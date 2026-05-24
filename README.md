# Simulacion Tren continuo con Vehículos modulares ##

El proposito es demostrar a traves de la simulacion la factibilidad y de este sistema de trasporte.
Se podan realizar pruebas de carga y modificar la simulacion para adaptarse a situaciones adversas
Esta version de la simulacion debera concentrar las mejores alternativas de diseño encontradas hasta este momento.

### Comando para Correr simulacion
```bash
python3 main.py

```
## Comandos para monitorear simulacion

#### Conteo de lineas
```bash
# En la carpeta NSim con abiente activado
cloc config objects simulation systems tests tracks CLAUDE.md main.py README.md --exclude-dir=__pycache__
```

#### Comando para testear de manera general
```bash
pytest tests/
pytest tests/ -v # Para ver mas detalles
```

#### Comando para testear archivo espesifico
```bash
python -m pytest tests/{{nombre_archivo_test}} -v
```

## Comandos para operar Ambiente uv

#### Crear entorno virtual por primera vez
```bash
uv init
```
#### Activar entorno virtual
```bash
source .venv/bin/activate
```
#### Instalacion de dependencias
```bash
uv add {{dependencia}}
```
#### Gestion de dependencias
si durante el desarollo se instalan nueva sdependencias, asegure que se actualize el archivo de requerimientos para mantener compatibilidad.
```bash
uv sync
```
#### Desactivar entorno
```bash
deactivate
```
