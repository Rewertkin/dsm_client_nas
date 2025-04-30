import os
import re
import json
import requests
import telebot
from dotenv import load_dotenv, find_dotenv
import kinopoisk_api as kp
import qbittorrent_client as qb

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
    message_data = {
        'magnet': None,
        'title': None,
        'alternative_title': None,
        'year': None,
        'season': None # Добавляем поле для сезона
    }
    # найдем магнет ссылку
    magnet_start = message_text.find('magnet')
    if magnet_start != -1:
        magnet_end_newline = message_text.find('\n', magnet_start)
        if magnet_end_newline == -1:
            magnet_finish = len(message_text)
        else:
            magnet_finish = magnet_end_newline
        message_data['magnet'] = message_text[magnet_start:magnet_finish].strip()

    # найдем строку с названием фильма/торрента:
    first_line_end = message_text.find(":\n")
    if first_line_end == -1:
        return message_data

    title_start = first_line_end + 2
    title_finish_newline = message_text.find("\n", title_start)
    if title_finish_newline == -1:
        if magnet_start != -1:
            title_finish = magnet_start
        else:
            title_finish = len(message_text)
    else:
        title_finish = title_finish_newline

    title_string = message_text[title_start:title_finish].strip()

    # --- Парсинг строки заголовка ---

    # Сначала пытаемся найти основной формат: Название / Альт.Название ... [Год,...]
    match_full = re.search(r"^(.*?)\s*/\s*([^/([]+)\s*.*?\[(\d{4})[-,]", title_string)

    if match_full:
        message_data['title'] = match_full.group(1).strip()
        message_data['alternative_title'] = match_full.group(2).strip()
        message_data['year'] = match_full.group(3)
    else:
        # Если не нашли полный формат, ищем упрощенный: Название ... [Год,...]
        match_simple = re.search(r"^(.*?)\s*\[(\d{4})[-,]", title_string)
        if match_simple:
            raw_title = match_simple.group(1).strip()
            # Убираем возможное имя режиссера в скобках в конце названия
            # (скобка должна быть последним элементом перед пробелом и [Год...])
            message_data['title'] = re.sub(r"\s+\([^)]*\)\s*$", "", raw_title).strip()
            # alternative_title остается None
            message_data['year'] = match_simple.group(2)
        else:
            # Если и это не сработало, берем всю строку как название
            message_data['title'] = title_string
            print(f"Warning: Could not parse title/year from string: '{title_string}'")
            # Остальные поля (year, season, alternative_title) остаются None

    # --- Поиск информации о сезоне ПОСЛЕ основного парсинга ---
    # Ищем в оригинальной строке заголовка (title_string), так как там может быть больше информации
    if message_data['year']:
        # Искать сезон имеет смысл только если нашли год (т.е. парсинг был успешным)
        season_match_sXX = re.search(r'\bS(\d+)\b', title_string, re.IGNORECASE)
        if season_match_sXX:
            message_data['season'] = season_match_sXX.group(1) # Забираем только номер

        # Вариант 2: Ищем "Сезон(ы)/Season(s)" и захватываем ТОЛЬКО цифры/диапазоны/перечисления после
        elif not message_data['season']: # Искать только если еще не нашли
            # Ищем "Сезон/Season", двоеточие (?), пробелы, а затем группу цифр/запятых/дефисов/пробелов
            season_match_word = re.search(
                r'(?:Сезон(?:ы)?|Season(?:s)?)\s*[:]?\s*([\d,\s-]+(?:\s*-\s*\d+)?)\b',
                title_string,
                re.IGNORECASE
            )
            if season_match_word:
                # Очищаем результат от лишних пробелов и знаков препинания по краям
                season_info = season_match_word.group(1).strip().rstrip(',.-')
                message_data['season'] = season_info

        # Вариант 3: Ищем числа/диапазоны, за которыми идет слово "сезон(а/ы)"
        elif not message_data['season']: # Искать только если еще не нашли
            season_match_num_season = re.search(
                r'\b([\d,\s-]+(?:\s*-\s*\d+)?)\s+(?:сезон|сезона|сезоны)\b',
                title_string,
                re.IGNORECASE
            )
            if season_match_num_season:
                season_info = season_match_num_season.group(1).strip().rstrip(',.-')
                message_data['season'] = season_info

    # Если title все еще содержит информацию о сезоне после альтернативного названия,
    # попробуем ее убрать (но это может быть рискованно и убрать нужное)
    # Пример: "Клан Сопрано / The Sopranos / Полные сезоны: ..." -> "Клан Сопрано / The Sopranos"
    # Делаем это только если есть alternative_title
    # if message_data['alternative_title'] and message_data['title']:
    #     # Ищем "/ " после alternative_title в исходной строке title_string
    #     alt_title_end_index = title_string.find(message_data['alternative_title']) + len(message_data['alternative_title'])
    #     # Если после альт. названия есть " / ", обрезаем title до этого момента
    #     # Эта логика сложная и может не всегда работать, пока оставим title как есть после первой регулярки.

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

with open("config.json", "r", encoding="utf-8") as file_json:
    config = json.load(file_json)

WHITELIST = config["allowed_users"]

@bot.message_handler(func=lambda message: True)  # Обрабатывает все текстовые сообщения  

def echo_all(message):

    user_id = message.from_user.id
    if user_id not in WHITELIST:
        bot.reply_to(message, "❌ Извините, у вас нет доступа к этому боту.")
        print(f"Доступ запрещен для {user_id}")
        return
    
    try:
        bot.reply_to(message, "Анализируем сообщение...")
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"Ошибка при отправке сообщения: {e}")

    message_data = get_message_data(message.text) #получаем данные из сообщения
    kp_id = kp.get_id_kinopoisk(message_data)

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

    #подготавливаем путь для скачивания
    tags_add = []
    title_folder = ''
    if not is_file_in_directory(metadata): 
    #если нет папки 1 уровня в торренте, формируем ее название
        title = message_data.get('title', False)
        year = message_data.get('year', False)
        if title and year:
            title_folder = f'{title} ({year})'

        if not title_folder:
            title_folder = metadata["data"]['name']

        if kp_id > 0:
            title_folder = title_folder + '.' + 'kp' + str(kp_id)
        correct_forbidden_characters(title_folder)
    else:
    #если папка есть, нам надо будет ее переимновать на пост обработке
    #для этого добавим тег, которым пометит скачанную папку скрипт
        if kp_id > 0:
            tags_add = ['kp' + str(kp_id)]

    if kp_id > 0:
        if message_data.get('season', False):
            path_download = config['serials_path']
        else:
            path_download = config['movies_path']
    else:
        path_download = config['default_path']

    if title_folder is not None:
        path_download = path_download + '/' + title_folder

    #добавляем задачу на скачку
    try:
        result_string = qb.add_torrent_from_magnet(message_data.get('magnet'), path_download, tags_add = tags_add)
        bot.reply_to(message, result_string + f" Папка: {path_download}")
    except:
        bot.reply_to(message, "Не удалось добавить торрент!")

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
