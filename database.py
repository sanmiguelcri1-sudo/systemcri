"""
Facade for the modular database system.
Imports all functions from the specialized db/ modules to maintain backward compatibility.
"""
from db.base import create_connection, init_db, DB_NAME
from db.patients import (
    insert_patient, get_patient_by_id, delete_patient, search_patients,
    get_patient_by_dni, get_next_hc, update_renovation,
    get_renovation_history, delete_renewal_entry, update_patient_fields,
    get_patients_all, sync_patient_master_from_patient_id, update_renewal_entry,
    rebuild_patient_master
)
from db.neuro import (
    get_neuro_patients, get_neuro_patients_by_month, search_neuro_patients,
    get_neuro_patient_by_id, insert_neuro_patient, update_neuro_patient,
    delete_neuro_patient, mark_neuro_whatsapp_sent, enrich_neuro_results
)
from db.hd import (
    get_hospital_dia, save_hd_entry, delete_hd_entry, check_op_duplicate
)
from db.dashboard import (
    get_folder_stats, get_panel_dashboard
)
from db.staff import (
    upsert_staff, list_staff, list_intersoftic_professionals, upsert_intersoftic_professional,
    delete_intersoftic_professional, get_staff_by_key, get_staff_by_id, delete_staff,
    update_staff_intersoftic_details,
    upsert_staff_attendance, get_staff_attendance, delete_staff_attendance,
    delete_staff_attendance_for_staff_date, list_staff_attendance_by_month,
    list_staff_attendance_for_staff_by_month, delete_staff_attendance_for_staff_month,
    get_staff_month_totals
)
from db.agenda import (
    get_agenda, get_agenda_week, insert_appointment, delete_appointment
)
from db.reports import (
    get_report_source, mark_report_source_processed
)
from db.holidays import (
    get_holidays, add_holiday, delete_holiday
)
from db.matching import (
    choose_value, merge_phones, row_to_dict, build_master_payload,
    find_patient_match, find_master_match, upsert_patient_master,
    find_patient_master_data
)
from utils.text import normalize_text, normalize_name, normalize_digits, is_blank

# Legacy aliases
def update_patient(p_id: int, data: dict) -> bool:
    data = dict(data)
    data["id"] = p_id
    return insert_patient(data)

if __name__ == "__main__":
    init_db()
