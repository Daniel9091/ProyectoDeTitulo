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