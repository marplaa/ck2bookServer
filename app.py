import hashlib
import os
import re
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from pip._vendor import urllib3
from flask import request
import wget
from pathlib import Path
from zipfile import ZipFile

app = Flask(__name__)

if __name__ == '__main__':
    app.run()


@app.route('/get/get_recipe_data_json_get', methods=['GET'])
def get_recipe_data_json_get():
    url = request.args.get('url');
    print(url)
    recipe_data = get_recipe_data(url)

    return jsonify(recipe_data)


def get_recipe_data(url):
    recipe = {"url": url}
    soup = soupify(url)
    content = soup.find("div", {"class": "print__content_left"}).find("p")
    # print(soup.find("div", {"class": "ds-box"}).get_text())

    recipe['title'] = soup.find("a", {"class": "bi-recipe-title"}).getText()
    try:
        recipe['subtitle'] = soup.find("div", {"id": "content"}).find("strong").getText()
    except Exception:
        pass

    recipe['ingredients'] = makelist(soup.find("table", {"class": "print__ingredients"}))

    recipe['recipe_info'] = makelist(soup.find("table", {'id': 'recipe-info'}).extract())
    recipe['text'] = re.sub(r'\s+', ' ', content.get_text('</br>', strip=True)).replace('\n', '')

    # get images

    # soup = soupify(url.replace("/drucken",""))
    # print(soup.find("div", {"class": "recipe-image"}))
    # print(url.replace("/drucken",""))
    # imgs = soup.find("div", {"class": "recipe-image"}).find_all("amp-img")
    image = soup.find("figure").find("img")
    # for image in imgs:

    try:
        recipe['images'] = getImages(url)
    except:
        pass

    recipe['image'] = image.get('src')

    return recipe


def soupify(url):
    if "/drucken/" not in url:
        url = url.replace("/rezepte/", "/rezepte/drucken/")

    http = urllib3.PoolManager()
    response = http.request('GET', url)

    return BeautifulSoup(response.data, 'html.parser')


# todo check if images überhaupt vorhanden sind unter bilderübersicht
def getImages(url):
    url = url.replace("/rezepte/", "/rezepte/bilderuebersicht/")
    http = urllib3.PoolManager()
    response = http.request('GET', url)
    soup = BeautifulSoup(response.data, 'html.parser')
    # print(soup.find("div", {'class': 'recipe-images'}))
    images = soup.find("div", {'class': 'recipe-images'}).findAll('amp-img')
    img_list = []
    # print(images)

    for img in images:
        img_list.append(img.get('src'))

    print(len(img_list))
    # download_images(img_list)

    return img_list


@app.route('/compile/toPdf', methods=['POST'])
def create_tex_file():
    data = request.get_json()
    directory_name = hashlib.md5(bytearray(data['content'], encoding="utf-8")).hexdigest()
    directory_path = Path('temp') / Path(directory_name)

    try:
        directory_path.mkdir()
        (directory_path / 'images').mkdir()

    except FileExistsError:
        pass

    print(Path('/book.txt'))
    print()

    f = open(directory_path / 'book.tex', "w", encoding='utf-8')
    f.write(data['content'])
    f.close()

    download_images(data['images'], directory_path / 'images')

    make_zip(str(directory_path), directory_name)

    # print(data)
    return {'url': request.base_url + '/static/' + directory_name + '.zip'}


def make_zip(directory_path, name):
    # create a ZipFile object
    zip_obj = ZipFile(Path(Path('static') / Path('books') / (name + '.zip')), 'w')
    # Add multiple files to the zip
    for dirname, subdirs, files in os.walk(directory_path):
        zip_obj.write(dirname)
        for filename in files:
            zip_obj.write(os.path.join(dirname, filename))
    # close the Zip File
    zip_obj.close()


def download_images(images, path):
    for image in images:
        name = hashlib.md5(bytearray(image, encoding="ascii")).hexdigest() + '.jpg'
        print(path / name)
        wget.download(image, out=str(path / name))


def makelist(table):
    result = []

    allrows = table.findAll('tr')
    for row in allrows:
        result.append([])
        allcols = row.findAll('td')
        for col in allcols:
            thestrings = []
            thestring = ""
            for thestring in col.stripped_strings:
                thestring = re.sub(r'\s+', ' ', thestring)
                # thestring = thestring.replace('\n', '')
                thestrings.append(thestring)
            thetext = ''.join(thestrings)
            result[-1].append(thetext)
    return result
