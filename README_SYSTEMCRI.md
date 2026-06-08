# SYSTEMCRI Intersoftic

Sistema local para revisar Estadística Intersoftic y Auditoría Intersoftic de San Miguel, Ituzaingo y Merlo.

## Como se usa como programa local

1. Ejecutar `build_systemcri_exe.cmd` en la PC donde se prepara el sistema.
2. Al finalizar, usar `dist\SYSTEMCRI.exe`.
3. Dejar `dist\.env` junto al ejecutable con los datos reales de Intersoftic.
4. Abrir `SYSTEMCRI.exe`. El programa levanta su motor interno solo local y muestra una ventana propia de SYSTEMCRI.

No se abre Chrome/Edge como navegador y no hace falta publicarlo en internet. Mientras se usa el sistema, dejar abierta la ventana del ejecutable.

## Alcance local

SYSTEMCRI queda disponible solo en la PC donde se ejecuta. Esto permite usar los drivers y accesos locales necesarios para Intersoftic sin exponer el sistema en internet ni en otras maquinas de la red.

## Tiempo real

Las dos pantallas consultan Intersoftic al abrir o al usar el boton `Actualizar`.
