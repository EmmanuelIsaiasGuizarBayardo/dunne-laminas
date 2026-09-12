# Neurona AR · DUNNE

Material didáctico interactivo de la División Universitaria de Neuroingeniería
(DUNNE), Facultad de Medicina, UNAM.

Sitio publicado: <https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/>
Repositorio: `EmmanuelIsaiasGuizarBayardo/dunne-neurona`

El repositorio contiene dos aplicaciones que comparten el mismo modelo 3D y el
mismo contenido didáctico:

| | **Neurona** | **Sala** |
|---|---|---|
| Qué es | Visor 3D y realidad aumentada de una motoneurona | Red de neuronas distribuida entre varios dispositivos |
| Despliegue | Sitio estático en GitHub Pages | Servidor local en una laptop |
| Origen | HTTPS | HTTP en red local |
| Público | Cualquier persona con un navegador | Asistentes a un taller, en el mismo wifi |
| Entrada | `index.html` | `sala/server.py` |

---

## 1. Arquitectura

### 1.1 Neurona (sitio estático)

```
index.html            visor, cédulas de contenido y ventanas modales
instrucciones.html    manual de instalación y uso
style.css             hoja única del visor
content.es.json       contenido didáctico con referencias en APA 7
hotspots.json         anclajes 3D de cada estructura sobre el modelo
manifest.webmanifest  instalable; abre sin barra de direcciones
assets/
  Neurona_v3.glb      modelo con un material por clase anatómica
  Neurona_v3.usdz     equivalente en USD para AR Quick Look en iOS
  poster.webp         imagen previa y miniatura de Open Graph
  icon-192.png        iconos del manifiesto
  icon-512.png
```

No hay compilación ni dependencias de instalación: es HTML, CSS y un módulo de
JavaScript. `<model-viewer>` se carga desde un CDN con versión fija.

La configuración específica del modelo vive en un bloque
`<script type="application/json" id="exhibit">` al inicio de `index.html`. Para
publicar otro modelo se duplica la página y se cambian esas rutas; el resto del
código no contiene nada específico de la neurona.

### 1.2 Sala (servidor local)

```
sala/
  server.py           HTTP y WebSocket en un solo puerto, sin dependencias
  neurona.html        cliente: un dispositivo es una neurona
  mural.html          pantalla grande y consola del operador
  sala.css            hoja única de la sala
  propagacion.json    posición normalizada de cada estructura sobre el axón
  test_sala.py        suite de integración
  arrancar.bat        lanzador para Windows
  assets/
    Neurona_sala.glb  modelo con un material por malla
```

El servidor mantiene la topología del circuito, recibe los potenciales de
acción que dispara cada dispositivo y los entrega a sus neuronas
postsinápticas con un retardo de conducción calculado a partir de parámetros
físicos.

El protocolo WebSocket está implementado sobre la biblioteca estándar de
Python. No requiere `pip install`.

### 1.3 Decisión de transporte

El visor se sirve por HTTPS porque la realidad aumentada lo exige: WebXR solo
existe en contexto seguro y Scene Viewer, la aplicación del sistema a la que
Android delega la AR, únicamente acepta URLs HTTPS.

La sala se sirve por HTTP porque una página HTTPS no puede abrir un WebSocket
`ws://` (el navegador lo bloquea como contenido mixto activo) y `wss://`
requeriría instalar una autoridad certificadora en cada dispositivo del
público. En la sala no se usa la cámara, por lo que el contexto seguro no es
necesario y la página y el socket comparten origen en HTTP.

Consecuencia práctica para quien desarrolla: **la AR no se puede probar con un
servidor HTTP local.** Hay que publicar en GitHub Pages o usar un túnel HTTPS
(`cloudflared tunnel --url http://localhost:8000`).

---

## 2. Puesta en marcha

### 2.1 Neurona

Cualquier servidor estático. `fetch` de los archivos JSON y del modelo falla
sobre `file://`, por lo que abrir el HTML con doble clic no funciona.

```bash
python -m http.server 8000
# http://localhost:8000
```

Publicación: GitHub Pages sobre `main`, directorio raíz. Al cambiar de dominio
hay que actualizar cuatro URLs absolutas en `index.html` (`canonical`,
`og:url`, `og:image`, `twitter:image`) y regenerar el código QR.

### 2.2 Sala

```bash
cd sala
python server.py
```

En Windows, `arrancar.bat` verifica Python, los archivos, la regla de firewall
y las direcciones IP antes de levantar el servidor.

Opciones:

```bash
python server.py --port 8000 --host 0.0.0.0 --topology convergencia --dilation 30
```

Rutas: `/n` es alias de `neurona.html` y `/m` de `mural.html`. Existen para
acortar la URL que se codifica en el QR impreso.

---

## 3. Pruebas

```bash
cd sala
pip install websockets     # solo para las pruebas
python test_sala.py
```

Veintisiete verificaciones de integración: asignación y reutilización de
asientos, aristas de cada topología, entrega del spike únicamente a las
neuronas postsinápticas, retardo de conducción con y sin mielina, polaridad
inhibitoria con peso negativo, propagación del voltaje solo a los murales,
cada control de la consola del operador, alias de ruta, baja de clientes y
convivencia de HTTP con WebSocket en el mismo puerto.

La suite usa la biblioteca `websockets` como cliente para que la
implementación del protocolo se valide contra una independiente. El servidor
no la necesita en producción.

---

## 4. Protocolo de la sala

WebSocket en `/ws`, mensajes JSON. Compatible con `WebSocketsClient` de ESP32
y puenteable a MQTT sin modificar el esquema.

Parámetros de conexión: `/ws?role=mural` para una pantalla de monitoreo,
`/ws?seat=3` para solicitar un asiento concreto.

### Cliente al servidor

| mensaje | efecto |
|---|---|
| `{"type":"spike"}` | dispara un potencial de acción hacia las postsinápticas |
| `{"type":"vm","v":-62.4}` | reporta el voltaje actual; se propaga solo a los murales |
| `{"type":"myelin","on":false}` | activa o desactiva la mielina de esa neurona |
| `{"type":"polarity","kind":"inhibitory"}` | cambia la polaridad; desde un mural admite `"seat"` |
| `{"type":"config","topology":"anillo","dilation":30}` | cambia la configuración global |
| `{"type":"reset"}` | reinicia el voltaje de todas las neuronas |

### Servidor al cliente

| mensaje | contenido |
|---|---|
| `welcome` | `id`, `seat`, `polarity`, `config`, `targets` |
| `targets` | destinos actualizados; se reenvía en cada cambio del censo |
| `input` | `from_seat`, `weight` (negativo si es inhibitorio), `delay_ms` |
| `roster` | `neurons`, `edges`, `config` |
| `event` | spike observado: `seat`, `targets`, `delay_ms`, `polarity` |
| `vm` | voltaje de un asiento; solo a los murales |

---

## 5. Modelo computacional

Cada dispositivo ejecuta un integrate-and-fire con fuga en unidades reales:

```
τ_m · dV/dt = -(V - V_rest) + R·I(t)
```

| parámetro | valor |
|---|---|
| potencial de reposo | −70 mV |
| umbral | −55 mV |
| potencial de reinicio | −75 mV |
| piso de hiperpolarización | −85 mV |
| constante de membrana | 20 ms |
| periodo refractario | 5 ms |
| peso sináptico | 0.6 de la distancia reposo-umbral |

El peso de 0.6 implica que se requieren dos entradas coincidentes para
alcanzar el umbral.

La polaridad es una propiedad de la neurona y no de la sinapsis, conforme al
principio de Dale: una neurona libera el mismo neurotransmisor en todos sus
terminales, por lo que su efecto es excitatorio o inhibitorio, nunca mixto.

**Dilatación temporal.** A escala real el potencial de acción recorre la sala
en menos de un milisegundo. Con el factor por omisión de 20, la constante de
membrana equivale a 400 ms de reloj de pared. Los clientes muestran el factor
en pantalla; cualquier cambio en ese comportamiento debe mantener la
declaración visible.

**Conducción.** El retardo es longitud del axón entre velocidad, multiplicado
por el factor de dilatación. Con mielina, 60 m/s; sin mielina, 6 m/s. La
animación cambia de saltatoria a continua en consecuencia, y los instantes de
cada salto se derivan de `propagacion.json`, calculado desde las coordenadas
reales del modelo.

---

## 6. Regeneración de los activos

Los modelos y los archivos de datos se generan con scripts, no a mano. El
modelo original no se modifica en ningún paso.

```bash
# 1. Limpieza: renombra por clase anatómica, hornea transformaciones,
#    colapsa materiales y elimina texturas y extensiones sin uso
python clean_glb.py --input Neurona.glb --mapping mapping.json \
    --output Neurona_v2.glb --report reporte_limpieza.json

# 2. Paleta didáctica por clase (neurona)
python bake_palette.py --input Neurona_v2.glb --output assets/Neurona_v3.glb

# 3. Paleta con un material por malla (sala; permite animar cada vaina)
python bake_palette.py --input Neurona_v2.glb \
    --output sala/assets/Neurona_sala.glb --per-instance

# 4. USDZ para AR Quick Look en iOS
python gltf_to_usdz.py --input assets/Neurona_v3.glb --output assets/Neurona_v3.usdz

# 5. Código QR de enlace
python make_qr.py --url "https://<dominio>/" --output assets/qr_dunne.png
```

`etiquetador_neurona.html` es la herramienta con la que se produjo
`mapping.json`: carga un GLB, permite asignar la clase anatómica de cada malla
y exporta el mapeo. Solo hace falta si se incorpora un modelo nuevo.

Dependencias de los scripts: `numpy`, `pygltflib`, `usd-core`, `segno`.
Ninguna es necesaria para ejecutar las aplicaciones.

---

## 7. Contenido didáctico

`content.es.json` es la única fuente del texto que se muestra al público. La
interfaz no contiene texto de contenido en el marcado.

Campos por estructura:

| campo | destino |
|---|---|
| `short` | se muestra al tocar la estructura |
| `long` | panel de más información |
| `analogy` | solo personal; guía para explicar en el taller |
| `misconception` | solo personal; error frecuente por desactivar |
| `geometry_note` | solo personal; límite del modelo 3D |
| `references` | claves del diccionario `references` de la raíz, en APA 7 |

Los campos marcados como solo personal se revelan con el **modo staff**: cinco
toques rápidos sobre el logo, o `?staff=1` en la URL.

`review.status` indica si el contenido cuenta con revisión académica. El
documento `Revision_academica_Neurona_AR.docx` se genera desde este mismo JSON
para que no puedan divergir.

---

## 8. Convenciones

**Código.** Python con anotaciones de tipo y docstrings en formato NumPy.
JavaScript en módulos ES, sin empaquetador. Nombres de identificadores en
inglés; comentarios en español, reservados para lo que el código no dice por
sí mismo.

**Identificadores.** Las claves de `content.es.json`, `mapping.json` y
`hotspots.json` son ASCII sin diacríticos. Las etiquetas visibles llevan
acentuación normal. No aplicar correcciones ortográficas automáticas sobre
archivos de datos: modifican identificadores y títulos de referencias en
inglés.

**Binarios.** Los modelos viven en `assets/`. Un archivo `.blend` o `.obj`
debe incorporarse con Git LFS, no como texto versionado línea por línea.

**Dos hojas de estilo.** `style.css` y `sala/sala.css` comparten los tokens de
color y tipografía pero se mantienen independientes: son dos aplicaciones con
ciclos de vida distintos y no deben acoplarse.

---

## 9. Cómo contribuir

1. Haz un fork y crea una rama descriptiva: `sala/registro-de-sesion`,
   `lamina/marcador-vuforia`.
2. Si el cambio toca `sala/`, ejecuta `python test_sala.py` antes de abrir el
   pull request y añade una verificación si introduces un mensaje nuevo en el
   protocolo.
3. Si el cambio toca el contenido, edita `content.es.json` y regenera el
   documento de revisión. El contenido nuevo no se publica frente a público
   sin visto bueno académico.
4. Si el cambio toca un modelo, modifica el script que lo genera y vuelve a
   ejecutarlo. No edites un `.glb` a mano.
5. Describe en el pull request cómo se probó, en qué navegador y en qué
   dispositivo.

---

## 10. Documentación adicional

| archivo | contenido |
|---|---|
| `docs/operacion.md` | guía de sala: red, firewall, laptop dedicada, lista de verificación |
| `docs/PUBLICAR.md` | publicación del sitio y migración de dominio |
| `instrucciones.html` | manual de uso para el público |
| `Revision_academica_Neurona_AR.docx` | contenido para revisión por especialista |

---

## 11. Estado y pendientes

- Marcador de Vuforia rediseñado como imagen independiente del código QR. Un
  QR es un mal *Image Target*: su patrón es repetitivo y auto-similar.
- Cono axónico, nodos de Ranvier y espinas dendríticas como geometría
  independiente. Hoy no existen como mallas separadas en el modelo.
- Registro de sesión en la sala, para mostrar el raster plot al cierre.
- ESP32 como neurona física. El protocolo ya lo admite.
- Revisión académica del contenido firmada.

---

## Créditos

Modelo 3D y aplicación en Unity: Mauricio Mendiola Rivera.
Limpieza del modelo, contenido didáctico, neurona web y sala interactiva:
División Universitaria de Neuroingeniería, UNAM.

El modelo representa una motoneurona somática: soma y dendritas en la médula
espinal, axón en un nervio periférico mielinizado por células de Schwann.

Pendiente de definir: licencia del repositorio y procedencia documentada del
modelo 3D original.
