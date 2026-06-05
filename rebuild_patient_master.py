import database


def main():
    database.init_db()
    result = database.rebuild_patient_master()
    print(result)


if __name__ == "__main__":
    main()
