# Textos para LinkedIn — Doctor Descheduler

Copiá el bloque, pegalo y dejá el link del repo en el **primer comentario**. LinkedIn suele mostrar mejor un post que no lleva el link en el cuerpo.

**Repo:** `https://github.com/ghcetraro/doctor-descheduler`

**Imágenes:** `docs/assets/dashboard-claro.png` y `docs/assets/apariencia-clara.png`. Subí el dashboard como imagen del post. No subas capturas de la pestaña de tokens.

---

## Post breve

```
Publiqué Doctor Descheduler.

Un solo proceso rebalancea varios clusters de Kubernetes. Lee el kubeconfig que ArgoCD ya tiene, aplica LowNodeUtilization y puede correr en dry-run.

Open source · Python · MIT

El link está en el primer comentario.

#kubernetes #devops #opensource #python #sre
```

Comentario:

```
https://github.com/ghcetraro/doctor-descheduler
```

---

## Post recomendado

```
Instalar el descheduler en cada cluster funciona, hasta que son varios.

Misma policy, copiada N veces. El historial partido. Y cuando un nodo se llena, te enterás mirando uno por uno.

Doctor Descheduler hace esa pasada desde un solo lugar.

Corre junto a ArgoCD, entra a los clusters con el kubeconfig que ArgoCD ya guarda y aplica LowNodeUtilization: si un nodo está por arriba del 60 % y otro por debajo del 15 %, mueve pods que se pueden mover.

Qué no toca: DaemonSets, Jobs, pods con disco local o PVC, prioridad crítica.

El default del repo es dry-run. Anota la pasada y no evicta hasta que lo cambies.

El panel muestra la flota, deja correr un cluster a mano y va escribiendo el log mientras trabaja. El tema claro/oscuro queda guardado para todos.

Open source, Python, MIT.

Link en el primer comentario.

#kubernetes #devops #opensource #python #sre #platformengineering
```

Primer comentario:

```
Código, compose y capturas del panel en claro:

https://github.com/ghcetraro/doctor-descheduler
```

---

## Storytelling

```
El descheduler oficial es bueno. El problema era otro: tener que operarlo una vez por cluster.

Quería una sola policy, un solo historial y un botón para correr un cluster ahora, viendo qué está haciendo.

Eso es Doctor Descheduler. Un proceso. Los kubeconfigs salen de ArgoCD. Dry-run por defecto, para mirar antes de mover pods.

Si administrás más de un cluster, el repo está en el primer comentario.

#kubernetes #opensource #devops
```

---

## Versión técnica

```
Doctor Descheduler, open source.

Policy LowNodeUtilization sobre requests/allocatable (CPU, memoria, pods).
Umbrales: bajo < 15 %, alto > 60 %, mínimo 2 réplicas.
Filtros: sin DaemonSet, Job, PVC, local storage, critical priority ni afinidad required.
Un API en el cluster de ArgoCD. Intervalo 900 s. Ejecución manual con log en vivo.
DRY_RUN=true por defecto.

Python 3.12 · FastAPI · MIT

#kubernetes #python #sre
```

Comentario:

```
https://github.com/ghcetraro/doctor-descheduler
```

---

## Guion de video (60–90 s)

1. "Tengo varios clusters y no quiero un descheduler distinto en cada uno."
2. Mostrá el dashboard en claro (`docs/assets/dashboard-claro.png` o la pantalla en vivo).
3. "Este proceso lee el kubeconfig de ArgoCD y aplica la misma policy en todos."
4. "Por defecto no mueve nada: dry-run. Cuando lo paso a real, evicta pods que pueden irse a un nodo más libre."
5. Apretá Ejecutar en un cluster y dejá que se vea el log.
6. "El código es MIT. Link en el comentario."

No muestres la pestaña API ni un kubeconfig.

---

## Carrusel

| Slide | Texto |
|-------|--------|
| 1 | Un descheduler para varios clusters |
| 2 | El oficial, instalado N veces, parte la operación |
| 3 | Doctor Descheduler corre en uno y entra al resto |
| 4 | LowNodeUtilization: 15 % / 60 %, requests sobre allocatable |
| 5 | No toca DaemonSet, Job, PVC ni pods críticos |
| 6 | Dry-run por defecto |
| 7 | Panel: flota, log en vivo, tema claro |
| 8 | MIT · github.com/ghcetraro/doctor-descheduler |

---

## Preguntas para clavar en comentarios

- ¿Lo correrías en dry-run una semana antes de dejarlo evictar?
- ¿Medís desbalance con requests o con uso real?
- ¿Preferís un CronJob por cluster o un solo proceso?

---

## Hashtags

Usá 5 o 6, no más de 8:

`#kubernetes` `#devops` `#opensource` `#python` `#sre` `#platformengineering`

---

## Antes de publicar

- [ ] El link va en el primer comentario, no solo en el post.
- [ ] La imagen es el dashboard en claro, sin la pestaña de tokens.
- [ ] No hay IPs, dominios internos ni kubeconfig en la captura ni en el texto.
- [ ] El repo ya está en GitHub y el README se ve.
- [ ] La captura no muestra nombres de clusters, usuarios ni correos reales.
