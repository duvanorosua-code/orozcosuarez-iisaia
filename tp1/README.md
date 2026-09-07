# TP 1 — Reproductor de Musica

Una aplicación para escuchar musica pero para cada usuario representa un reto cambiar, parar o continuar la cancion

## Cómo se ejecuta

Doble click en `index.html`. Un solo archivo, sin dependencias.

## Qué me propuse construir

Un mas diseño de experiencia de usuario en el que para poder realizar un cambio en una lista de reproducción, represente un reto realizar cada accion y los usurio se sepan la canción. Costo dos prompts realizar con la metodologia y los conocimientos de clase.

## Decisiones que tomé yo

**DOM en vez de `<canvas>`.** La solicitud de eventos al DOM se basa en el ordenamiento del anagrama y la funcionalidad de los botones de siguiete, anterior y parar/continuar.

**Las letras del anagrama se reordenan.** Despues de haber ejecutado la accion del evento de cualquiera de los botones se reordenan aleatoriamente las letras por si se quiere hacer otra acción.

**Posicionamiento y Funcionalidad.** Es un poco molesto el desarrollo del juego para hacer una accion que quieres usar normalmente, cuando claramente no quieres verlo como si fuera una recompensa.

## Qué salió mal y cómo lo corregí

El resultado salió bien y el prompt igual estaba mal.

Se genero como grid el anagrama lo cual lo hacia quizas un poco mas dificil de completar y no tenia el nombre de la cancion que querias ordenar en el anagrama, tambien se quedaban enlazadas las letras que decidias mover como clicks entonces se cambio eso en el promp posterior.

Se especifico sobre esos puntos con el segundo prompt y la funcionalidad siguio perfecta como se esperaba.

## Prompts

El registro completo está en [prompts.md](prompts.md). Los que más pesaron son el primero, que fija el artefacto entero, y el del reordenamiento, que convirtió una animación que se mira en una interfaz que se opera.
