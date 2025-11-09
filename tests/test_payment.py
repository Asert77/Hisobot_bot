import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, CallbackQuery, Message
from telegram.ext import ContextTypes, ConversationHandler

from main_bot import enter_payment, start_payment, ENTER_PAYMENT_AMOUNT, back_button, handle_menu_selection, ADMINS


@pytest.mark.asyncio
@patch("main_bot.add_payment")
async def test_enter_payment_valid(mock_add_payment):
    mock_user = User(id=123, first_name="Test", is_bot=False)
    mock_message = AsyncMock()
    mock_message.from_user = mock_user
    mock_message.text = "50000"
    mock_message.reply_text = AsyncMock()

    update = Update(update_id=1, message=mock_message)
    context = MagicMock()
    context.user_data = {"doctor_id": 5}

    result = await enter_payment(update, context)

    mock_add_payment.assert_called_once_with(None, 50000.0, 5)
    mock_message.reply_text.assert_called_once_with(
        "✅ 50000 so‘m to‘lov saqlandi.", reply_markup=back_button
    )
    assert result == ConversationHandler.END

#
@pytest.mark.asyncio
async def test_enter_payment_invalid():
    mock_message = AsyncMock()
    mock_message.text = "-100"
    mock_message.reply_text = AsyncMock()

    update = Update(update_id=2, message=mock_message)
    context = MagicMock()
    context.user_data = {"doctor_id": 5}

    result = await enter_payment(update, context)

    mock_message.reply_text.assert_called_once_with("❌ Iltimos, to‘g‘ri raqam kiriting.")
    assert result == ConversationHandler.END or result is not None  # U holda qaytadi


# @pytest.mark.asyncio
# async def test_enter_payment_no_doctor():
#     mock_message = AsyncMock()
#     mock_message.text = "10000"
#     mock_message.reply_text = AsyncMock()
#
#     update = Update(update_id=3, message=mock_message)
#     context = MagicMock()
#     context.user_data = {}  # doctor_id yo‘q
#
#     result = await enter_payment(update, context)
#
#     mock_message.reply_text.assert_called_once_with("❌ Doktor aniqlanmadi.")
#     assert result == ConversationHandler.END
#
#
@pytest.mark.asyncio
async def test_start_payment_valid_doctor_id():
    mock_query = AsyncMock()
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()

    update = Update(update_id=4, callback_query=mock_query)
    context = MagicMock()
    context.user_data = {"doctor_id": 10}

    result = await start_payment(update, context)

    mock_query.edit_message_text.assert_called_once_with("💳 To‘lov summasini kiriting:")
    assert context.user_data["doctor_id"] == 10
    assert result == ENTER_PAYMENT_AMOUNT
#
#
# @pytest.mark.asyncio
# async def test_start_payment_no_doctor_id():
#     mock_query = AsyncMock()
#     mock_query.answer = AsyncMock()
#     mock_query.edit_message_text = AsyncMock()
#
#     update = Update(update_id=5, callback_query=mock_query)
#     context = MagicMock()
#     context.user_data = {}  # No doctor_id
#
#     result = await start_payment(update, context)
#
#     mock_query.edit_message_text.assert_called_once_with("❌ Doktor aniqlanmadi.")
#     assert result == ConversationHandler.END



@pytest.mark.asyncio
async def test_add_debt_valid():
    mock_query = AsyncMock()
    mock_query.data = "add_debt"
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()

    mock_query.from_user.id = list(ADMINS)[0]  # ✅ admin ID

    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    mock_context = MagicMock()
    mock_context.user_data = {"doctor_id": 1}

    await handle_menu_selection(mock_update, mock_context)

    mock_query.edit_message_text.assert_called_once_with("💸 Qarz miqdorini kiriting:")

@pytest.mark.asyncio
async def test_cancel_close_debt():
    mock_query = AsyncMock()
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    mock_query.data = "cancel_close_debt"
    mock_query.from_user.id = list(ADMINS)[0]  # ✅ admin ID


    update = Update(update_id=1235, callback_query=mock_query)
    context = MagicMock()
    context.user_data = {}

    from main_bot import handle_menu_selection
    await handle_menu_selection(update, context)

    mock_query.edit_message_text.assert_called_once_with("❌ Qarzni yopish bekor qilindi.")

from unittest.mock import patch

@pytest.mark.asyncio
@patch("main_bot.close_debts")
async def test_confirm_close_debt(mock_close_debts):
    mock_query = AsyncMock()
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    mock_query.data = "confirm_close_debt"
    mock_query.from_user.id = list(ADMINS)[0]  # ✅ admin ID


    update = Update(update_id=1236, callback_query=mock_query)
    context = MagicMock()
    context.user_data = {
        "doctor_id": 1,
        "debt_total": 20000
    }

    from main_bot import handle_menu_selection, ConversationHandler
    result = await handle_menu_selection(update, context)

    mock_close_debts.assert_called_once_with(1, 20000)
    mock_query.edit_message_text.assert_called_once_with("✅ Qarzdorlik muvaffaqiyatli yopildi.")
    assert result == ConversationHandler.END
