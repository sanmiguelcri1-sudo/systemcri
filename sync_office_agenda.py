import subprocess
import os
import sys
from utils.status import set_status

def full_sync():
    try:
        set_status(5, "Exportando datos de Office Agenda...")
        # Ejecutar script VBS de extraccion
        vbs_path = os.path.join("scratch", "export_split.vbs")
        
        # 32-bit cscript es REQUERIDO para el driver de 32-bit de Jet OLEDB
        cscript_path = r"C:\Windows\SysWOW64\cscript.exe"
        
        if not os.path.exists(cscript_path):
            set_status(0, "Error: No se encontró cscript.exe (32-bit).", "error")
            return
            
        subprocess.run([cscript_path, vbs_path], capture_output=True, text=True)
        
        set_status(25, "Integrando datos en HC (Carga de CSV)...")
        import sync_from_csv_v2
        sync_from_csv_v2.run_sync()
        
        set_status(70, "Completando DNI de Neuro desde Office Agenda...")
        import sync_neuro_dni_from_office
        sync_neuro_dni_from_office.sync_neuro_dni_from_office()
        
        set_status(85, "Reconstruyendo ficha maestra...")
        import database
        database.rebuild_patient_master()
        
        set_status(100, "Sincronización Total Completa.", "completed")
        
    except Exception as e:
        set_status(0, f"Error en sincronización: {str(e)}", "error")
        raise e

if __name__ == "__main__":
    full_sync()
