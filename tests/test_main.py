import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY, mock_open
from main_bot import start, handle_menu_selection, NAME
import main_bot

# @pytest.mark.asyncio
# async def test_start_admin_with_message():
#     user = MagicMock()
#     user.id = 123456789  # Admin ID
#     user.username = "admin"
#
#     message = AsyncMock()
#     message.from_user = user
#
#     update = MagicMock()
#     update.message = message
#     update.callback_query = None
#
#     context = MagicMock()
#
#     await start(update, context)
#
#     message.reply_text.assert_called_once()
#     assert "🏠 Boshqaruv menyusi:" in message.reply_text.call_args[0][0]
#
#
# @pytest.mark.asyncio
# async def test_start_non_admin_user():
#     # ❌ Admin bo'lmagan foydalanuvchi
#     user = MagicMock()
#     user.id = 123456789  # bu ID ADMINSda yo‘q bo‘lishi kerak
#     user.username = "testuser"
#     user.full_name = "Test User"
#
#     # 🔄 Mock message
#     message = AsyncMock()
#     message.from_user = user
#
#     # 🔄 Mock update
#     update = MagicMock()
#     update.message = message
#     update.callback_query = None
#
#     # 🔄 Mock context
#     context = MagicMock()
#
#     # ⚙️ Test qilinayotgan funksiya
#     await start(update, context)
#
#     # ✅ 2 marta chaqirilgan bo'lishi kerak
#     assert message.reply_text.call_count == 2
#
#     # ✅ Xabar matnlarini tekshiramiz
#     first_call_msg = message.reply_text.call_args_list[0][0][0]
#     second_call_msg = message.reply_text.call_args_list[1][0][0]
#
#     assert "Telegram ID" in first_call_msg
#     assert "xizmatlar bo‘yicha bildirishnomalar" in second_call_msg
#
#
# @pytest.mark.asyncio
# @patch("main_bot.get_all_doctors", return_value=[])
# async def test_handle_menu_selection_list_doctors_no_data(mock_get_all_doctors):
#     query = AsyncMock()
#     query.data = "list_doctors"
#     query.from_user.id = 123456789  # admin ID
#     query.edit_message_text = AsyncMock()
#
#     update = MagicMock()
#     update.callback_query = query
#
#     context = MagicMock()
#     context.user_data = {}
#
#     # 👇 ADMINS ni vaqtincha patch qilish
#     with patch("main_bot.ADMINS", [123456789]):
#         await handle_menu_selection(update, context)
#
#     # ✅ Tekshiruv
#     query.edit_message_text.assert_called_with("📄 Doktorlar yo‘q.", reply_markup=ANY)
#
#
# @pytest.mark.asyncio
# @patch("main_bot.ADMINS", [1111])
# async def test_handle_menu_selection_add_doctor():
#     # 🔧 Callback query
#     mock_query = AsyncMock()
#     mock_query.data = "add_doctor"
#     mock_query.from_user.id = 1111
#     mock_query.edit_message_text = AsyncMock()
#
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#
#     mock_context = MagicMock()
#     mock_context.user_data = {}
#
#     # ✅ Funksiyani chaqiramiz
#     result = await handle_menu_selection(mock_update, mock_context)
#
#     # 🔍 Natija va xabarni tekshiramiz
#     mock_query.edit_message_text.assert_called_once_with("🧾 Doktorning ismini yuboring:")
#     assert result == NAME
#
#
# @pytest.mark.asyncio
# @patch("main_bot.ADMINS", [1111])
# @patch("main_bot.start_report", new_callable=AsyncMock)
# async def test_handle_menu_selection_report_main(mock_start_report):
#     # 🔧 Callback query
#     mock_query = AsyncMock()
#     mock_query.data = "report_main"
#     mock_query.from_user.id = 1111
#     mock_query.answer = AsyncMock()
#
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#
#     mock_context = MagicMock()
#     mock_context.user_data = {}
#
#     # 🔧 return value
#     mock_start_report.return_value = "mocked_response"
#
#     # ✅ Funksiyani chaqiramiz
#     result = await handle_menu_selection(mock_update, mock_context)
#     mock_start_report.assert_awaited_once_with(mock_update, mock_context)
#     assert result == "mocked_response"
#
#
# @pytest.mark.asyncio
# @patch("main_bot.ADMINS", [1234])
# @patch("main_bot.open_doctor_menu", new_callable=AsyncMock)
# async def test_handle_menu_selection_doctor_id(mock_open_doctor_menu):
#     # 🔧 Callback query soxta
#     mock_query = AsyncMock()
#     mock_query.data = "doctor_1"
#     mock_query.from_user.id = 1234
#     mock_query.answer = AsyncMock()
#
#     # 🔧 Update va Context
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#     mock_context = MagicMock()
#     mock_context.user_data = {}
#
#     # ✅ Test qilinayotgan funksiya
#     result = await handle_menu_selection(mock_update, mock_context)
#
#     # 🔍 Tekshiruvlar
#     assert mock_context.user_data["doctor_id"] == 1
#     mock_open_doctor_menu.assert_awaited_once_with(mock_update, mock_context, 1)
#     assert result is None
#
# @pytest.mark.asyncio
# @patch("main_bot.get_all_services", return_value=[(1, "Tilla", 10000)])
# @patch("main_bot.ADMINS", [1234])
# async def test_handle_menu_selection_services_with_data(mock_get_services):
#     # Callback query va update
#     mock_query = AsyncMock()
#     mock_query.data = "services"
#     mock_query.from_user.id = 1234
#     mock_query.answer = AsyncMock()
#
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#     mock_context = MagicMock()
#
#     # Run
#     await handle_menu_selection(mock_update, mock_context)
#
#     # Tekshirish
#     mock_query.edit_message_text.assert_awaited_once()
#
# @patch("main_bot.get_all_services", return_value=[])
# @patch("main_bot.ADMINS", [1234])
# @pytest.mark.asyncio
# async def test_handle_menu_selection_services_empty(mock_get_services):
#     mock_query = AsyncMock()
#     mock_query.data = "services"
#     mock_query.from_user.id = 1234
#     mock_query.answer = AsyncMock()
#
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#     mock_context = MagicMock()
#
#     await handle_menu_selection(mock_update, mock_context)
#
#     mock_query.edit_message_text.assert_awaited_once()
#     args, kwargs = mock_query.edit_message_text.call_args
#     assert "hech qanday xizmat yo‘q" in str(kwargs["reply_markup"]).lower()
#
# @pytest.mark.asyncio
# @patch("main_bot.delete_service_by_id")
# async def test_handle_menu_selection_delete_service(mock_delete_service, monkeypatch):
#     # ✅ ADMINS ro‘yxatini test uchun o‘zgartiramiz
#     monkeypatch.setattr(main_bot, "ADMINS", [1234])
#
#     mock_query = AsyncMock()
#     mock_query.data = "delete_service_1"
#     mock_query.from_user.id = 1234
#     mock_query.answer = AsyncMock()
#
#     mock_update = MagicMock()
#     mock_update.callback_query = mock_query
#     mock_context = MagicMock()
#
#     await handle_menu_selection(mock_update, mock_context)
#
#     mock_delete_service.assert_called_once_with(1)
#     mock_query.edit_message_text.assert_awaited_with(
#         "🗑 Xizmat o‘chirildi. ✅",
#         reply_markup=ANY
#     )


@pytest.mark.asyncio
@patch("main_bot.get_service_by_id")
async def test_select_global_service_valid(mock_get_service):
    # Mock service
    mock_get_service.return_value = {"name": "Xizmat A", "price": 10000}

    # Mocks
    mock_query = AsyncMock()
    mock_query.data = "select_123"
    mock_context = MagicMock()
    mock_context.user_data = {}
    mock_update = MagicMock(callback_query=mock_query)

    result = await main_bot.select_global_service(mock_update, mock_context)

    mock_query.answer.assert_awaited_once()
    mock_get_service.assert_called_once_with(123)
    mock_query.edit_message_text.assert_awaited_once_with("📦 Xizmat A sonini kiriting:")
    assert mock_context.user_data["selected_service_id"] == 123
    assert mock_context.user_data["selected_service_name"] == "Xizmat A"
    assert mock_context.user_data["selected_service_price"] == 10000
    assert result == 1

@pytest.mark.asyncio
@patch("main_bot.get_service_by_id")
async def test_select_global_service_not_found(mock_get_service):
    mock_get_service.return_value = None

    mock_query = AsyncMock()
    mock_query.data = "select_999"
    mock_context = MagicMock()
    mock_context.user_data = {}
    mock_update = MagicMock(callback_query=mock_query)

    from telegram.ext import ConversationHandler
    result = await main_bot.select_global_service(mock_update, mock_context)

    mock_query.answer.assert_awaited_once()
    mock_query.edit_message_text.assert_awaited_once_with("❌ Xizmat topilmadi.")
    assert result == ConversationHandler.END

from main_bot import handle_service_confirmation

@pytest.mark.asyncio
@patch("main_bot.get_notification_doctor_id")
@patch("main_bot.get_doctor_telegram_id")
@patch("main_bot.mark_notification_confirmed")
async def test_handle_service_confirmation_accepted(mock_mark, mock_get_telegram, mock_get_doctor_id):
    mock_get_doctor_id.return_value = 10
    mock_get_telegram.return_value = 12345678

    mock_query = AsyncMock()
    mock_query.data = "confirm_received_1"
    mock_query.from_user.id = 12345678

    mock_update = MagicMock(callback_query=mock_query)
    mock_context = MagicMock()

    await handle_service_confirmation(mock_update, mock_context)

    mock_query.answer.assert_awaited_once()
    mock_mark.assert_called_once_with(1)
    mock_query.edit_message_text.assert_awaited_once_with("✅ Qabul qilindi. Rahmat!")