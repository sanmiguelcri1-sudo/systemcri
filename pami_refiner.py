import sqlite3
import urllib.request
import urllib.parse
import re
import time
import random
import logging

SQLITE_DB = 'hc_archive.db'

def solve_pami_dni(dni):
    url_base = "https://prestadores.pami.org.ar/result.php?c=6-2"
    try:
        # 1. Get Form/Captcha
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url_base, headers=headers)
        with urllib.request.urlopen(req) as response:
            cookie = response.headers.get('Set-Cookie')
            html = response.read().decode('utf-8', errors='ignore')
            
        match = re.search(r'name="captchaImage"\s+value="(\d+)\s*\+\s*(\d+)"', html)
        if not match: return None
        result = int(match.group(1)) + int(match.group(2))
        
        # 2. POST to search DNI
        post_url = "https://prestadores.pami.org.ar/result.php?c=6-2-2"
        data = urllib.parse.urlencode({'nroDocumento': dni, 'math2': str(result)}).encode()
        req_post = urllib.request.Request(post_url, data=data, headers=headers)
        if cookie: req_post.add_header('Cookie', cookie)
        
        with urllib.request.urlopen(req_post) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        # 3. Detect first data row
        rows = re.findall(r'<tr.*?>(.*?)</tr>', html, re.DOTALL)
        if len(rows) < 2: return None
        
        cols = re.findall(r'<td.*?>(.*?)</td>', rows[1], re.DOTALL)
        if len(cols) >= 6:
            name = re.sub('<.*?>', '', cols[0]).strip()
            beneficio = re.sub('<.*?>', '', cols[1]).strip()
            
            # Follow detail link for birthday
            detail_match = re.search(r'href="(result\.php\?c=6-2-1-1&.*?)"', cols[5])
            if detail_match:
                detail_url = "https://prestadores.pami.org.ar/" + detail_match.group(1).replace('&amp;', '&')
                req_det = urllib.request.Request(detail_url, headers=headers)
                if cookie: req_det.add_header('Cookie', cookie)
                with urllib.request.urlopen(req_det) as res_det:
                    det_html = res_det.read().decode('utf-8', errors='ignore')
                
                # Extraer campos desde la página de detalle si existen
                def _find_label(label):
                    m = re.search(rf'{label}.*?<b>(.*?)</b>', det_html, re.DOTALL | re.IGNORECASE)
                    if m:
                        return re.sub('<.*?>', '', m.group(1)).strip()
                    # fallback: look for td next to label in table cells
                    m2 = re.search(rf'<td[^>]*>\s*{label}\s*</td>\s*<td[^>]*>(.*?)</td>', det_html, re.DOTALL | re.IGNORECASE)
                    if m2:
                        return re.sub('<.*?>', '', m2.group(1)).strip()
                    return ''

                fn = _find_label('Fecha de Nacimiento')
                # normalizar fecha DD/MM/YYYY -> YYYY-MM-DD
                if fn and '/' in fn:
                    parts = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", fn)
                    if parts:
                        d, m, y = parts[0]
                        fn = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

                domicilio = _find_label('Domicilio') or _find_label('Direcci')
                localidad = _find_label('Localidad')
                telefono = _find_label('Tel') or _find_label('Telefono') or _find_label('Teléfono')
                nacionalidad = _find_label('Nacionalidad')

                # También intentar sacar número de afiliado si aparece en detalle
                afiliado = beneficio
                af_match = _find_label('Afiliado') or _find_label('Nro Afiliado') or _find_label('Nº Afiliado')
                if af_match:
                    afiliado = af_match

                return {
                    "name": name,
                    "beneficio": afiliado,
                    "fn": fn,
                    "domicilio": domicilio,
                    "localidad": localidad,
                    "telefono": telefono,
                    "nacionalidad": nacionalidad
                }
        return None
    except Exception as e:
        logging.exception(f"Error consultando PAMI para {dni}")
        return None

def refine_batch(limit=20):
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    # Seleccionar pacientes que les falta FN o Beneficio
    cursor.execute('''
        SELECT id, dni, apellido_nombre FROM patients 
        WHERE (num_beneficio IS NULL OR num_beneficio = '' OR fecha_nacimiento IS NULL OR fecha_nacimiento = '')
        AND dni IS NOT NULL AND dni != ''
        LIMIT ?
    ''', (limit,))
    
    patients = cursor.fetchall()
    print(f"Iniciando refinado de {len(patients)} pacientes...")
    
    updated = 0
    for p_id, dni, old_name in patients:
        print(f"Consultando PAMI para {old_name} (DNI {dni})...")
        res = solve_pami_dni(dni)
        if res:
            # Actualizar los campos disponibles
            cursor.execute('''
                UPDATE patients SET num_beneficio = ?, fecha_nacimiento = ?, domicilio = ?, localidad = ?, telefono = ?
                WHERE id = ?
            ''', (res.get('beneficio') or '', res.get('fn') or '', res.get('domicilio') or '', res.get('localidad') or '', res.get('telefono') or '', p_id))
            print(f"  OK: {res['name']} | FN: {res.get('fn','')} | Ben: {res.get('beneficio','')} | Loc: {res.get('localidad','')} | Tel: {res.get('telefono','')}")
            updated += 1
        else:
            print(f"  No se encontraron datos en PAMI.")
            
        # Espera aleatoria para no saturar
        time.sleep(random.uniform(2.0, 4.0))
        
    conn.commit()
    conn.close()
    print(f"Refinado completo. {updated} pacientes actualizados.")

if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    refine_batch(count)
