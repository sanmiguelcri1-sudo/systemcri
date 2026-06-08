# SYSTEMCRI

Sistema central para controlar las tres sucursales: San Miguel, Ituzaingo y Merlo.

## Como se usa como programa local

1. Ejecutar `build_systemcri_exe.cmd` en la PC donde se prepara el sistema.
2. Al finalizar, usar `dist\SYSTEMCRI.exe`.
3. Dejar `dist\.env` junto al ejecutable con los datos reales de Intersoftic.
4. Abrir `SYSTEMCRI.exe`. El programa levanta su motor interno solo local y muestra una ventana propia de SYSTEMCRI.

No se abre Chrome/Edge como navegador y no hace falta publicarlo en internet. Mientras se usa el sistema, dejar abierta la ventana del ejecutable.

La base local queda en la misma carpeta del exe como `hc_archive.db`. Si se recompila el programa, no borrar esa base si ya tiene datos cargados.

## Alcance local

SYSTEMCRI queda disponible solo en la PC donde se ejecuta. Esto permite usar los drivers y accesos locales necesarios para Intersoftic sin exponer el sistema en internet ni en otras maquinas de la red.

## Tiempo real

Las pantallas de Estadistica Intersoftic y Auditoria se actualizan automaticamente cada 30 segundos mientras estan abiertas. Los botones de actualizar siguen disponibles para forzar una consulta manual.
