import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from database import add_doctor, get_all_doctors, delete_doctor, get_doctor_id_by_telegram_id, get_all_services


def test_add_and_get_doctor():
    name = "Test Doktor"
    phone = "900000000"
    telegram_id = 999999999

    # Doktor qo‘shish
    add_doctor(name, phone, telegram_id)

    # Endi tekshirish uchun doctor_id olish
    doctor_id = get_doctor_id_by_telegram_id(telegram_id)

    assert doctor_id is not None
    assert isinstance(doctor_id, int)

def test_get_doctor_id_by_telegram_id():
    # Oldindan mavjud Telegram ID
    telegram_id = 999999999  # oldingi testda qo‘shgan edik

    doctor_id = get_doctor_id_by_telegram_id(telegram_id)

    assert doctor_id is not None
    assert isinstance(doctor_id, int)


def test_get_all_services():
    services = get_all_services()
    assert isinstance(services, list)
    for service in services:
        assert isinstance(service, tuple)
        assert len(service) == 3  # id, name, price

def test_get_all_doctors():
    doctors = get_all_doctors()
    assert isinstance(doctors, list)
    if doctors:
        assert len(doctors[0]) == 3  # id, name, phone