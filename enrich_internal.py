import sqlite3
import re

DB = 'hc_archive.db'

def normalize(s):
    if not s:
        return ''
    return re.sub(r'\s+', ' ', s.strip()).upper()

def first_nonempty(*vals):
    for v in vals:
        if v and str(v).strip():
            return v
    return ''

def enrich(limit=0):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    q = '''
    SELECT id, apellido_nombre, dni, domicilio, localidad, telefono, fecha_nacimiento
    FROM patients
    WHERE (COALESCE(domicilio,'')='' OR COALESCE(localidad,'')='' OR COALESCE(telefono,'')='' OR COALESCE(fecha_nacimiento,'')='')
      AND COALESCE(dni,'')<>''
    '''
    if limit and limit > 0:
        q += f" LIMIT {int(limit)}"

    rows = cur.execute(q).fetchall()
    print(f"Pacientes a revisar: {len(rows)}")

    updated = 0
    for r in rows:
        pid = r['id']
        dni = r['dni']
        name = r['apellido_nombre']

        # buscar en patient_master por dni
        pm = cur.execute('SELECT domicilio, localidad, telefono1, telefono2, fecha_nacimiento FROM patient_master WHERE dni = ?', (dni,)).fetchone()
        domicilio = localidad = telefono = fecha_nac = ''
        if pm:
            domicilio = first_nonempty(pm['domicilio'], '')
            localidad = first_nonempty(pm['localidad'], '')
            telefono = first_nonempty(pm['telefono1'], pm['telefono2'], '')
            fecha_nac = first_nonempty(pm['fecha_nacimiento'], '')

        # si no encontrado, buscar en neuro_patients
        if not (domicilio or localidad or telefono or fecha_nac):
            np = cur.execute('SELECT domicilio, localidad, telefono1, telefono2, fecha_nacimiento FROM neuro_patients WHERE dni = ?', (dni,)).fetchone()
            if np:
                domicilio = domicilio or first_nonempty(np['domicilio'], '')
                localidad = localidad or first_nonempty(np['localidad'], '')
                telefono = telefono or first_nonempty(np['telefono1'], np['telefono2'], '')
                fecha_nac = fecha_nac or first_nonempty(np['fecha_nacimiento'], '')

        # fallback: buscar por nombre en patient_master
        if not (domicilio or localidad or telefono or fecha_nac):
            like = f"%{name}%"
            pm2 = cur.execute('SELECT domicilio, localidad, telefono1, telefono2, fecha_nacimiento FROM patient_master WHERE UPPER(apellido_nombre) LIKE ? LIMIT 1', (like.upper(),)).fetchone()
            if pm2:
                domicilio = domicilio or first_nonempty(pm2['domicilio'], '')
                localidad = localidad or first_nonempty(pm2['localidad'], '')
                telefono = telefono or first_nonempty(pm2['telefono1'], pm2['telefono2'], '')
                fecha_nac = fecha_nac or first_nonempty(pm2['fecha_nacimiento'], '')

        # if we found at least one value, update
        if domicilio or localidad or telefono or fecha_nac:
            cur.execute('''
                UPDATE patients SET domicilio = COALESCE(NULLIF(?,''), domicilio), localidad = COALESCE(NULLIF(?,''), localidad), telefono = COALESCE(NULLIF(?,''), telefono), fecha_nacimiento = COALESCE(NULLIF(?,''), fecha_nacimiento)
                WHERE id = ?
            ''', (domicilio, localidad, telefono, fecha_nac, pid))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Enriquecimiento completado. Pacientes actualizados: {updated}")

if __name__ == '__main__':
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    enrich(limit)
