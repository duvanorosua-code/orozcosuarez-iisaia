# Prompts — TP 1

El registro del proceso, en orden. Dos prompts en una sola conversación de Gemini Canvas. El artefacto quedó terminado en el segundo.

---

## 1 — Prompt inicial

```
Vamos a realizar una interfaz que funcione y genere un reproducto de musica que la distribución y funcionalidad va a ser la siguiente:

Estructura:
- <header> Agregar titulo "Reproductor de Musica" y el nombre de la siguiente canción.
- <main> En el tablero: La foto de la canción en el centro conel nombre de la cancion debajo de ella en forma de anagrama, cada letra en una caja (Nombre de la cancion de ejemplo "la cancion").
- <footer> de lo anterior, un <button> "Anterior" , un   <button> "Siguiente" y por ultimo otro <button> "Play/Stop".

Estilo:
- Estética de captcha viejo: fondo amarillo, centrados los elementos sin margen superior e inferior pero centrado, y con margen de los laterales y letra negra.
-Color verde en las letras del anagrama cuando estén en el lugar correcto, en el caso contrario se encuentren en rojo.

Comportamiento:
- Estado: objetivo order correcto anagrama (ejemplo "la cancion"),
cambiando de color mientras se reinicia la configuracion.
- Al mover una letra se intercambia de lugar con la otra y se colorea de acuerdo si esta en la posición correcta o no.
- Al terminar de colocar todas las letras en la posición correcta puedo oprimir uno de los tres botones, esto vuelve a reorganizar el anagrama en una posición aleatoria nuevamente si el usuario quiere darle a otro boton.
- Realizar cambio de acuerdo al resultado anterior con otro ejemplo la segunda canción se llama (El cantante).

Constraints:
- Un solo archivo HTML, con el CSS en un <style> y el JS en un <script>.
- Vanilla JS, sin frameworks ni dependencias externas.
- Los botones son elementos del DOM posicionados con CSS. No usar <canvas>: quiero poder ver el estado reflejado en el DOM.  

```

**Qué intentaba lograr:** el reproductor de musica con las 5 capas de una vez para que fuera funcional.

**Qué devolvió:** eel reproducto funcionalidad con unos pequeñs cambios en el diseño que tocaba arreglar y un cambio en un evento de elementos del DOM en lugar de `<canvas>`.

**Qué hice con eso:** lo acepté. Pero el prompt me falto ser mas claro sobre el diseño a pesar de que queria que fuera incomodo quedo mas complicado de lo que pretendia.

---

## 2 — Iterar sobre el estado: reordenar las canaletas

```
Agregale las siguientes indicaciones quiero que en la parte del <header> tambien tenga el nombre de la cancion actual para que lo pueda desarrollar mas facil el usuario, el angrama que se encuentra en <main> tenga un estilo display : flex para que no se genere en dos filas o como un grid, y por ultimo al cambiar el estado de intercambiar dos letras con clicks no se quede pegado la posicion que elegi al principio en el DOM.
```

**Qué intentaba lograr:** Que se generara el anagrama en una sola fila, y el usuario pudira saber qu eetsaba completando.

**Por qué está escrito así:** Para ser especifico sobre que habia quedado bien pero se necesitaba cambiar el diseño especificamente y como el DOM ejecutaba la seleccion de las letras.

**Qué devolvió:** El ajuste visual y el funcionamiento del DOM correctamente..

## Conversación completa

Una sola conversación de Gemini Canvas, sin reiniciar el hilo. El artefacto final tiene 318 líneas en un archivo.
