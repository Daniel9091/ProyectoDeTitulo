### Comandos Utililes:
#### Activar el ambiente venv:
```bash
source venv/bin/activate
```
#### Dependencias del proyecto
Una vez que se halla activado el abiente
```bash
pip install -r requirements.txt
```
#### Iniciar la simulacion:
```bash
python3 -m simulation.main
```



### Apuntes

Hola tengo que pregutarte un par de cosas para continuar la refractorisacion.

Me di cuenta que el puto de test essta muy cerca del comienzo del arbol de desaselaracion (entrada de la estacion)

Hasta ahota en la similacion se puede dar el caso de que que halla una colicion inevitable, producida por que el tren continuo esta muy denso por lo tanto aunque se busque hacia atras o hacia adeltante no se encuenntra un espacio disponible para que un vm se inserte.

Haora quiero encargarme de dos refatrorisaciones, la primera es para que el calculo que predice coliciones se haga cuando el vm ingresas a la lane de la estacion. este cambio va a hacer que el putno donde se esta mirando para predecir las coliciones retroseda hasta antes de la union entre el tren continuo y la propia estacion.
La segunda refactorisacion va ser un sistema que evite las coliciones inevitables. lo que va a ahser para evitarlas es que si hay alguna colicion inevitable  va a decirle a la estacion que debe sacar un vm en el rango de slots para cuando un vm se quiere incorporar.

para eplicarlo mejor si una colicion es inevitale como el putno que esta mirando va a estar antes de la entrada al arbol de aceleracion de la estacion va a mandar a la estacion a sacar un vm que esta en el punto de mira o proximo a (dentro del rango de slots que se pueden revisar) y de esta manera al estacion se va a generar el espacio neesesario para evitar una colision inevitable.

algunas reglas de funcionameinteo para esta refactorisacion son:
hay que evitar a toda costa los choques inevitables ya que es lo mas peligroso
de ser posible la estacion debe evitar vms que  tengan pasageros  y vallan a otra estacion para no hacer que la gente pierda el tiempo pasando por otra estacion
la estacion tiene un contador de cuantos vms debe consumir por unidad de tiempo, cuanodo un vm entra a la estacion debe contar en el conteo de vms por unidad de tiempo (puedes dar la alternativa de que este en negativo)
hay que revisaar el caso en el que el puto de testo o de vista para ver el posible choquee este entre estaciones o este entre arboles de aceleracion de otra estacion por que  en tal caso podiramos ver solo slots reservados  por vms que bienen de la estacion  anterior, en tal caso se debe saber como manerjar el caso (se debe pedir un vm que todavia ño ha llegadoa al tren continuo a la estacion? esto afectaria al usuario, o nos limitamos a pedir vms que estan en el tren continuo? yo  creo que podriamos pobar con esta primera opcion por que las estaciones no tienen capacidad para consumir tantos vms al mismo tiempo y estos problemas solo se dan cuanto todo esta muy denso en esta situaacion puedes tierar un choque inevitable par  reevisar el caso (en el caso de que choque por que no tenia vms que podia pedir del tren continuo))

de todas maneras la funiconalidad de choqeu inevitable aunque se qeuiera evitar a toda costa queiro que la dejes implementaa por que de esta manera puedo ver los bugus que vallan ocurriendo entre medio y puedo aprender como solucionarlos

como refactorisaciones  extras adjuntas al problema pero que pueden solucionar de apoco, es que si se 
preugnta por una colicion justo cuanod se entra a un anden entonces el putno de test TZ debe calcularse calculando la demora del vm en la lane

en esta primera interaccion que tenogo contigo quiero que comberzemos del tema, me comentes si estoy pensando bien las cosas, como podrias realizar la refactorisacion teines que actuar como un experto en simulaciones en general y sobre todo experto en esta simulacion por lo msimo debes leer el codigo (o las partes que te sirban para poder entender esto que te digo)
quiero que me invites a pensar y reflexionar respecto a como  puedo abordar el problema etc. que partes crees que le estan faltando a la logica que te estoy comentando que cosas se  me pasaron comentarte etc



## Apuntes 2
Muy bien ahora continuemos con la refactorisacion 2
respondiendo a las preguntas, efectivamente el puto tz queda entre los arboles de la estacion pasada asiq eu se debe reservar un slot incluso antes de que el tren continuo este completo.
lo que no se es que si para ese punto que esta revisando es si llegara a estar reservado por la estacion anterior el vm que le corresponderia a ese espacio ya paso por al lane ya se subieron los pasageros.
esta pregunta es importante por que no quiero llamar a un vm que tenga pasageros
el funionamiento de este sistema va a ser de la siguiente manera.

todo vm que quiera ingresar al tran continuo debera tener una reserva a un slot vacio o a un slot con otro vm (colision inevitable)
la reserva de este slot se realizara cuando u vm ingrese a la lane, calculando el tiempo que se demora en recorrer la lane y el tiempo que se demore en recorrer el arbol de aceleracion, en este mismo lugar debera ajustar la aceleracion exacta para que llegue al tren continuo de manera fluida.
una vez que comprueba el espacio donde deberia llegar el vm en condiciones normales se deben ejecutar las reglas que establecimos previamente.
1. si no esta ocupado ni reservado lo reserva y llega a ese slot
2. si esta reservado o ocupado o con gente revisa para atras o adelante segun el rango descrito
3. en caso de que todos en el rango esten en con alguna condicion que puese en el punto anterior se priorisa los que estan ocupados, debe marcarse para que la estacion lo consuma a el,  para dejar un espacio para que el vm pueda reservar ese espacio.
4. si el vm estaba reservado (revise en todo el rango establecido) por la estacion anterior, debe revisar si la reserva es de un vm sin pasageros, si este esta sin pasageros se priorisa pedir este vm para que sea consumido por la siguiete estacion (el vm bajara por el arbol de aceleracion anterior al reservado, estara en el tren continuo, y luego sera consumido por la estacion siguiente)
5. por ultimo se solicitara el consumo de un vm que este con pasageros antes que una colision inevitable.
- se debe considerar que el vm pueda ser consumido por la estacion tomando en consideracion las restricciones del consumo por cada uno del los arboles de desaseleracion
- se debe tener en consideracion que cada vm que llega a la estacion debe pasar por la etapa de abordaje para que peuda subirse la gente.
- en los logs de lao vms se debe mostrar la cantidad de pasageros abordo