import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Message
from telegram.ext import ConversationHandler
from service import show_services_for_payment, select_service, SELECT_SERVICE_QUANTITY, add_service_to_doctor, \
    open_doctor_menu
from telegram import InlineKeyboardMarkup

from service import ask_service_quantity

@pytest.mark.asyncio
@patch("service.doctor_view.add_doctor_service")
@patch("service.doctor_view.schedule_notification")
async def test_ask_service_quantity_valid(mock_schedule, mock_add_service):
    fake_message = MagicMock(spec=Message)
    fake_message.text = "3"
    fake_message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {
        "selected_service_price": 50000,
        "selected_service_name": "UZI",
        "doctor_id": 1,
        "selected_service_id": 10
    }

    update = MagicMock()
    update.message = fake_message

    result = await ask_service_quantity(update, context)

    mock_add_service.assert_called_once_with(1, 10, 3)
    mock_schedule.assert_called_once()
    fake_message.reply_text.assert_called_once()
    assert result == ConversationHandler.END

@pytest.mark.asyncio
@patch('service.doctor_view.get_all_services')
async def test_show_services_for_payment_with_services(mock_get_services):
    # 1. Mock services
    mock_get_services.return_value = [(1, "Tekshiruv", 10000), (2, "Davolash", 20000)]

    # 2. Mock update/callback_query
    mock_query = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    # 3. Call function
    result = await show_services_for_payment(mock_update, {})

    # 4. Test expected behavior
    mock_query.edit_message_text.assert_called_once()
    called_args, called_kwargs = mock_query.edit_message_text.call_args
    assert "🛠 Xizmatni tanlang:" in called_args[0]
    assert isinstance(called_kwargs["reply_markup"], InlineKeyboardMarkup)
    assert result == 1  # SELECT_SERVICE_QUANTITY


@pytest.mark.asyncio
@patch('service.doctor_view.get_all_services')
async def test_show_services_for_payment_without_services(mock_get_services):
    mock_get_services.return_value = []  # Empty service list

    mock_query = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    result = await show_services_for_payment(mock_update, {})

    mock_query.edit_message_text.assert_called_once_with("❌ Xizmatlar topilmadi.")
    assert result == ConversationHandler.END


@pytest.mark.asyncio
@patch('service.doctor_view.get_service_by_id')
@patch('service.doctor_view.get_doctor_id_by_telegram_id')
async def test_select_service_valid(mock_get_doctor_id, mock_get_service):
    # Mocks
    mock_get_service.return_value = {"name": "Tekshiruv", "price": 10000}
    mock_get_doctor_id.return_value = 28

    mock_query = AsyncMock()
    mock_query.data = "select_service_1"
    mock_query.from_user.id = 123456

    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    # 🧠 Context ni obyekt sifatida yaratamiz
    context = MagicMock()
    context.user_data = {}

    # Call function
    result = await select_service(mock_update, context)

    # Assertions
    assert context.user_data["selected_service_id"] == 1
    assert context.user_data["selected_service_name"] == "Tekshiruv"
    assert context.user_data["selected_service_price"] == 10000
    assert context.user_data["doctor_id"] == 28
    mock_query.edit_message_text.assert_called_once()
    assert "sonini kiriting" in mock_query.edit_message_text.call_args[0][0]
    assert result == 1  # SELECT_SERVICE_QUANTITY


@pytest.mark.asyncio
@patch('service.doctor_view.schedule_notification')
@patch('service.doctor_view.add_doctor_service')
async def test_ask_service_quantity_valid(mock_add_service, mock_schedule_notification):
    # Fake context
    context = MagicMock()
    context.user_data = {
        "selected_service_price": 10000,
        "selected_service_name": "Tekshiruv",
        "doctor_id": 28,
        "selected_service_id": 1
    }

    # Fake update
    mock_message = MagicMock()
    mock_message.text = "2"
    mock_message.reply_text = AsyncMock()  # 👈 MUHIM: endi AsyncMock
    update = MagicMock()
    update.message = mock_message

    # Funksiyani chaqirish
    result = await ask_service_quantity(update, context)

    # ✅ Tekshiruvlar
    mock_add_service.assert_called_once_with(28, 1, 2)
    mock_schedule_notification.assert_called_once()
    mock_message.reply_text.assert_called_once()

    assert result == ConversationHandler.END

@pytest.mark.asyncio
async def test_ask_service_quantity_invalid():
    # Fake context (kerakli user_data bilan)
    context = MagicMock()
    context.user_data = {
        "selected_service_price": 10000,
        "selected_service_name": "Tekshiruv",
        "doctor_id": 28,
        "selected_service_id": 1
    }

    # Fake update with invalid quantity
    mock_message = MagicMock()
    mock_message.text = "abc"  # noto‘g‘ri son
    mock_message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = mock_message

    # Run function
    result = await ask_service_quantity(update, context)

    # Check that it sent error message
    mock_message.reply_text.assert_called_once_with("❌ To‘g‘ri son kiriting (musbat butun son).")
    assert result == SELECT_SERVICE_QUANTITY

@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor_with_services(mock_get_all_services):
    mock_get_all_services.return_value = [(1, "Tekshiruv", 10000), (2, "Davolash", 20000)]

    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    result = await add_service_to_doctor(mock_update, {})

    mock_query.edit_message_text.assert_called_once()
    called_args, called_kwargs = mock_query.edit_message_text.call_args

    assert "Qo‘shiladigan xizmatni tanlang" in called_args[0]
    assert isinstance(called_kwargs["reply_markup"], InlineKeyboardMarkup)

@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor_without_services(mock_get_all_services):
    mock_get_all_services.return_value = []  # xizmatlar yo‘q

    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    result = await add_service_to_doctor(mock_update, {})

    mock_query.edit_message_text.assert_called_once_with("❌ Hozircha xizmatlar mavjud emas.")


@pytest.mark.asyncio
@patch("service.doctor_view.get_services_summary_by_doctor")
@patch("service.doctor_view.get_expected_total_by_doctor")
@patch("service.doctor_view.get_payments_by_doctor")
async def test_open_doctor_menu(
    mock_get_payments,
    mock_get_expected_total,
    mock_get_services_summary
):
    doctor_id = 28

    # Fake data
    mock_get_services_summary.return_value = [("Tekshiruv", 10000, 2, None)]
    mock_get_expected_total.return_value = 20000
    mock_get_payments.return_value = [(5000, None, None)]

    # Fake update
    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    # ✅ context must be a mock with .user_data
    context = MagicMock()
    context.user_data = {}

    # Run function
    await open_doctor_menu(mock_update, context, doctor_id)

    # Tekshirish
    mock_query.edit_message_text.assert_called_once()
    called_args, called_kwargs = mock_query.edit_message_text.call_args

    assert "Doktor uchun ma'lumotlar" in called_args[0]
    assert "20000 so‘m" in called_args[0]  # Umumiy summa
    assert "5000 so‘m" in called_args[0]   # To‘lov
    assert "15000 so‘m" in called_args[0]  # Qarzdorlik


@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor(mock_get_all_services):
    mock_get_all_services.return_value = [
        (1, "Tekshiruv", 10000),
        (2, "Davolash", 15000)
    ]

    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    context = {}

    await add_service_to_doctor(mock_update, context)

    mock_query.edit_message_text.assert_called_once()
    args, kwargs = mock_query.edit_message_text.call_args

    assert "Qo‘shiladigan xizmatni tanlang" in args[0]
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_ask_service_quantity_invalid():
    # Noto‘g‘ri kiritilgan qiymat (matn)
    mock_message = AsyncMock()
    mock_message.text = "salom"
    update = MagicMock()
    update.message = mock_message

    context = MagicMock()
    context.user_data = {}

    result = await ask_service_quantity(update, context)

    mock_message.reply_text.assert_called_once_with("❌ To‘g‘ri son kiriting (musbat butun son).")
    assert result == SELECT_SERVICE_QUANTITY


@pytest.mark.asyncio
@patch("service.doctor_view.get_services_summary_by_doctor")
@patch("service.doctor_view.get_expected_total_by_doctor")
@patch("service.doctor_view.get_payments_by_doctor")
async def test_open_doctor_menu_no_services_no_payments(
    mock_get_payments,
    mock_get_expected_total,
    mock_get_services_summary
):
    doctor_id = 28

    # Bo‘sh ma'lumotlar
    mock_get_services_summary.return_value = []
    mock_get_expected_total.return_value = 0
    mock_get_payments.return_value = []

    # Soxta update/query
    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    # Context
    context = MagicMock()
    context.user_data = {}

    await open_doctor_menu(mock_update, context, doctor_id)

    # Test qilamiz
    mock_query.edit_message_text.assert_called_once()
    called_args, _ = mock_query.edit_message_text.call_args
    text = called_args[0]

    assert "🚫 Hali xizmat qo‘shilmagan." in text
    assert "💰 Umumiy: 0 so‘m" in text
    assert "✅ To‘langan: 0 so‘m" in text
    assert "❌ Qarzdorlik: 0 so‘m" in text


@pytest.mark.asyncio
@patch("service.doctor_view.get_service_by_id")
@patch("service.doctor_view.get_doctor_id_by_telegram_id")
async def test_select_service_not_found(mock_get_doctor_id, mock_get_service):
    # get_service_by_id hech narsa topmaydi
    mock_get_service.return_value = None
    mock_get_doctor_id.return_value = 28

    # Fake update va context
    mock_query = AsyncMock()
    mock_query.data = "select_service_1"
    mock_query.from_user.id = 123456

    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    context = MagicMock()
    context.user_data = {}

    # Call
    result = await select_service(mock_update, context)

    # Testlar
    mock_query.edit_message_text.assert_called_once_with("❌ Xizmat topilmadi.")
    assert result == ConversationHandler.END  # -1


@pytest.mark.asyncio
@patch("service.doctor_view.get_service_by_id")
@patch("service.doctor_view.get_doctor_id_by_telegram_id")
async def test_select_service_no_doctor_found(mock_get_doctor_id, mock_get_service):
    # Xizmat bor, lekin doktor yo‘q
    mock_get_service.return_value = {"name": "Tekshiruv", "price": 10000}
    mock_get_doctor_id.return_value = None

    # Mock update va query
    mock_query = AsyncMock()
    mock_query.data = "select_service_1"
    mock_query.from_user.id = 123456

    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    # Context
    context = MagicMock()
    context.user_data = {}

    # Chaqarish
    result = await select_service(mock_update, context)

    # Tekshiruvlar
    mock_query.edit_message_text.assert_called_once_with("❌ Doktor aniqlanmadi.")
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_ask_service_quantity_invalid():
    # 0 yoki manfiy son yuboriladi
    mock_message = AsyncMock()
    mock_message.text = "-3"
    update = MagicMock()
    update.message = mock_message

    context = MagicMock()
    context.user_data = {}

    # Funksiyani chaqiramiz
    result = await ask_service_quantity(update, context)

    # Javobni tekshiramiz
    mock_message.reply_text.assert_awaited_once_with("❌ To‘g‘ri son kiriting (musbat butun son).")
    assert result == SELECT_SERVICE_QUANTITY


@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor_with_services(mock_get_all_services):
    # 1. Mocked service list
    mock_get_all_services.return_value = [(1, "Tekshiruv", 10000), (2, "Davolash", 20000)]

    # 2. Fake update and context
    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    # 3. Call the function
    result = await add_service_to_doctor(mock_update, {})

    # 4. Assert edit_message_text called
    mock_query.edit_message_text.assert_called_once()
    args, kwargs = mock_query.edit_message_text.call_args
    assert "➕ Qo‘shiladigan xizmatni tanlang:" in args[0]
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)
    assert result == 1  # SELECT_SERVICE_QUANTITY


@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor_without_services(mock_get_all_services):
    # 1. No services
    mock_get_all_services.return_value = []

    # 2. Fake update and context
    mock_query = AsyncMock()
    mock_update = AsyncMock()
    mock_update.callback_query = mock_query

    # 3. Call the function
    result = await add_service_to_doctor(mock_update, {})

    # 4. Expect error message and END
    mock_query.edit_message_text.assert_called_once_with("❌ Hozircha xizmatlar mavjud emas.")
    assert result == ConversationHandler.END


@pytest.mark.asyncio
@patch("service.doctor_view.get_all_services")
async def test_add_service_to_doctor(mock_get_services):
    # 1. Mock xizmatlar
    mock_get_services.return_value = [
        (1, "Tekshiruv", 10000),
        (2, "Davolash", 15000),
    ]

    # 2. Fake callback query
    mock_query = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    # 3. Function call
    result = await add_service_to_doctor(mock_update, MagicMock())

    # 4. Tekshiruvlar
    mock_query.edit_message_text.assert_called_once()
    called_args, called_kwargs = mock_query.edit_message_text.call_args
    assert "➕ Qo‘shiladigan xizmatni tanlang:" in called_args[0]
    assert isinstance(called_kwargs["reply_markup"], InlineKeyboardMarkup)
    assert result == SELECT_SERVICE_QUANTITY
