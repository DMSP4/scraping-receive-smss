import requests
from bs4 import BeautifulSoup
import time
import redis
from datetime import datetime, timedelta
import threading


redis_host = 'localhost'
redis_port = 6379
redis_db = 0

r = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)


url = 'https://receive-smss.com/'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')


def get_number():
    links = soup.find_all('a', style="text-decoration: none;")
    result = []
    for link in links:
        href = link.get('href')
        aria_label = link.get('aria-label')
        if href and aria_label:
            full_url = f"https://receive-smss.com{href}"
            result.append((full_url, aria_label))
    return result


def get_message_info(link):
    response = requests.get(link, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    messages = soup.find_all('div', class_='row message_details')
    message_info = []
    for message in messages:
        msg_text = message.find('div', class_='col-md-6 msgg').find('span').text.strip()
        sender = message.find('div', class_='col-md-3 senderr').find('a').text.strip()
        time_sent = message.find('div', class_='col-md-3 time').text.strip()
        message_info.append({
            'message': msg_text,
            'sender': sender,
            'time_sent': time_sent
        })
    return message_info


def store_number_info(number, source, status):
    key = f"number:{number}"
    r.hset(key, "source", source)
    r.hset(key, "date_added", datetime.now().isoformat())
    r.hset(key, "last_checked", datetime.now().isoformat())
    r.hset(key, "status", status)


def update_number_status(number, status):
    key = f"number:{number}"
    r.hset(key, "last_checked", datetime.now().isoformat())
    r.hset(key, "status", status)


def check_number_activity(number):
    key = f"number:{number}"
    last_checked = r.hget(key, "last_checked")
    if last_checked:
        last_checked = datetime.fromisoformat(last_checked)
        if datetime.now() - last_checked < timedelta(hours=2):
            update_number_status(number, "active")
        else:
            update_number_status(number, "inactive")


def periodic_check(interval, status):
    while True:
        keys = r.keys("number:*")
        for key in keys:
            number = key.split(":")[1]
            if r.hget(key, "status") == status:
                check_number_activity(number)
        time.sleep(interval)


def main():
    numbers_and_links = get_number()
    all_messages = []
    for link, number in numbers_and_links:
        messages = get_message_info(link)
        all_messages.append({
            'number': number,
            'messages': messages
        })
        store_number_info(number, link, "active")
    print(f"Total number of links and numbers found: {len(numbers_and_links)}")
    for entry in all_messages:
        print(f"Number: {entry['number']}")
        for msg in entry['messages']:
            print(f"Message: {msg['message']}, Sender: {msg['sender']}, Time Sent: {msg['time_sent']}")
        update_number_status(entry['number'], "active")

    # Запуск периодической проверки активных и неактивных номеров
    active_thread = threading.Thread(target=periodic_check, args=(60, "active"))
    inactive_thread = threading.Thread(target=periodic_check, args=(3600, "inactive"))
    active_thread.start()
    inactive_thread.start()


if __name__ == '__main__':
    main()
