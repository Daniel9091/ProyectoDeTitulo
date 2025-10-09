### Comando para correr la simulacion:
```bash
python3 -m simulation.main
```

### Notas Ultima reunion con profesor:

- arbol tree 400 de largo
- andenes con una longitud con 50 m
- habilitar dona
- agregar personas con destingo y cambian el destino
- agregar andenes

### Comando para combertir videos .webm a .mp4
```bash
for f in *.webm; do ffmpeg -i "$f" -c:v libx264 -c:a aac "${f%.webm}.mp4"; done
```

### Cosas Por Hacer:
#### Perspectiva simple
- ~~Corregir perspectiva~~ (Mas dificil de lo que pense)
- ~~Corregir diseño de las estaciones y medidas de las estaciones~~
- Corregir dibujo de los arboles de aceleracion con medidas del profesor
- ~~Corregir medidas de los vm~~

#### Movimiento
- Agregar perspectiva dona
- Agregar mas andenes por estacion (revisar como se elije la ruta en el movimiento)
- agregar nuevo trak que va con la banda en la estacion
- Manejo de que se hace cuando un vm ya llego a la estacion


### Preguntas al profesor
- Como se puedo manejar los choques, si todo esto es denso
- Se me hace complicado de aplicar y de pensar como manejar choques con varios andenes y con flujo denso
- cuenteme de nuevo que era lo de la matriz que me conto la reunion anterior


