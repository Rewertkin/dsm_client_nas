import os
from dotenv import load_dotenv, find_dotenv
import qbittorrentapi
import json

load_dotenv(find_dotenv())

with open("config.json", "r", encoding="utf-8") as file:
    config = json.load(file)

QBITTORRENT_HOST = config['addr']
QBITTORRENT_PORT = config['port']
QBITTORRENT_USERNAME = os.getenv('USER')
QBITTORRENT_PASSWORD = os.getenv('PASSWORD')

client = qbittorrentapi.Client(
    host=QBITTORRENT_HOST,
    port=QBITTORRENT_PORT,
    username=QBITTORRENT_USERNAME,
    password=QBITTORRENT_PASSWORD,
)

def add_torrent_from_magnet(magnet, path, tags_add = None):
    if tags_add is None:
        tags_add = []
    try: 
        client.torrents_add(urls=magnet, save_path = path, tags = tags_add)
    except qbittorrentapi.exceptions.APIError as e:
        return "Ошибка API при добавлении торрента"
    except Exception as e:
       return f"Ошибка при добавлении торрента: {e}"
    
    return "Торрент добавлен!"