# Seguridad

## Qué puede hacer este proceso

Con `DRY_RUN=false` Doctor Descheduler **evicta pods** en los clusters configurados. Eso mueve cargas reales. El default de este repo es `DRY_RUN=true`.

Para funcionar necesita:

- leer los secrets de cluster de ArgoCD (kubeconfig de cada destino);
- permiso de eviction sobre pods en esos clusters.

Empezá en un cluster de prueba y recién después pasá a modo real.

## Secretos

No subas al repositorio:

- kubeconfig ni client certificates;
- `API_TOKEN`, `SESSION_SECRET`, `OIDC_CLIENT_SECRET`;
- `.env` con valores reales;
- capturas de la pestaña API (ahí se ve el token).

Los ejemplos de este repo usan `change-me`. Cambialos antes de exponer el panel.

## Superficie

- `GET /health` no pide autenticación.
- El resto de la API espera `Authorization: Bearer` o `X-API-Token`.
- El panel tiene login local. OpenID es opcional y viene apagado.
- No publiques el panel en Internet sin TLS y sin un token distinto del ejemplo.

## Reporte

Si encontrás un problema de seguridad, abrí un [advisory privado](https://github.com/ghcetraro/doctor-descheduler/security/advisories/new) o escribile al mantenedor. No abras un issue público con el detalle explotable.
