import sqlite3
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from db.base import DB_NAME
from utils.sync_base import BaseSync
from utils.date import normalize_date_es as normalize_date

class HospitalDiaSync(BaseSync):
    def __init__(self):
        super().__init__(DB_NAME)
        self.raw_data_sheet3 = """
1	JCP	ROJAS VILMA	150506901901/00	ACV	3325530641194	9929257774	4/6/2025	9929643614	4/7/2025	9930000768	4/8/2025	9930000768	4/9/2025	SUSPENDIDO	6/10/2025
2	SM	ACUÑA RAMON	150573382801/00	ACV	3325530650776	9929257961	4/6/2025	9929643649	4/7/2025	9930000817	4/8/2025	9930000817	4/9/2025	SUSPENDIDO	6/10/2025
3	SM	CANDIA JARA	150073801206/00	PARKINSON	3325530664643	9929257891	4/6/2025	9929643688	4/7/2025	9930000866	4/8/2025	9930000866	4/9/2025	suspendido	6/10/2025
4	SM	DOMINGUEZ ANGEL	150563275400/00	ACV	3325586266907	9929584677	1/7/2025	9929997914	1/8/2025	9930409771	1/9/2025	9930802196	1/10/2025		
5	SM	PINTOS ROJAS EMETERIO	150702427300/00	ACV	3325587594702	9929584788	1/7/2025	9929998116	1/8/2025	9930409811	1/9/2025	9930802268	1/10/2025		
6	SM	MOSTEIRO GUILLERMO	465019422408/00	ACV	3325586267980	9929584740	1/7/2025	9929998070	1/8/2025	9930409852	1/9/2025	9930802402	1/10/2025		
7	SM	DIAZ AMERICO	465023594903/00	ACV	3325586268765	9929584833	1/7/2025	9929997839	1/8/2025	9930409886	1/9/2025	9930802653	1/10/2025		
8	MORENO	GOMEZ VICTOR	140130971200/00	ACV	3325646894873	9929997987	1/8/2025	9930409915	1/9/2025	9930802777	1/10/2025	9931254488	3/11/2025		
1	SM	BUSTOS CLARISA	150160630908/00	ACV	3325762358716	9930791868	1/10/2025	9931254444	3/11/2025	9931615165	3/12/2025	9932094811	2/1/2026		
1	SM	DIAZ MARIA INES	155604563605/00	ACV	3325838085577	9931254535	3/11/2025	9931615210	3/12/2025	9932095137	2/1/2026	9932496567	2/2/2026		
2	SM	CASTAÑEDA ELSA	150717913608/00	REH MARCHA	3325905124567	9931517246	1/12/2025	9932095397	2/1/2026	9932496765	2/2/2026	9932848128	2/3/2026		
1	MORENO	GAUTIER EDGARDO	140227108303/00	ACV	3325916850332	9931556812	1/12/2025	9932096973	2/1/2026	9932496614	2/2/2026	9932848239	2/3/2026		
4	SM	BRAVO CELSA	150549926002/00	PARKINSON	3325932818682	9931666922	1/12/2025	9932097044	2/1/2026	9932496510	2/2/2026	9932847887	2/3/2026		
2	SM	YÑIGUEZ JOSE	150586338108/00	PARKINSON	3325953311476	9932097106	2/1/2026	9932496698	2/2/2026	9932848650	2/3/2026	9933328286	1/4/2026		
3	SM	BATTISTA OSCAR	140179221901/00	PARKINSON	3325953320195	9932097177	2/1/2026	9932496471	2/2/2026	9932847765	2/3/2026	9933328442	1/4/2026		
4	SM	BRANDAN LUISA	150446977801/00	ACV	3326010705788	9932379609	2/2/2026	9932847835	2/3/2026	9933328489	1/4/2026		4/5/2026		
5	SM	RASPO MARIA	140070949305/00	ACV	3326010707348	9932379453	2/2/2026	9932848450	2/3/2026	9933328555	1/4/2026		4/5/2026		
6	SM	PEREYRA FERNANDO	140217269906/00	ACV	3326010706792	9932379559	2/2/2026	9932848400	2/3/2026	9933328598	1/4/2026		4/5/2026		
7	MORENO	IVANOV MARTA	150706070506/00	ACV	3326010706396	9932379396	2/2/2026	9932848327	2/3/2026	9933328636	1/4/2026		4/5/2026		
8	SM	TORINO GERONIMA	150498423800/00	PARKINSON	3326040381877	9932496649	2/2/2026	9932848595	2/3/2026	9933328683	1/4/2026		4/5/2026		
9	SM	ACUÑA CLEDIA	150003742001/00	ACV	3326040382423	9932496419	2/2/2026	9932847701	2/3/2026	9933328715	1/4/2026		4/5/2026		
10	SM	BRITO RODOLFO	150723492605/00	ACV	3326083012103	9932847958	2/3/2026	9933328775	1/4/2026		4/5/2026				
11	SM	SEVERO EMILIO	140046900308/00	ACV	3326083010260	9932848507	2/3/2026	9933328814	1/4/2026		4/5/2026				
12	SM	CEJAS MARCELO	140236817001/00	ACV	3326154943008	9933328855	1/4/2026		4/5/2026						
        """.strip()
        self.raw_data_medico_aud = """
1	SM	PEREZ MARIA CRISTINA	140031208901/00	ACV	MEDICO AUD		01/06/2026
2	SM	RIVEROS GREGORIO CLEMENTINO	150460203002/00	PARKINSON	MEDICO AUD		01/06/2026
3	SM	MUGGERI JUAN CARLOS	140210483904/00	ACV	MEDICO AUD		01/06/2026
4	SM	GONZALEZ AURORA	140236657808/00	ACV	MEDICO AUD		01/06/2026
        """.strip()

    def fetch_data(self) -> List[Dict]:
        all_lines = self.raw_data_sheet3.split("\n") + self.raw_data_medico_aud.split("\n")
        records = []
        for line in all_lines:
            parsed = self.parse_line(line)
            if parsed: records.append(parsed)
        return records

    def parse_line(self, line: str) -> Optional[Dict]:
        parts = line.split("\t")
        if len(parts) < 3: return None
        try:
            name = parts[2].strip()
            beneficio = parts[3].strip()
            loc = parts[1].strip()
            diag = parts[4].strip()
            orden = parts[5].strip()
            
            # Extract OPs
            ops = []
            for i in range(6, len(parts) - 1, 2):
                op_num = parts[i].strip()
                op_date = parts[i+1].strip() if i+1 < len(parts) else ""
                if op_num:
                    ops.append((op_num, normalize_date(op_date)))
            
            suspendido = "SUSPENDIDO" in line.upper()
            return {"name": name, "beneficio": beneficio, "loc": loc, "diag": diag, "orden": orden, "ops": ops, "suspendido": suspendido}
        except: return None

    def find_patient(self, cursor: sqlite3.Cursor, name: str, beneficio: str) -> tuple[Optional[int], Optional[str]]:
        # Match by beneficio
        if beneficio and beneficio not in ('', '-', '—'):
            cursor.execute("SELECT id, apellido_nombre FROM patients WHERE num_beneficio = ?", (beneficio,))
            row = cursor.fetchone()
            if row: return row['id'], row['apellido_nombre']
        
        # Match by name
        cursor.execute("SELECT id, apellido_nombre FROM patients WHERE UPPER(TRIM(apellido_nombre)) = ?", (name.upper(),))
        row = cursor.fetchone()
        if row: return row['id'], row['apellido_nombre']
        
        return None, None

    def process_row(self, cursor: sqlite3.Cursor, row: Any) -> bool:
        # Not used because we override run() for full reload logic
        return True

    def run(self):
        self.logger.info("Iniciando recarga de Hospital de Día...")
        data = self.fetch_data()
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            # 1. Backup UI entries
            cursor.execute("""
                SELECT hd.id, hd.patient_id, p.apellido_nombre, hd.localidad, hd.diagnostico,
                       hd.orden_elect, hd.estado, hd.fecha_pedido, hd.sesiones_check, hd.sesiones_max
                FROM hospital_dia hd
                JOIN patients p ON p.id = hd.patient_id
            """)
            existing_hd = {row['patient_id']: dict(row) for row in cursor.fetchall()}
            
            cursor.execute("SELECT * FROM hd_ops")
            all_ops_backup = {}
            for row in cursor.fetchall():
                hd_id = row['hd_id']
                if hd_id not in all_ops_backup: all_ops_backup[hd_id] = []
                all_ops_backup[hd_id].append(dict(row))

            # 2. Clean
            cursor.execute("DELETE FROM hd_ops")
            cursor.execute("DELETE FROM hospital_dia")
            
            # 3. Process records
            loaded_patient_ids = set()
            for record in data:
                p_id, matched_name = self.find_patient(cursor, record["name"], record["beneficio"])
                if p_id is None:
                    temp_dni = re.sub(r'\D', '', record["beneficio"])[-8:] if record["beneficio"] else f"TEMP{len(loaded_patient_ids)}"
                    cursor.execute(
                        "INSERT INTO patients (apellido_nombre, num_beneficio, num_hc, anio_vigencia, mes_renovacion, dni) VALUES (?, ?, ?, ?, ?, ?)",
                        (record["name"], record["beneficio"], "TEMP_" + temp_dni, 2026, 1, temp_dni)
                    )
                    p_id = cursor.lastrowid
                    self.logger.info(f"Paciente nuevo creado: {record['name']}")
                
                loaded_patient_ids.add(p_id)
                estado = "Suspendido" if record["suspendido"] else "Activo"
                cursor.execute(
                    "INSERT INTO hospital_dia (patient_id, localidad, diagnostico, orden_elect, estado, fecha_pedido) VALUES (?, ?, ?, ?, ?, ?)",
                    (p_id, record["loc"], record["diag"], record["orden"], estado, today)
                )
                hd_id = cursor.lastrowid
                for op_num, op_date in record["ops"]:
                    cursor.execute("INSERT INTO hd_ops (hd_id, op_number, fecha_val) VALUES (?, ?, ?)", (hd_id, op_num, op_date))

            # 4. Restore UI entries
            restored = 0
            for pid, hd_data in existing_hd.items():
                if pid not in loaded_patient_ids:
                    cursor.execute(
                        "INSERT INTO hospital_dia (patient_id, localidad, diagnostico, orden_elect, estado, fecha_pedido, sesiones_check, sesiones_max) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (pid, hd_data['localidad'], hd_data['diagnostico'], hd_data['orden_elect'], hd_data['estado'], hd_data['fecha_pedido'], hd_data.get('sesiones_check', 0), hd_data.get('sesiones_max', 24))
                    )
                    new_hd_id = cursor.lastrowid
                    if hd_data['id'] in all_ops_backup:
                        for op in all_ops_backup[hd_data['id']]:
                            cursor.execute("INSERT INTO hd_ops (hd_id, op_number, fecha_val, color_code) VALUES (?, ?, ?, ?)", (new_hd_id, op.get('op_number', ''), op.get('fecha_val', ''), op.get('color_code', '')))
                    restored += 1
            
            conn.commit()
            from db.patients import rebuild_patient_master
            rebuild_patient_master()
            self.logger.info(f"HD Recargado. Registros: {len(loaded_patient_ids)}, Restaurados UI: {restored}")
        except Exception as e:
            self.logger.error(f"Error en HospitalDiaSync: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == "__main__":
    HospitalDiaSync().run()
