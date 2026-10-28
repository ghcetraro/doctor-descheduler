# Presentación — Doctor Descheduler

Texto corto, slide por slide. Las capturas están en `docs/assets/`.

## 1. Título

**Doctor Descheduler**

Un proceso. Varios clusters. La misma policy de descheduler, sin instalarla en cada uno.

## 2. El problema

El descheduler de Kubernetes se despliega por cluster. Umbrales, RBAC e historial quedan partidos. Cuando algo se mueve, no hay una sola pantalla para verlo.

## 3. La idea

Correr **una** API en el cluster donde ya está ArgoCD. Los secrets de cluster son el kubeconfig. Cada 15 minutos entra, mide y decide.

## 4. La policy

LowNodeUtilization sobre requests / allocatable.

- Nodo bajo: menos de 15 % en CPU, memoria o pods.
- Nodo alto: más de 60 %.
- No toca DaemonSet, Job, PVC, almacenamiento local ni pods críticos.
- Hace falta al menos 2 réplicas.

## 5. Dry-run primero

En este repo `DRY_RUN=true`. La pasada anota qué habría evictado y no mueve nada. El modo real es un cambio explícito.

## 6. El panel

![Dashboard](assets/dashboard-claro.png)

Uso por cluster, estado de la última pasada y un botón para correr uno ahora. Mientras corre, se ve el log.

## 7. Apariencia

![Apariencia clara](assets/apariencia-clara.png)

Claro u oscuro, compartido: queda en un ConfigMap, no solo en el navegador.

## 8. Cómo probarlo

```bash
cp .env.example .env
docker compose up --build
```

`http://localhost:8080`. Sin los secrets de ArgoCD la flota no conecta: el panel sí.

## 9. Cierre

Open source, MIT, Python 3.12.

Repo: https://github.com/ghcetraro/doctor-descheduler
