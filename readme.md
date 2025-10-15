### Comando para correr la simulacion:
```bash
python3 -m simulation.main
```

### Cosas Por Hacer:

#### Urgentes
- Personas y andenes que incorporan personas
- Manejo de que se hace cuando un vm ya llego a la estacion
- Manejo de eleccion de arbol de aceleracion
- ~~problema desface optimo andenes de la misma estacion~~
- ~~Agregar mas vm (en tiempo de simulacion)~~
#### No tan Urgentes
- Matriz, estacion de origen, estacion de destino (Mostrar, Editar, Cumplir)
- Revisar por qeu se descordina la simulacion cuando aumento o disminuyo el tiempo de la simulacion


#### Problema de desface optimo
El problema es que la estacion tiene varios arboles de aceleracion de subida que tienen los mismos desplasamientos en "x" e "y" y diferente desplasamiento en z, a pesar de eso el profesor quiere que los vm llegen al mismo tiempo a la estacion arriba si es que parten al mismo tiempo en cada uno de los arboles. El problema se repite en la bajada, con la diferencia de que ya no parten en el mismo punto como en la subida si no que deben terminar en el mismo punto, considerando que si los vm se tiran de los arboles de aceleracion al mismo tiempo deben llegar al punto final en el mismo tiempo esto quiere decir que me pone como restriccion que todos los arboles deben tener la misma longitud (400.5 metros) a pesar del desplasamiento, y todo debe cuadrar bien.

#### Opciones
- Podemos regular el largo del trak que conecta los arboles arriba de la estacion
- Podemos regular la velocidad del trak que esta en la estacion para que valla mas rapido o mas lento
- No quiero que los vm no conisderen el desplasamiento en z por que despues se que lo voy a tener que cambiar
- si hacemos que los arboles se conecten con el trak de abajo en distintos puntos
    - este punto tiene la desventaja de que dificulta enrmemente la eleccion de arbol cuando un vm  debe decidir entre continuar por la ruta o subir por algun arbol (a lo mejor solo lo puedo hacer para los arboles de bajada para evitar ese problema, pero tendria que hacer muchos station connector por que son muchos nodos)
    - no me gusta mucho esta alnativa por las dificultades
- Puedo agregar roce o aceleracion de manera artificial en los arboles con caminos mas largos


#### Conclucion del problema
##### supuestos
- Arboles de subida parten del mismo nodo, terminan en la estacion y = 0, z = variable (andenes)
- Arboles de bajada parten de distintos puntos (andenes distinto z), llegan al mismo nodo al terminar
- Arboles tienen mismo largo, misma mi aceleracion
- Se considera que cuando un vm termina un arbol de subida llego a la estacion
- cuando un vm comienza un arbol de bajada salio de la estacion
##### Ajustes
- Los station connector en las estaciones (conectan arbol de bajada y de subida) y = 0 van a tener
    - Distintos largos ya que algunos arboles de aceleracion van a terminar o empezar antes o despues (para respetar el largo de cada uno)
    - Van a tener diferentes velocidades para asegurar que todo vm que suba a las estaciones por distintos arboles, llege a la parte de arriba al mismo tiempo y baje por su arbol correspondiente al mismo tiempo
##### Calculos
- Se debe calcular cual es la velocidad variable que debe tener el station conector para asegurar que los vm llegen al mismo tiempo al arbol de bajada
- Cual es el largo que debe tener para permitir que un arbol de subida y de bajada pueda partir antes o despues
##### Evaluar
- La velocidad variante de los station connector en la estacion no puede ser muy diferente a 0.5 metros/segundo para que la gente sea capaz de subir y no alterar la capacidad de la estacion calculada

- No fueron mas de 15 centimetros los modificados



# preg

Preguntas de la implementacion;
por que en lane los andenes son deentry or exit?, quiero que la gente se pueda subir y bajar en el mismo anen o no?

por que en modular vehicles no eliminas sefl.passengers si ya tienes self.passengers_info, estaba hecho para que fuera facil la actualizacion

los passengers deben estar llamados en briainpara poder gnerarlos

la generacion aleatorea de pasageros esta bien en el lugar donde esta o es mejor que este en otro lugar para que se manejen mejor las responsabilidades, pensando en algo parecido a lo que se hace con los vms



