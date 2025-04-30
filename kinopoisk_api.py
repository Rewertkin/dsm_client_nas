'''Модуль для работы с Кинопоиск API'''
import os
import requests
from dotenv import load_dotenv, find_dotenv


def get_id_kinopoisk(message_data):
    '''Получить id кинопоиска'''
    if message_data['year'] is None or message_data['title'] is None:
        return 0
    
    load_dotenv(find_dotenv())
    KINOPOISK_API= os.getenv("KINOPOISK_API")
    try: 
        name = message_data['title']
        url = f"https://api.kinopoisk.dev/v1.4/movie/search?page=1&limit=10&query={name}"

        headers = {"accept": "application/json",
                "X-API-KEY": KINOPOISK_API }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except:
        return 0
    
    is_series = False #определяем идентификатор сериала
    if message_data['season'] is not None:
        is_series = True

    data_kinopoisk = response.json()['docs']
    data_film = [docs for docs in data_kinopoisk if docs['year'] == int(message_data['year'])
                 and docs['isSeries'] == is_series]

    if len(data_film) == 1:
        return data_film[0]['id']
  
    data_film = [docs for docs in data_kinopoisk if docs['alternativeName'] == message_data['alternative_title']]

    if len(data_film) == 1:
        return data_film[0]['id']

    return 0

