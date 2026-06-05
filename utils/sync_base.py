import sqlite3
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, List, Dict

class BaseSync(ABC):
    def __init__(self, db_path: str = 'hc_archive.db'):
        self.db_path = db_path
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def fetch_data(self) -> List[Any]:
        """Obtiene los datos de la fuente (API, CSV, MDB, etc.)"""
        pass

    @abstractmethod
    def process_row(self, cursor: sqlite3.Cursor, row: Any) -> bool:
        """Procesa una fila individual e impacta en la DB"""
        pass

    def run(self):
        self.logger.info("Iniciando proceso de sincronización...")
        data = self.fetch_data()
        self.logger.info(f"Se obtuvieron {len(data)} registros para procesar.")

        conn = self.get_connection()
        cursor = conn.cursor()
        success_count = 0
        error_count = 0

        try:
            for row in data:
                try:
                    if self.process_row(cursor, row):
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    self.logger.error(f"Error procesando fila: {e}")
                    error_count += 1

            conn.commit()
            self.logger.info(f"Sincronización finalizada. Éxito: {success_count}, Errores: {error_count}")
        except Exception as e:
            self.logger.error(f"Error general en la sincronización: {e}")
            conn.rollback()
        finally:
            conn.close()
