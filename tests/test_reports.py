import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_services_summary_by_doctor, get_services_by_doctor, get_expected_total_by_doctor

from database import get_services_summary_by_doctor
from datetime import datetime

from decimal import Decimal


def test_services_summary_with_date_range():
    doctor_id = 28
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 5)

    result = get_services_summary_by_doctor(doctor_id, start_date, end_date)

    assert isinstance(result, list)
    for row in result:
        assert len(row) == 4  # name, quantity, price, created_at
        assert isinstance(row[0], str)      # service name
        assert isinstance(row[1], int)      # quantity
        assert isinstance(row[2], (int, float))  # price

from database import get_payments_by_doctor

def test_payments_by_doctor():
    doctor_id = 28
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 5)

    result = get_payments_by_doctor(doctor_id, start_date, end_date)

    assert isinstance(result, list)
    for row in result:
        assert len(row) == 3  # amount, created_at, service_name
        assert isinstance(row[0], (int, float, Decimal))  # ✅ Decimal turini qo‘shdik



def test_services_by_doctor():
    doctor_id = 28  # mavjud doctor_id qo‘ying
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 5)

    result = get_services_by_doctor(doctor_id, start_date, end_date)

    assert isinstance(result, list)
    for row in result:
        assert len(row) == 4
        assert isinstance(row[0], str)            # service name
        assert isinstance(row[1], int)            # quantity
        assert isinstance(row[2], (float, int)) or str(row[2]).replace('.', '', 1).isdigit()
        assert isinstance(row[3], datetime)       # created_at



def test_expected_total_by_doctor():
    doctor_id = 28  # mavjud doktor ID
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 5)

    total = get_expected_total_by_doctor(doctor_id, start_date, end_date)

    assert total is not None
    assert isinstance(total, (int, float)) or str(total).replace('.', '', 1).isdigit()

def test_services_summary_by_doctor():
    doctor_id = 28
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 5)

    result = get_services_summary_by_doctor(doctor_id, start_date, end_date)

    assert isinstance(result, list)
    for row in result:
        assert len(row) == 4  # name, quantity, price, created_at
        assert isinstance(row[0], str)      # name
        assert isinstance(row[1], int)      # quantity
        assert isinstance(row[2], (int, float))  # price
        assert row[3] is not None           # created_at