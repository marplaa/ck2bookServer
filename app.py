import hashlib
import os
import re
import subprocess
import urllib3
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from flask import request
import wget
from pathlib import Path
from zipfile import ZipFile
from shutil import move
from PIL import Image, ImageFilter, ImageEnhance
import logging

app = Flask(__name__)

if __name__ == '__main__':
    app.run()

logging.basicConfig(filename='log.log', level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')

logging.info('Starting...')



@app.route('/test')
def test():
    return "OK"


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

    recipe['image'] = recipe['images'][0]

    return recipe


def soupify(url):
    if "/drucken/" not in url:
        url = url.replace("/rezepte/", "/rezepte/drucken/")

    http = urllib3.PoolManager()
    response = http.request('GET', url)

    return BeautifulSoup(response.data, 'html.parser')


# todo check if images überhaupt vorhanden sind unter bilderübersicht
def getImages(url):
    logging.info('retrieving images...')
    url = url.replace("/rezepte/", "/rezepte/bilderuebersicht/")
    http = urllib3.PoolManager()

    img_list = []
    try:
        logging.info("getting images from url: " + url)
        response = http.request('GET', url)

        soup = BeautifulSoup(response.data, 'html.parser')
        # print(soup.find("div", {'class': 'recipe-images'}))
        images = soup.find("div", {'class': 'recipe-images'}).findAll('amp-img')
        for img in images:
            image = re.sub(r'/crop-[0-9x]*/', '/crop-960x640/', img.get('src'))
            img_list.append(image)

    except Exception as ex:
        print(ex.args)
        logging.error('error while getting images')



    # print(images)




    # download_images(img_list)

    return img_list


@app.route('/compile/toPdf', methods=['POST'])
def create_tex_file():
    data = request.get_json()
    file_id = hashlib.md5(bytearray(data['content'], encoding="utf-8")).hexdigest()
    directory_path = Path('temp') / Path(file_id)

    try:
        directory_path.mkdir()
        (directory_path / 'images').mkdir()

    except FileExistsError:
        pass

    f = open(directory_path / (file_id + '.tex'), "w", encoding='utf-8')
    f.write(data['content'])
    f.close()

    download_images(data['images'], directory_path / 'images')

    # make_zip(str(directory_path), file_id)

    ok = compile_latex(directory_path, file_id)


    if True: # ok:
        logging.info('moving pdf file to static...')
        try:
            move(str(directory_path) / Path(file_id + '.pdf'), Path('static/books') / (file_id + '.pdf'))
        except:
            pass
    else:
        logging.error('error while compiling texfile')


    # print(data)
    return {'ok': ok, 'url': request.url_root + 'static/books/' + file_id + '.pdf'}


def compile_latex(directory, file_id):
    ok = False
    if not subprocess.run(["/usr/bin/lualatex", file_id + '.tex'], cwd=str(directory)).returncode:
        ok = not subprocess.run(["/usr/bin/lualatex", file_id + '.tex'],
                                cwd=str(directory)).returncode

    return ok


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
    logging.info("downloading images to:" + str(path))
    for image in images:
        hash = hashlib.md5(bytearray(image['url'], encoding="ascii")).hexdigest()
        orig_name = hash + '.jpg'
        logging.info('downloading: ' + str(image['url']))
        try:
            wget.download(image['url'], out=str(path / orig_name))
        except Exception as ex:
            logging.error(ex.args)

        # iterate through all resolutions per picture
        for size in image['sizes']:
            # name = hash + '-' + res + '.jpg'

            resolution = int(size['size'].split('x')[0]), int(size['size'].split('x')[1])
            crop_image(path, hash, resolution, size['filter'])


def crop_image(path, name, size, filter):
    img = Image.open(str(path / (name + '.jpg')))
    ar_orig = img.size[0] / img.size[1]
    ar_crop = size[0] / size[1]

    # orig_width = crop_width
    if ar_orig < ar_crop:
        crop_height = int(img.size[0] / ar_crop)
        print(img.size[0], ' ', crop_height)
        upper_left = int((img.size[1] - crop_height) / 2)
        box = (0, upper_left, img.size[0], crop_height + upper_left)
    else:
        crop_width = int(img.size[1] * ar_crop)
        print(img.size[0], ' ', crop_width)
        upper_left = int((img.size[0] - crop_width) / 2)
        box = (upper_left, 0, crop_width + upper_left, img.size[1])

    cropped_img = img.crop(box)

    # resize

    image = cropped_img.resize((size[0], size[1]), Image.ANTIALIAS)

    # apply filters here
    filtered = ''
    for f in filter:

        if f == 'blur':
            image = image.filter(ImageFilter.GaussianBlur(float(filter[f])))
            filtered = '-f'
        elif f == 'brightness':
            image = ImageEnhance.Brightness(image).enhance(float(filter[f]))
            filtered = '-f'
        elif f == 'color':
            image = ImageEnhance.Color(image).enhance(float(filter[f]))
            filtered = '-f'

    image.save(str(path / (name + '-' + str(size[0]) + 'x' + str(size[1]) + filtered + '.jpg')))


def makelist(table):
    result = []

    rows = table.findAll('tr')
    for row in rows:
        new_row = []
        allcols = row.findAll('td')
        for col in allcols:
            empty = True;
            thestrings = []

            for thestring in col.stripped_strings:
                thestring = re.sub(r'\s+', ' ', thestring)

                thestrings.append(thestring)
                if not thestring.split() == '':
                    empty = False
            thetext = ''.join(thestrings)
            new_row.append(thetext)
        # check if row would be empty
        if not empty:
            result.append(new_row)
    return result
