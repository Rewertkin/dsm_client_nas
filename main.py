import os
import urllib.parse
import json
import requests
from dotenv import load_dotenv, find_dotenv

class APIError(Exception):
    """Ошибки DSM API"""
    def __init__(self, error_code):
        self.error_code = str(error_code)
        super().__init__(error_code)

    def __str__(self):
        errors_dict = {'100' : 'Unknown error',
                       '101' : 'Invalid parameter',
                       '102' : 'The requested API does not exist',
                       '103' : 'The requested method does not exist',
                       '104' : 'The requested version does not support the functionality',
                       '105' : 'The logged in session does not have permission',
                       '106' : 'Session timeout',
                       '107' : 'Session interrupted by duplicate login'}
        try:
            result = "Ошибка API! " + self.error_code + ' ' + errors_dict[self.error_code]
        except:
            result = 'Ошибка API! Неизвестная ошибка!'
        return result

class NotSession(Exception):
    """ошибка если не передана сессия API"""
    def __init__(self, message = 'Не открыта сессия!'):
        self.message = message
        super().__init__(self.message)


#считываем данные для API
load_dotenv(find_dotenv())
USER = os.getenv('USER')
PASSWORD = os.getenv('PASSWORD')
PATH_SAVE = os.getenv('PATH_SAVE')
ADDR_API = f'http://{os.getenv('ADDR')}:{os.getenv('PORT')}/webapi'

def check_fail_response(response):
    """проверим, что не вурнулись ошибки"""
    if 'error' in response.json().keys():
        raise APIError(str(response.json()['error']['code']))
    return


def logging_api() -> requests.session:
    """запускаем сессию"""
    session = requests.session()
    url = f'{ADDR_API}/auth.cgi?'
    params_logging = {
        'api' : 'SYNO.API.Auth',
        'version' : '2',
        'method' : 'login',
        'account' : {USER},
        'passwd' : {PASSWORD},
        'session' : 'DownloadStation',
        'format' : 'cookie'
    }

    response = session.get(url, params=params_logging, timeout=10)
    response.raise_for_status() #вызываем ошибку requests.exceptions.HTTPError, если ответ не 200
    return session

def logout_api(session):
    """выходим из сессии"""
    if session is None:
        raise NotSession
    url = f'{ADDR_API}/auth.cgi?'
    params_logout = {
        'api' : 'SYNO.API.Auth',
        'version' : '1',
        'method' : 'logout',
        'session' : 'DownloadStation'
    }
    response = session.get(url, params_logout, timeout=10)
    response.raise_for_status() #вызываем ошибку requests.exceptions.HTTPError, если ответ не 200


def get_api_information():
    """получаем информацию об API"""
    url = f'{ADDR_API}/query.cgi?'
    params_inf = {
        'api' : 'SYNO.API.Info',
        'version' : '1',
        'method' : 'query',
        'query' : 'SYNO.API.Auth,SYNO.DownloadStation.Task'
    }
    response = requests.get(url, params=params_inf, timeout=100)
    response.raise_for_status() #вызываем ошибку requests.exceptions.HTTPError, если ответ не 200
    return response.json()

def get_tasks_list(session = None):
    """получаем список текущих задач в Download Station"""
    if session is None:
        raise NotSession
    url = f'{ADDR_API}/DownloadStation/task.cgi?'
    params_list = {
        'api': 'SYNO.DownloadStation.Task',
        'version' : '1',
        'method' : 'list',
        'additional' : 'detail,file'
    }
    response = session.get(url, params = params_list, timeout=100)
    check_fail_response(response)
    return response.json()

def creat_task(session = None, source = None):
    """создание задачи для скачивания"""
    if session is None or source is None:
        raise NotSession
    file_source = urllib.parse.unquote(source)
    add_url = f"{ADDR_API}/DownloadStation/task.cgi"
    add_payload = {
        "api": "SYNO.DownloadStation.Task",
        "version": "1",
        "method": "create",
        "uri": file_source
        }
    response = session.post(add_url,data=add_payload, timeout=10)
    response.raise_for_status()

def prepare_data(data):
    "Подготовка данных для выдачи"
    prepare_list = [task for task in data['data']['tasks'] if task['status'] != 'seeding']
