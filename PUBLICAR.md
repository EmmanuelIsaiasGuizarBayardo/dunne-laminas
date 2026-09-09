# Publicar Neurona AR

La realidad aumentada solo funciona sobre HTTPS. Este documento es la ruta
más corta para tenerla andando y para verificar que quedó bien.

## Por qué HTTPS no es negociable

Dos bloqueos independientes se acumulan:

- **WebXR**, que produce la AR dentro del navegador, solo existe en contexto
  seguro. En HTTP `navigator.xr` no está definido.
- **Scene Viewer**, la app del sistema a la que Android delega la AR cuando no
  hay WebXR, descarga el modelo por su cuenta y solo acepta URLs HTTPS. Una
  dirección de red local por HTTP produce el error `Could not load object`
  aunque el servidor responda 200.

En iOS pasa lo equivalente con AR Quick Look.

Consecuencia práctica: **`python -m http.server` sirve para desarrollar el
visor 3D, nunca para probar AR.**

## 1. Publicar

Los archivos van en la raíz del repositorio, con esta estructura:

```
index.html
instrucciones.html
style.css
content.es.json
hotspots.json
assets/
  Neurona_v3.glb
  Neurona_v3.usdz
  poster.webp
  Dunne_oscuros.png
  qr_dunne.jpg
```

```bash
git add index.html instrucciones.html style.css content.es.json hotspots.json assets
git commit -m "Landing con visor 3D y AR: modelo limpio y paleta didactica"
git push origin main
```

GitHub Pages tarda de uno a dos minutos en propagar. Si el repositorio se
llama `Mau897.github.io`, el sitio queda en `https://mau897.github.io`.

## 2. Verificar, en este orden

1. **Que los archivos existan.** Abre en el teléfono
   `https://mau897.github.io/assets/Neurona_v3.glb`. Debe descargar unos
   2.3 MB. Si da 404, el push no incluyó `assets/`.
2. **Que el visor cargue.** Entra a la página. Debe aparecer primero el
   póster y luego el modelo girable.
3. **Que el diagnóstico esté limpio.** Abre *Diagnóstico* en la cabecera y
   confirma:
   - `contexto seguro: sí`
   - `modelo: cargado`
   - `WebXR: presente` en Android con ARCore instalado
   - `AR disponible: sí`
4. **Que la AR abra.** Toca *Verla en tu espacio*. Debe abrirse la cámara y
   pedirte apuntar al piso.

Si el paso 4 falla con el diagnóstico limpio, el siguiente sospechoso es el
tipo MIME (ver abajo).

## 3. Iterar sin publicar cada vez

Un túnel entrega una URL HTTPS pública apuntando a tu servidor local:

```bash
python -m http.server 8000
cloudflared tunnel --url http://localhost:8000
```

Devuelve algo como `https://xxxx-yyyy.trycloudflare.com`. Esa URL sí funciona
con Scene Viewer y con Quick Look. `ngrok http 8000` es equivalente.

Alternativa sin salir de la red local: `mkcert` genera un certificado válido
para `192.168.x.x`, lo que da contexto seguro y habilita **WebXR**, es decir
AR dentro del navegador sin pasar por Scene Viewer. Requiere instalar la
autoridad certificadora local en el teléfono, así que conviene solo si van a
iterar mucho sobre AR.

## Posible siguiente obstáculo: el tipo MIME del USDZ

GitHub Pages sirve las extensiones que no conoce como
`application/octet-stream` y **no permite configurar encabezados propios**.
Para el `.glb` no importa, porque lo descarga el propio JavaScript del visor.
Para el `.usdz` de iOS puede importar: AR Quick Look a veces exige
`model/vnd.usdz+zip`.

Si en iPhone la AR no abre pero en Android sí, esa es la causa probable, y la
salida es alojar en un servicio que permita encabezados personalizados
(Netlify con un archivo `_headers`, o Cloudflare Pages) manteniendo el
dominio actual como redirección. No vale la pena moverlo antes de comprobar
que hace falta.

## Pendientes que no bloquean la publicación

- Estandarizar el nombre del asset del APK a `NeuronaAR.apk` y cambiar el
  enlace del HTML a `releases/latest/download/NeuronaAR.apk`, para no editar
  la página en cada release. El comentario con la línea exacta ya está en
  `index.html`.
- Publicar la suma `shasum -a 256` del APK en la página del release.
- Rediseñar el marcador de Vuforia como imagen aparte del QR.
