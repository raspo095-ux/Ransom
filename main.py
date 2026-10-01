import asyncio
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatMemberStatus
from aiogram.types import FSInputFile, ChatPermissions

# ------------------------------------------------------------------
# УКАЖИ СВОЙ ТОКЕН ОТ BOTFATHER
BOT_TOKEN = "8885799794:AAG57dwHa1IDTtUo131jktXqEubh_LAveNw"
# ------------------------------------------------------------------

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Переменные для отслеживания состояния
stop_active = False
violator_id = None
dm_message_count = 0
timer_task = None
active_chat_id = None


# 1. Обработка сообщений в ЛС от нарушителя
@dp.message(F.chat.type == "private")
async def process_dm_message(message: types.Message):
    global violator_id, dm_message_count, timer_task, active_chat_id

    # Если пишет именно тот, кто нарушил
    if violator_id and message.from_user.id == violator_id:
        dm_message_count += 1
        remaining = 10 - dm_message_count

        if remaining > 0:
            await message.answer(f"Принято! Осталось написать: {remaining}")
        else:
            # Успел написать 10 сообщений
            if timer_task:
                timer_task.cancel()  # Отменяем таймер наказания

            # Размучиваем пользователя в чате
            try:
                await bot.restrict_chat_member(
                    chat_id=active_chat_id,
                    user_id=violator_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                    ),
                )
            except Exception as e:
                print(f"Ошибка при размуте: {e}")

            await message.answer("Вы успели! Угроза ликвидирована. Вы разблокированы в чате.")

            # Сбрасываем состояние
            violator_id = None
            dm_message_count = 0
            active_chat_id = None


# 2. Обработка сообщений в группах / чатах
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def process_group_message(message: types.Message):
    global stop_active, violator_id, dm_message_count, timer_task, active_chat_id

    if message.from_user.is_bot:
        return

    # Если уже идет проверка нарушителя, игнорируем новые знаки стоп
    if violator_id is not None:
        return

    # ЕСЛИ ДЕЙСТВУЕТ РЕЖИМ «СТОП» И КТО-ТО НАПИСАЛ
    if stop_active:
        stop_active = False
        violator_id = message.from_user.id
        active_chat_id = message.chat.id
        dm_message_count = 0

        # Мутим пользователя в чате
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=violator_id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await message.reply(
                f"🚨 {message.from_user.full_name} нарушил порядок! Ransom отправил инструкцию в ЛС!"
            )

            # Отправка видео и инструкции в ЛС нарушителю
            video = FSInputFile("ransom.mp4")
            await bot.send_video(
                chat_id=violator_id,
                video=video,
                caption="ВЫ ЗАМЕЧЕНЫ В НАРУШЕНИИ ПРАВИЛ ПОРЯДКА!\n\n"
                        "Вы должны написать 10 сообщений прямо сюда.\n"
                        "Если таймер закончится (60 сек) — будете ликвидированы!",
            )

            # Запускаем таймер на 60 секунд
            timer_task = asyncio.create_task(
                punish_timer(message.chat.id, violator_id)
            )

        except Exception as e:
            await message.reply(f"Не удалось выдать мут. Проверьте права бота (нужен бан/мут): {e}")
            violator_id = None
            active_chat_id = None

        return

    # ШАНС НА ЗАПУСК ЗНАКА «СТОП» (сейчас стоит 10%, т.е. random от 1 до 10 == 1)
    if random.randint(1, 10) == 1 and not stop_active:
        stop_active = True
        await message.answer("🛑 **СТОП!** Все замрите и молчите 30 секунд!")

        await asyncio.sleep(30)

        # Если никто не написал за 30 секунд
        if stop_active:
            stop_active = False
            await message.answer("👍")


# 3. Функция таймера наказания (если не успел)
async def punish_timer(chat_id, user_id):
    global violator_id, dm_message_count, active_chat_id
    await asyncio.sleep(60)

    # Если таймер истек, а пользователь не написал 10 сообщений
    if violator_id == user_id and dm_message_count < 10:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="Время вышло! Вы ликвидированы. Мут установлен на 5 минут.",
            )
        except Exception:
            pass

        # Мут на 5 минут (300 секунд)
        until_date = int(asyncio.get_event_loop().time()) + 300
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
        except Exception as e:
            print(f"Ошибка при выдаче 5-минутного мута: {e}")

        violator_id = None
        dm_message_count = 0
        active_chat_id = None


async def main():
    print("Бот Ransom запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
