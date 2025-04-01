"""реализация телеграм бота для удаленной работы с Nas сервером
Алгоритм работы: 
1. Получаем сообщение где обязательно должна быть строка с magnet ссылкой
2. Собираем данные из сообщения магент ссылка, и если есть: наименование и год
3. Получаем метаданные на основании магнет ссылки, через сервис https://torrentmeta.fly.dev/
4. Все торрент файлы закачки должны лежать в отдельных папочках. На основании метаданных проверяем это, если файлы в торрент файле не в папке:
    4.1. Формируем наименование папки на основании данных п2
    4.2. Если наименование не получилось сформировать, формируем на основании метаданных(наменование торрент файла)
    4.3. Проверяем, что в наименовании папки нет запрещенных символов, если есть удаляем
    4.4. Создаем папку с помощью dsm.creat_folder
5. Создаем задачу dsm.creat_task для скачивания данных

Не сделано: 
1. Статус скачиваемых данны
2. Кеширование данных по файлам на NAS
2. Поиск обложек по наименованию через апи кинопоска
3. Загрузка обложек и описания фильмов в папку с файлом фильме
"""

import dsm
import os
import re
import requests
import telebot
from dotenv import load_dotenv, find_dotenv

def get_metadata(magnet = None):
    """получить метаданные по магнет ссылке"""
    if magnet is None:
        return
    url = 'https://torrentmeta.fly.dev/'
    data_url = {
    'query' : magnet
    }
    response = requests.post(url, data=data_url, timeout=10)
    response.raise_for_status()
    return response.json()

def get_message_data(message_text):
    """ получение данных из сообщения"""
    message_data = {}
    #найдем магнет ссылку
    magnet_start = message_text.find('magnet')
    magnet_finish = message_text[magnet_start:].find('\n') + magnet_start
    message_data['magnet'] = message_text[magnet_start:magnet_finish].strip()

    #найдем название фильма\торрента:
    title_start = message_text.find(":\n") + 2
    title_finish = message_text[title_start:magnet_start].find("\n") + title_start
    title_string = message_text[title_start:title_finish]

    #Извлекает названия и год фильма.
    #match = re.search(r"^(.*?)\s/\s(.*?)\s\[(\d{4}),", title_string)
    match = re.search(r"^(.*?)\s/\s(.*?)(?:\s\(.*?\))?\s\[(\d{4}),", title_string)
    if match:
        message_data['title'] = match.group(1).strip()
        message_data['alternative_title'] = match.group(2).strip()
        message_data['year'] = match.group(3)
    return message_data

def is_file_in_directory(metadata):
    """Проверяет, указана ли папка на верхнем уровне в торренте"""
    #если торрент сразу грузится в папку, то не создаем папку для него
    #если хоть один файл кладется вне папки, то считаем, что он грузится без папки 
    for file in metadata['data']['files']:
        if '/' not in file['path']:
            return False
    return True

def correct_forbidden_characters(folder_name):
    """проверяем и убираем в наименование запрещенные символы"""
    forbidden_characters_regex = r'[<>:"/\\|?*\x00-\x1F]'
    sanitized_name = re.sub(forbidden_characters_regex, '_', folder_name)
    sanitized_name = sanitized_name.lstrip(".").rstrip(".")
    return sanitized_name


load_dotenv(find_dotenv())
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
bot = telebot.TeleBot(TG_BOT_TOKEN)


@bot.message_handler(func=lambda message: True)  # Обрабатывает все текстовые сообщения
def echo_all(message):
    message_data = get_message_data(message.text) #получаем данные из сообщения
    
    if not message_data.get('magnet', False):
        bot.reply_to(message, "Магнет ссылка не найдена!")
        return
    try:
        metadata = get_metadata(message_data.get('magnet')) #получаем метаданные торрента
    except requests.exceptions.HTTPError:
        bot.reply_to(message, "Торрент не найден!")
        return
    
    try:
        bot.reply_to(message, "Подготавливаем torrent к скачиванию...")
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"Ошибка при отправке сообщения: {e}")

    if not is_file_in_directory(metadata): #если нет папки 1 уровня, создаем папку
        
        title = message_data.get('title', False)
        year = message_data.get('year', False)
        if title and year:
            title_folder = title + ' ' + year

        if not title_folder:
            title_folder = metadata["data"]['name']
        correct_forbidden_characters(title_folder)
        try:
            session_FileStation = dsm.logging_api('FileStation')
            dsm.creat_folder(session=session_FileStation, name_new_folder=title_folder)
        except:
            print("Не удалось создать папку " + title_folder)
            title_folder = None #если папка не создалась, всеравно идем дальше
            
        #закрываем сессии при любом случае
        try:
            dsm.logout_api(session_FileStation, 'FileStation')
        except:
            print("Не удалось закрыть сессию FileStation")

    try:   
        destination_folder = None
        if title_folder:
            destination_folder = '/volume1/video/' + title_folder

        session_DownloadStation = dsm.logging_api('DownloadStation')
        dsm.creat_task(session = session_DownloadStation, 
                       source = message_data.get('magnet', None), 
                       destination = destination_folder)
    except:
        print("Не добавилась задача на скачку")
        print("Magnet = " + message_data.get('magnet', None))
        print("Папка: " + title_folder )
        bot.reply_to(message, "Неудалось создать задачу на скачивание!")
        try:
            dsm.logout_api(session_DownloadStation, 'DownloadStation')
        except:
            print("Не удалось закрыть сессию FileStation")
        return

    if title_folder:
        message_folder = title_folder
    else:
        message_folder = 'Стандартная папка'
    bot.reply_to(message, "Торрент добавлен на скачивание! Папка: " + message_folder)


if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
