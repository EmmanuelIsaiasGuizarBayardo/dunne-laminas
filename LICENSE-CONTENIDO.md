# Licencia del contenido y de los modelos

El código de este repositorio se distribuye bajo la licencia MIT (ver
`LICENSE`). Este archivo cubre lo que **no** es código.

## Qué cubre

- El modelo 3D de la motoneurona en todas sus variantes:
  `assets/Neurona_v3.glb`, `assets/Neurona_v3.usdz`,
  `sala/assets/Neurona_sala.glb` y cualquier derivado.
- El contenido didáctico de `content.es.json`, incluidos los textos que ve el
  público y los dirigidos a quien imparte el taller.
- El documento `docs/Revision_academica_Neurona_AR.docx`.
- Las imágenes generadas del modelo: `assets/poster.webp`,
  `docs/social-preview.png`.

Queda fuera el logotipo de DUNNE (`assets/Dunne_oscuros.png`, `icon-192.png`,
`icon-512.png`), que es un identificador de la organización. Puede
reproducirse al citar o redistribuir el proyecto, pero no para identificar
trabajos derivados ni para dar a entender que DUNNE respalda un derivado.

## Bajo qué términos

**Creative Commons Atribución 4.0 Internacional (CC BY 4.0).**

Texto legal completo: <https://creativecommons.org/licenses/by/4.0/legalcode.es>
Resumen: <https://creativecommons.org/licenses/by/4.0/deed.es>

Cualquier persona puede compartir y adaptar este material, con cualquier
finalidad, incluso comercial, siempre que otorgue el crédito correspondiente,
enlace a la licencia e indique si realizó cambios.

## Cómo dar el crédito

Al reutilizar el modelo o el contenido, incluir una nota como esta:

> Modelo 3D de motoneurona: Mauricio Mendiola Rivera. Contenido didáctico y
> aplicaciones: Emmanuel Isaías Guízar Bayardo. División Universitaria de
> Neuroingeniería (DUNNE), UNAM. Proyecto Neurona AR, bajo CC BY 4.0.
> https://emmanuelisaiasguizarbayardo.github.io/dunne-neurona/

Si se realizaron modificaciones, indicarlo: *"adaptado de"* en lugar de *"por"*.

## Procedencia del modelo

El modelo 3D de la motoneurona fue creado desde cero por **Mauricio Mendiola
Rivera**, quien cedió los derechos de uso, modificación y distribución a la
División Universitaria de Neuroingeniería. No incorpora geometría de terceros,
por lo que la organización puede escalarlo, modificarlo y redistribuirlo sin
restricciones heredadas.

Las variantes que hay en el repositorio son transformaciones automatizadas de
ese original, producidas por los scripts de `tools/`.

## Contenido académico

El contenido didáctico cita fuentes en formato APA 7. Las referencias remiten
a obras de terceros que conservan sus propios derechos: se citan, no se
reproducen. El campo `review.status` de `content.es.json` indica el estado de
la revisión académica del contenido en cada momento.

## Por qué esta combinación

Las licencias Creative Commons no son adecuadas para software, y las licencias
de software no están pensadas para obras creativas ni para textos. Separar
ambas es la práctica habitual en proyectos que, como este, contienen las dos
cosas.

Se eligió CC BY antes que CC BY-SA porque la cláusula de compartir igual
obligaría a cualquier material que incorpore el modelo a adoptar esta misma
licencia, lo que impediría a un museo o a otra universidad incluirlo en
materiales con licencias distintas. Se descartó CC BY-NC porque la restricción
no comercial excluye usos legítimos, como un taller de paga o un libro de
texto, y es incompatible con la mayoría de las licencias abiertas.

En ambos casos la atribución es obligatoria, que era el requisito de fondo.
