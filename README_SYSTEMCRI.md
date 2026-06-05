# SYSTEMCRI

Sistema central para controlar las tres sucursales: San Miguel, Ituzaingo y Merlo.

## Como se usa

1. Elegir una sola PC/servidor central para dejar el sistema prendido.
2. En esa PC, ejecutar `install_dependencies.cmd` una vez.
3. Copiar `.env.example` como `.env` y completar la clave real de Intersoftic.
4. Ejecutar `run_server.cmd`.
5. Abrir desde cualquier PC o celular de la misma red:

   `http://IP_DE_LA_PC_CENTRAL:8010/`

En esta arquitectura todos entran al mismo servidor, por eso ven la misma informacion al mismo tiempo.

## Tiempo real

Las pantallas de Estadistica Intersoftic y Auditoria se actualizan automaticamente cada 30 segundos mientras estan abiertas. Los botones de actualizar siguen disponibles para forzar una consulta manual.

## Para acceso fuera de la red

Si las tres sucursales no estan en la misma red, hace falta una de estas opciones:

- VPN entre sucursales.
- Un servidor en la nube.
- Un tunel seguro tipo Cloudflare Tunnel.

Para dejarlo definitivo y seguro tambien falta definir usuarios/permisos de acceso.
