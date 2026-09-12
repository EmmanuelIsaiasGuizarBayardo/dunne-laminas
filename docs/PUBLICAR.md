> **Estado:** el repositorio ya existe y el sitio está publicado en
> <https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/>. Esta guía queda como referencia para republicar, migrar de
> dominio o crear el sitio de un modelo nuevo.

# Publicar Neurona AR en un repositorio propio

Guía para llevar la neurona a un repositorio nuevo bajo
`github.com/EmmanuelIsaiasGuizarBayardo` y dejar la realidad aumentada
funcionando.

Antes de los comandos hay una decisión que determina todo lo demás, así que
va primero.

---

## 1. Qué repositorio crear

La URL final depende del tipo de repositorio, y esa URL se propaga a cuatro
lugares: las etiquetas `canonical` y Open Graph del HTML, el QR impreso, los
enlaces que se compartan en talleres, y cualquier material ya distribuido.
Conviene decidirlo una sola vez.

### Las tres opciones

**a) Sitio de usuario.** Repositorio llamado exactamente
`EmmanuelIsaiasGuizarBayardo.github.io`, publicado en
`https://emmanuelisaiasguizarbayardo.github.io`. Solo puede haber uno por
cuenta, y ese dominio es el mejor lugar para tu página personal con tu CV, tu
tesis y tus publicaciones. **Recomiendo no gastarlo en este proyecto.**

**b) Repositorio de proyecto.** Por ejemplo `dunne-neurona`, publicado en
`https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/`. Es la opción
inmediata y la que sugiero para hoy. El nombre en plural deja lugar a las
modelos que vengan después: la página ya está parametrizada por un bloque de
configuración, así que agregar un modelo nuevo es duplicar una carpeta.

**c) Organización de DUNNE.** Una organización de GitHub, por ejemplo
`DUNNE-UNAM`, con el proyecto en `https://dunne-unam.github.io/neurona/`. Es
lo correcto a mediano plazo por una razón que no es técnica: **el proyecto
deja de vivir bajo una cuenta personal y sobrevive al cambio de mesa
directiva.** Hoy la landing está en la cuenta de Mauricio y por eso hay que
migrarla; si queda en la tuya, en dos años alguien repetirá esta misma
migración. Crear la organización es gratis y toma diez minutos.

### Un argumento medible: la densidad del QR

La longitud de la URL determina cuántos módulos tiene el código, y con ello
qué tan fácil es leerlo proyectado o impreso en pequeño. Con corrección de
errores nivel H:

| URL | caracteres | módulos |
|---|---|---|
| `https://dunne.unam.mx` (dominio propio) | 21 | 29² |
| `https://dunne-unam.github.io/neurona/` | 37 | 37² |
| `https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/` | 57 | 41² |
| `https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/` | 60 | 45² |

De 29² a 45² son módulos casi la mitad de grandes al mismo tamaño impreso.
Para un taller en Universum, donde el código se escanea de lejos y con luz
irregular, eso se nota. No es razón para bloquear la publicación de hoy, pero
sí para que la organización con nombre corto entre al plan.

**Mi recomendación:** crea hoy `dunne-neurona` bajo tu cuenta y publica; y por
separado, sin prisa, la organización `DUNNE-UNAM` como hogar definitivo. El
día que migres, el único cambio real es la URL en cuatro lugares y regenerar
el QR.

---

## 2. Crear el repositorio y publicar

En GitHub: **New repository**, nombre `dunne-neurona`, visibilidad pública,
sin README ni `.gitignore` iniciales para que el primer push no choque.

Los archivos van en la raíz, con esta estructura:

```
index.html
instrucciones.html
style.css
content.es.json
hotspots.json
PUBLICAR.md
assets/
  Neurona_v3.glb
  Neurona_v3.usdz
  poster.webp
  Dunne_oscuros.png
  qr_dunne.png
```

```bash
cd C:\ISAIAS\Procesamiento\Programas\Code\DUNNE\landing
git init
git branch -M main
git add .
git commit -m "Lamina 01: motoneurona en 3D y AR, con contenido didactico"
git remote add origin https://github.com/EmmanuelIsaiasGuizarBayardo/dunne-neurona.git
git push -u origin main
```

Luego, en el repositorio: **Settings → Pages → Source: Deploy from a branch →
Branch: `main` / `/ (root)` → Save.** La primera propagación tarda de uno a
dos minutos.

---

## 3. Cambiar la URL en el HTML

`index.html` tiene cuatro URLs absolutas apuntando al sitio anterior. Las
relativas (`./assets/…`) funcionan igual en un subdirectorio, así que solo hay
que cambiar esas cuatro. En PowerShell:

```powershell
$viejo = "https://mau897.github.io/"
$nuevo = "https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/"
(Get-Content index.html -Raw).Replace($viejo, $nuevo) | Set-Content index.html -NoNewline
```

Verifica que quedaron cuatro reemplazos: `canonical`, `og:url`, `og:image` y
`twitter:image`. Los dos últimos apuntan a `assets/poster.webp`, que es la
miniatura que aparece al compartir el enlace por WhatsApp.

**El enlace del APK es aparte.** Sigue apuntando a los *releases* del
repositorio de Mauricio y funciona sin cambios. Decide si el binario se queda
ahí, lo que mantiene la atribución donde está, o si se republica en el
repositorio nuevo para que el proyecto sea autocontenido. Si se republica,
aprovecha para nombrar el asset `NeuronaAR.apk` y cambiar el enlace a
`releases/latest/download/NeuronaAR.apk`; el comentario con la línea exacta ya
está en el HTML.

---

## 4. Regenerar el QR

El código actual codifica el sitio anterior, así que apunta al lugar
equivocado. Con el script incluido:

```bash
pip install segno
python make_qr.py --url "https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/" --output assets/qr_dunne.png
```

Usa corrección de errores nivel H, cerca de 30% de redundancia, porque el
código se imprime y se proyecta y en esas condiciones pierde contraste. El
script imprime la versión y el número de módulos para que puedas comprobar
que coincide con la tabla de arriba.

Después cambia la extensión en `index.html`, donde hoy dice `qr_dunne.jpg`, y
retira el JPG viejo del repositorio para que nadie lo imprima por error.

Si Mauricio está de acuerdo, vale la pena dejar en su sitio un `index.html`
mínimo con `<meta http-equiv="refresh" content="0; url=…">` hacia la URL
nueva, para que los códigos ya impresos sigan llevando a algún lado.

Y recuerda: **este QR no es el marcador de realidad aumentada.** Sirve para
compartir la página. El marcador de Vuforia sigue pendiente de rediseño,
porque un QR tiene patrón repetitivo y auto-similar, justo lo contrario de lo
que necesita el reconocimiento por características.

---

## 5. Por qué la AR exige HTTPS

Dos bloqueos independientes se acumulan:

- **WebXR**, que produce la AR dentro del navegador, solo existe en contexto
  seguro. En HTTP `navigator.xr` no está definido, y el diagnóstico de la
  página lo reporta como `WebXR: ausente`.
- **Scene Viewer**, la app del sistema a la que Android delega la AR cuando no
  hay WebXR, descarga el modelo por su cuenta y solo acepta URLs HTTPS. Una
  dirección de red local por HTTP produce `Could not load object` aunque el
  servidor responda 200.

En iOS ocurre lo equivalente con AR Quick Look.

Consecuencia práctica: **`python -m http.server` sirve para desarrollar el
visor 3D, nunca para probar AR.** GitHub Pages resuelve esto porque sirve por
HTTPS con certificado válido.

---

## 6. Verificar, en este orden

Cada paso descarta al anterior, así que conviene no saltárselos.

1. **Que los archivos existan.** Abre en el teléfono
   `…/dunne-neurona/assets/Neurona_v3.glb`. Debe descargar unos 2.3 MB. Si da
   404, el push no incluyó `assets/`.
2. **Que el visor cargue.** Entra a la página: primero aparece el póster y
   después el modelo girable.
3. **Que el diagnóstico esté limpio.** Abre *Diagnóstico* en la cabecera:
   - `contexto seguro: sí`
   - `modelo: cargado`
   - `WebXR: presente` en Android con ARCore instalado
   - `AR disponible: sí`
4. **Que la AR abra.** Toca *Verla en tu espacio*. Debe abrirse la cámara y
   pedir que apuntes al piso.

Si el paso 4 falla con el diagnóstico limpio, el siguiente sospechoso es el
tipo MIME.

---

## 7. Iterar sin publicar cada cambio

Un túnel entrega una URL HTTPS pública apuntando a tu servidor local:

```bash
python -m http.server 8000
cloudflared tunnel --url http://localhost:8000
```

Devuelve algo como `https://xxxx-yyyy.trycloudflare.com`, que sí funciona con
Scene Viewer y con Quick Look. `ngrok http 8000` es equivalente.

Alternativa sin salir de la red local: `mkcert` genera un certificado válido
para `192.168.x.x`, lo que da contexto seguro y habilita **WebXR**, es decir
AR dentro del navegador sin pasar por Scene Viewer. Requiere instalar la
autoridad certificadora local en el teléfono, así que conviene solo si van a
iterar mucho sobre AR.

---

## 8. Posible siguiente obstáculo: el tipo MIME del USDZ

GitHub Pages sirve las extensiones que no conoce como
`application/octet-stream` y **no permite configurar encabezados propios**.
Al `.glb` no le afecta, porque lo descarga el JavaScript del visor. Al `.usdz`
de iOS puede afectarle, porque AR Quick Look a veces exige
`model/vnd.usdz+zip`.

Si Android funciona y iPhone no, esa es la causa probable, y la salida es
alojar en un servicio que permita encabezados personalizados, como Netlify con
un archivo `_headers` o Cloudflare Pages. No vale la pena moverlo antes de
comprobar que hace falta.

---

## 9. Higiene del repositorio nuevo

Aprovecha que empieza limpio.

**LICENSE.** Falta y hace falta. Hay una pregunta previa que importa: el
patrón de exportación del modelo original sugiere que fue descargado y
convertido, no modelado desde cero. Si va a llevar el nombre de DUNNE en
Universum, la procedencia y su licencia deben quedar documentadas antes de
elegir la licencia del repositorio.

**CREDITS.md.** Modelo 3D y aplicación en Unity de Mauricio Mendiola Rivera;
limpieza del modelo, contenido didáctico y landing por separado. Las
referencias en APA 7 ya viven en `content.es.json`.

**`.gitignore` de Unity**, si algún día el proyecto de Unity se migra aquí:
`Library/`, `Temp/`, `Logs/`, `Obj/`, `Builds/`, `*.csproj`, `*.sln`. Y en ese
caso, Git LFS con el `.gitattributes` estándar de Unity, porque el proyecto
trae binarios que no deben versionarse línea por línea.

**El `.blend` y el `Neurona.obj`** conviene que vayan por Git LFS y no como
archivos de texto: el OBJ pesa 9.3 MB para la misma geometría que el GLB de
2.3 MB.

---

## Qué falta decidir

1. El nombre del repositorio, que fija la URL y con ella el QR.
2. Si el APK se queda en los *releases* de Mauricio o se republica aquí.
3. Si se crea la organización `DUNNE-UNAM` ahora o después.

Con el nombre confirmado puedo entregarte el `index.html` ya con las URLs
cambiadas y el QR nuevo generado, para que solo hagas el push.
