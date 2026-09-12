# Operación de la sala interactiva

Guía para quien monta la actividad. La documentación técnica está en el
`README.md` de la raíz.

---

## 1. Antes del evento

### Red

Casi todo wifi institucional trae **client isolation** activado, que bloquea
el tráfico entre dispositivos conectados al mismo punto de acceso. Con esa
opción activa ningún dispositivo alcanza al servidor, y el diagnóstico es
confuso porque todos los equipos tienen internet.

Usar un **router propio** en modo punto de acceso, sin depender de la red de
la sede. Verificar que el aislamiento de clientes esté desactivado.

### Laptop dedicada

Con laptop y router propios la dirección del servidor deja de cambiar, lo que
permite imprimir el código QR una sola vez.

1. SSID fijo en el router, por ejemplo `DUNNE-SALA`.
2. Reserva de DHCP para la MAC de la laptop, por ejemplo `192.168.4.10`.
3. Regla de firewall, una vez y como administrador:

   ```
   netsh advfirewall firewall add rule name="Sala DUNNE" dir=in action=allow protocol=TCP localport=8000
   ```

   Sin esta regla Windows bloquea las conexiones entrantes: en la laptop
   funciona y en los teléfonos no.
4. Código QR impreso con la ruta corta:

   ```bash
   python make_qr.py --url "http://192.168.4.10:8000/n" --output sala/qr_sala.png
   ```
5. Acceso directo a `arrancar.bat` en el escritorio.

### Tablets propias

Abrir `http://<ip>:8000/n` y añadir a la pantalla de inicio. Arranca sin barra
de direcciones y sin posibilidad de navegar fuera de la actividad.

---

## 2. Durante el evento

1. Encender el router y esperar que levante.
2. Ejecutar `arrancar.bat`.
3. Abrir `http://localhost:8000/m` en la laptop. Esa vista es el mural que se
   proyecta y la consola del operador.
4. Probar con un dispositivo propio antes de recibir público.

### Verificación en orden

Cada paso descarta el anterior.

1. En la laptop, `http://localhost:8000/n` muestra el modelo y el trazo en
   movimiento.
2. En un teléfono en el mismo wifi, la dirección IP carga la misma página. Si
   falla aquí, el problema es la red.
3. Con dos dispositivos, dos estímulos seguidos en el primero lo hacen
   disparar y el segundo registra la entrada.
4. Si el paso 3 falla y el 2 funciona, revisar el firewall.

---

## 3. Demostraciones

### Suma temporal

Un estímulo no alcanza el umbral. Dos seguidos sí, porque el segundo llega
antes de que el voltaje decaiga. Dos espaciados, no. Se observa en el trazo
del potencial de membrana.

### Suma espacial

Con topología de **convergencia**, varias neuronas apuntan a la misma. Una
sola presináptica no logra hacerla disparar; dos coordinadas, sí.

### Inhibición

Desde la consola, volver inhibitoria una de las presinápticas en convergencia.
Sus potenciales pasan a hiperpolarizar a la postsináptica en lugar de
acercarla al umbral, y cancelan a las excitatorias que llegan al mismo tiempo.

### Conducción saltatoria y desmielinización

Con mielina, el destello salta de vaina en vaina; el instante de cada salto
corresponde a la posición real de esa vaina sobre el axón. Al quitar la
mielina, las vainas se desaturan y la animación pasa a un barrido continuo un
orden de magnitud más lento. Es lo que mide un estudio de velocidad de
conducción nerviosa.

### Reverberación

Con topología de **anillo**, un solo estímulo puede sostener actividad que se
propaga indefinidamente por el circuito.

---

## 4. Ajustes según el público

| control | uso |
|---|---|
| Topología `cadena` | primera aproximación, grupos infantiles |
| Topología `convergencia` | suma espacial e inhibición |
| Topología `anillo` | actividad autosostenida |
| Topología `divergencia` | una neurona con muchos blancos |
| Dilatación ×30 o ×50 | público infantil |
| Dilatación ×10 | licenciatura y posgrado |
| Reiniciar voltajes | entre grupos |

La dilatación temporal aparece siempre en el mural. Conviene mencionarla en la
explicación: lo que se observa está ralentizado respecto a la fisiología real.

---

## 5. Asientos

Se asignan por orden de conexión y se reutiliza el primero libre cuando
alguien se desconecta, para no dejar huecos en la cadena. Un dispositivo puede
solicitar un asiento concreto con `?seat=3` en la URL, útil para las pantallas
fijas que deben ocupar siempre la misma posición del circuito.
