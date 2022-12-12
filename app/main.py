# app/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Union
from tqdm import tqdm
from fastapi.openapi.utils import get_openapi

from app.db import database, User

from bs4 import BeautifulSoup
import requests
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin, urlparse
import re
import requests
from urllib.parse import urlsplit
from collections import deque
import pandas as pd
from tld import get_fld



def is_valid(url):
    """
    Checks whether `url` is a valid URL.
    """
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)





app = FastAPI()

class Item(BaseModel):
    url: str



@app.get("/get_free_proxy")
async def get_proxy():
    main_url  = "https://free-proxy-list.net/"
    page = requests.get(main_url)
    soup = BeautifulSoup(page.content, "html.parser")
    content_html = soup.findAll("div", class_="table-responsive fpl-list")[0]
    df = pd.read_html(str(content_html))[0]
    df = df.loc[df['Google']=='yes']
    df['Last Checked'] = df['Last Checked'].str.replace(' ago', '', regex=True)
    searchfor = ['min', 'secs']
    df = df[df['Last Checked'].str.contains('|'.join(searchfor))]
    df = df[df['Last Checked'].str.contains('hour')==False]
    df = df.drop(columns=['Last Checked'])
    return df.iloc[0].to_json()

@app.post("/get_all_images/")
async def get_all_images(item: Item):
    """
    Returns all image URLs on a single `url`
    """

    soup = bs(requests.get(item.url).content, "html.parser")
    urls = []
    for img in tqdm(soup.find_all("img"), "Extracting images"):
        img_url = img.attrs.get("src")
        if not img_url:
            # if img does not contain src attribute, just skip
            continue
        # make the URL absolute by joining domain with the URL that is just extracted
        img_url = urljoin(item.url, img_url)
        # remove URLs like '/hsts-pixel.gif?c=3.2.5'
        try:
            pos = img_url.index("?")
            img_url = img_url[:pos]
        except ValueError:
            pass
        # finally, if the url is valid
        if is_valid(img_url):
            urls.append(img_url)
    return urls




@app.post("/get_fav_icon/")
async def get_fav_icon(item: Item):
    """
    Returns the url of the favicon of a single `url`
    """
    if 'http' not in item.url:
        item.url = 'http://' + item.url
    page = requests.get(item.url)
    soup = BeautifulSoup(page.text, features="lxml")
    icon_link = soup.find("link", rel="shortcut icon")

    parsed = urlparse(item.url)
    # 👇️ ParseResult(scheme='https', netloc='example.com', path='/images/wallpaper.jpg', params='', query='', fragment='')
    base = parsed.netloc
    if icon_link is None:
        icon_link = soup.find("link", rel="icon")
    if icon_link is None:
        return item.url + '/favicon.ico'
    return base + icon_link["href"]



@app.post("/get_all_urls/")
async def get_all_urls(item: Item):
    """
    Returns all urls of a single `url`
    """
    reqs = requests.get(item.url)
    soup = BeautifulSoup(reqs.text, 'html.parser')

    urls = []
    for link in soup.find_all('a'):
        urls.append(link.get('href'))

    return urls





@app.post("/extract_emails_from/")
async def extract_emails_from(item: Item):
    """
    Returns all emails found on a website `url`
    """

    if "https://" in item.url:
        item.url = item.url
    else:
        item.url = "https://"+ item.url


    unscraped_url = deque([item.url])
    scraped_url = set()
    list_emails = set()

    while len(unscraped_url):
        url = unscraped_url.popleft()
        scraped_url.add(url)
        parts = urlsplit(url)

        base_url = "{0.scheme}://{0.netloc}".format(parts)

        if '/' in parts.path:
            part = url.rfind("/")
            path = url[0:part + 1]
        else:
            path = url

        print("Searching for Emails in  %s" % url)
        try:
            response = requests.get(url)
        except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError, requests.exceptions.InvalidURL):
            continue
        new_emails = ((re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", response.text, re.I)))
        list_emails.update(new_emails)
        soup = BeautifulSoup(response.text, 'lxml')
        print("Email Extracted: " + str(len(list_emails)))
        for tag in soup.find_all("a"):
            if "href" in tag.attrs:
                weblink = tag.attrs["href"]
            else:
                weblink = ""
            if weblink.startswith('/'):
                weblink = base_url + weblink
            elif not weblink.startswith('https'):
                weblink = path + weblink
            if base_url in weblink:
                if ("contact" in weblink or "Contact" in weblink or "About" in weblink or "about" in weblink or 'CONTACT' in weblink or 'ABOUT' in weblink or 'contact-us' in weblink):
                    if not weblink in unscraped_url and not weblink in scraped_url:
                        unscraped_url.append(weblink)
    url_name = "{0.netloc}".format(parts)
    col = "emails"
    df = pd.DataFrame(list_emails, columns=[col])
    s = get_fld(base_url)
    df = df[df[col].str.contains(s) == True]

    return df.to_json()



@app.on_event("startup")
async def startup():
    if not database.is_connected:
        await database.connect()
    # create a dummy entry
    await User.objects.get_or_create(email="test@test.com")


@app.on_event("shutdown")
async def shutdown():
    if database.is_connected:
        await database.disconnect()



    title="",
    description="Octopus is an API that provides powerful features to help make web scraping easier",
    version="0.0.1",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Ahmed Jabrane",
        "email": "its.jabrane.ahmed@gmail.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Octopus",
        version="1.2.0",
        description="Octopus is an API that provides powerful features to help make web scraping easier",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://s3.us-west-2.amazonaws.com/secure.notion-static.com/a7801c26-182a-4a8a-82fd-fe7b3c50183a/Octopus.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=AKIAT73L2G45EIPT3X45%2F20221212%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20221212T150037Z&X-Amz-Expires=86400&X-Amz-Signature=f46da0634b0b928aefe0b371f32f478ab6a4aba36d5cfde62d6324d276f9695c&X-Amz-SignedHeaders=host&response-content-disposition=filename%3D%22Octopus.png%22&x-id=GetObject"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi