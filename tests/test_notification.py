import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import patch, MagicMock, AsyncMock, ANY
from database import schedule_notification, send_scheduled_notifications, resend_reminder_notifications, \
    handle_notification_response, delete_notification, mark_notification_confirmed


@patch("database.get_connection")
def test_schedule_notification(mock_get_connection):
    # 1. Mock cursor va connection context managerlari
    mock_cursor = MagicMock()
    mock_conn = MagicMock()

    # 2. get_connection() chaqirilganda context manager tarzida ishlaydi:
    #    with get_connection() as conn → conn = mock_conn
    mock_get_connection.return_value.__enter__.return_value = mock_conn

    # 3. conn.cursor() ham context manager: with conn.cursor() as cur → cur = mock_cursor
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # 4. Funksiyani chaqiramiz
    schedule_notification(doctor_id=1, message="Test notification")

    # 5. SQL bajarilganini tekshiramiz
    assert mock_cursor.execute.called, "❌ SQL execute chaqirilmadi!"
    called_args = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO doctor_service_notifications" in called_args


@pytest.mark.asyncio
@patch("database.get_connection")
async def test_send_scheduled_notifications(mock_get_connection):
    # 1. Fake cursor va connection
    mock_cursor = MagicMock()
    mock_conn = MagicMock()

    # 2. Context manager sozlash
    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # 3. Fake natija — bitta notification
    mock_cursor.fetchall.return_value = [
        (1, 1, "Test xabar", 123456789)
    ]

    # 4. Fake context va bot
    mock_bot = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot = mock_bot

    # 5. Funksiyani chaqiramiz
    await send_scheduled_notifications(mock_context)

    # 6. send_message chaqirilganini tekshiramiz
    mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
@patch("database.get_connection")
async def test_resend_reminder_notifications(mock_get_connection):
    # 🔧 Mock cursor va connection
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # 🔢 Mock bazadan qaytadigan reminderlar
    mock_cursor.fetchall.return_value = [
        (1, 101, "Test xabar", 123456789),  # (notif_id, doctor_id, message, telegram_id)
    ]

    # 🤖 Mock context va bot.send_message
    mock_bot = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot = mock_bot

    # ✅ Funksiyani chaqiramiz
    await resend_reminder_notifications(mock_context)

    # ✅ send_message chaqirilganini tekshiramiz
    assert mock_bot.send_message.called, "❌ send_message chaqirilmadi"
    mock_bot.send_message.assert_called_once()

@pytest.mark.asyncio
@patch("database.get_connection")
async def test_handle_notification_confirm(mock_get_connection):
    # Mock bazaga ulanish
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock update va context
    mock_query = AsyncMock()
    mock_query.data = "confirm_received_1"
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    mock_context = MagicMock()

    # Funksiyani chaqiramiz
    await handle_notification_response(mock_update, mock_context)

    # ✅ UPDATE query bo‘ldi va xabar o‘zgardi
    assert mock_cursor.execute.called
    mock_query.edit_message_text.assert_called_once_with("✅ Xizmat qabul qilindi.")

@pytest.mark.asyncio
async def test_handle_notification_reject():
    # "Yo‘q" bosilganda test
    mock_query = AsyncMock()
    mock_query.data = "reject_received_1"
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_context = MagicMock()

    await handle_notification_response(mock_update, mock_context)

    # ✅ Faqat xabar o‘zgartirilgan
    mock_query.edit_message_text.assert_called_once_with("❌ Xizmat rad etildi.")





@patch("database.get_connection")
def test_delete_notification(mock_get_connection):
    # Mock bazaga ulanish
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Test qilinayotgan funksiya
    delete_notification(notif_id=123)

    # SQL chaqirilganini tekshiramiz
    mock_cursor.execute.assert_called_once_with(
        "DELETE FROM doctor_service_notifications WHERE id = %s", (123,)
    )

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main_bot import send_scheduled_notifications

@pytest.mark.asyncio
@patch("main_bot.get_pending_notifications")
@patch("main_bot.get_doctor_telegram_id")
@patch("main_bot.mark_notification_sent")
async def test_send_scheduled_notifications(mock_mark_sent, mock_get_telegram, mock_get_pending):
    # Mock notifications
    mock_get_pending.return_value = [(1, 10, "Salom Doktor")]
    mock_get_telegram.return_value = 12345678  # Telegram ID

    # Mock context va bot
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    # Call function
    await send_scheduled_notifications(mock_context)

    # ✅ Assertions
    mock_get_pending.assert_called_once()
    mock_get_telegram.assert_called_once_with(10)
    mock_context.bot.send_message.assert_awaited_once_with(
        chat_id=12345678,
        text="📩 Salom Doktor",
        reply_markup=ANY
    )
    mock_mark_sent.assert_called_once_with(1)