import aiohttp
import asyncio
from bs4 import BeautifulSoup
import sqlite3
import datetime

SITE_URL = 'https://www.ixbt.com/'
PAGE_URL = lambda year, month, day: f'{SITE_URL}/news/{year}/{month}/{day}'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
}

# Функция для создания таблицы в базе данных SQLite
def create_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS articles
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          title TEXT,
                          pretitle TEXT,
                          contents TEXT,
                          category TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        print("Ошибка при создании таблицы:", e)

# Функция для добавления записи в базу данных SQLite
def insert_article(conn, title, pretitle, contents, category):
    try:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO articles (title, pretitle, contents, category) VALUES (?, ?, ?, ?)''', (title, pretitle, "\n".join(contents), category))
        conn.commit()
    except sqlite3.Error as e:
        print("Ошибка при добавлении записи:", e)

# Основная функция для сохранения данных в базу данных SQLite
def save_to_database(title, pretitle, contents, category):
    conn = sqlite3.connect('articles.db')
    create_table(conn)
    insert_article(conn, title, pretitle, contents, category)
    conn.close()

async def fetch_content(url, session):
    async with session.get(url, headers=headers) as response:
        return await response.text()

# Получить URL-страниц со статьями, вид страницы f'{SITE_URL}/news/{year}/{month}/{day}'

async def get_page_urls(session, start_date, finish_date):
    async with session.get(SITE_URL, headers=headers) as response:
        if response.status == 200:
            page_urls = []
            current_date = start_date
            while current_date <= finish_date:
                year, month, day = current_date.year, str(current_date.month).zfill(2), str(current_date.day).zfill(2)
                page_url = PAGE_URL(year, month, day)
                page_urls.append(page_url)
                current_date += datetime.timedelta(days=1)
            return page_urls
        else:
            print('Ошибка при запросе:', response.status)
            return []

async def get_article_urls(url, session):
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            bodyOfArticle = soup.find_all('li', {'class':'item'})
            return [(SITE_URL + item.find('a').get('href')) for item in bodyOfArticle]
            
        else:
            print('Ошибка при запросе:', response.status)
            return []

async def get_article_content(url, session):
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            title = soup.find('h1').text if soup.find('h1') else 'No title'
            pretitle = soup.find('h4').text if soup.find('h4') else 'No pretitle'
            category = soup.find('a', {'class':'news-tag'}).text if soup.find('a', {'class':'news-tag'}) else 'No category'
            # На странице статей, помимо нужного текста, в тегах <p> есть также и другая бесполезная информация (автор, теги и другие поля)
            # Решение - парсить теги <p> до определённого тега, после которого в тегах <p> идет ненужная информация
            # На странице это тег <meta itemprop="datePublished">

            target_meta_tag = soup.find('meta', {'itemprop': 'datePublished'}) # искомый тег
            contents = []
            current_tag = soup.html.body
            while current_tag != target_meta_tag:
                if current_tag.name == 'p':
                    contents.append(current_tag.text.strip())
                current_tag = current_tag.next_element
            await asyncio.sleep(1)  # Задержка между запросами, иначе ловлю 503 ошибку
            return title, pretitle, contents, category
        else:
            print('Ошибка при запросе:', response.status)
            return None, None, None, None

async def main():
    conn = sqlite3.connect('articles.db')
    async with aiohttp.ClientSession() as session:
        page_urls = await get_page_urls(session, datetime.date(2024, 4, 17), datetime.date(2024, 4, 19))
        for page_url in page_urls:
            article_urls = await get_article_urls(page_url, session)
            for article_url in article_urls:
                title, pretitle, contents, category = await get_article_content(article_url, session)
                if title:
                    save_to_database(title, pretitle, contents, category)
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
