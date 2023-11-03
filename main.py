from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from credentials import Credentials
from SMTPEmail import SMTP
from databases import Database
from typing import List, Optional
import numpy as np
from time import time
from datetime import datetime
import cryptocode
import boto3
import uvicorn
import io
import requests
import json
import rq


app = FastAPI()
app.add_middleware(CORSMiddleware, allow_headers=['*'], allow_origins=['*'], allow_methods=['*'])
credentials = Credentials()
credentials = credentials.credentials()
s3 = boto3.client('s3', aws_access_key_id=credentials['aws_access_key_id'], aws_secret_access_key=credentials['aws_secret_access_key'])
db = Database(f"mysql+pymysql://{credentials['db_login']}:{credentials['db_password']}@{credentials['db_host']}:3306/{credentials['db_name']}")
smtp = SMTP(SMTP_server='smtp.gmail.com', SMTP_account=credentials['smtp_account'], SMTP_password=credentials['smtp_password'])
aws_bucket = credentials['aws_bucket']


# API FOR ITEMS

@app.get('/goods', name='goods')
async def goods():
    try:
        status = 500
        message = 'Товари не знайдені!'
        db_conn = await db.connect()
        query_string = f"SELECT * FROM goods"
        goods = await db.fetch_all(query_string)
        await db.disconnect()
        if goods:
            goods_list = [dict(row) for row in goods]
            while len(goods_list) % 6 != 0:
                goods_list.append({})

            message = [goods_list[i:i + 6] + [{}] * (6 - len(goods_list[i:i + 6])) for i in range(0, len(goods_list), 6)]
            status = 200

        return JSONResponse(content={'status': status, 'message': message}, status_code=200)

    except Exception as e:
        return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.get('/goods/category/{category}', name='goods')
async def goods(category: int):
    try:
        status = 500
        message = 'Товари не знайдені!'
        db_conn = await db.connect()
        query_string = f"SELECT * FROM goods WHERE category = '{category}'"
        goods = await db.fetch_all(query_string)
        await db.disconnect()
        if goods:
            goods_list = [dict(row) for row in goods]
            while len(goods_list) % 6 != 0:
                goods_list.append({})

            message = [goods_list[i:i + 6] + [{}] * (6 - len(goods_list[i:i + 6])) for i in range(0, len(goods_list), 6)]
            status = 200

        return JSONResponse(content={'status': status, 'message': message}, status_code=200)

    except Exception as e:
        return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.get('/goods/item/{title}', name='goods.item')
async def goods(title: str):
	try:
		status = 500
		message = 'Товар не знайден!'
		db_conn = await db.connect()
		query_string = f"SELECT * FROM goods WHERE title = '{title}'"
		item = await db.fetch_all(query_string)
		await db.disconnect()
		if item:
			message = [dict(row) for row in item][0]
			status = 200

		return JSONResponse(content={'status': status, 'message': message}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.post('/goods/item/add', name='goods.add')
async def goods(title: str, description: str, category: int, sum: float, images: List[UploadFile] = File(...)):
    try:
        active = False
        color = 'primary'
        buttonText = 'Додати в кошик'

        status = 500
        message = "Товар з таким ім'ям вже існує!"
        db_conn = await db.connect()
        query_string = f"SELECT * FROM goods WHERE title = '{title}'"
        item = await db.fetch_all(query_string)
        item = [dict(row) for row in item]

        if item:
            await db.disconnect()
            return JSONResponse(content={'status': status, 'message': message}, status_code=200)

        else:
            message = 'Товар додан!'
            allowed_types = ['image/png', 'image/jpeg']
            images_list = []
            images_not_uploaded = []

            for image in images:
                image_type = image.content_type
                image_filename = f"{round(time() * 1000)}_image"

                if image_type in allowed_types:
                    s3.upload_fileobj(image.file, Bucket=aws_bucket, Key=image_filename)
                    images_list.append(image_filename)
                else:
                    images_not_uploaded.append(image_filename)

            if len(images_list) > 0:
                status = 200
                images_list = ', '.join(images_list).strip()
                query_string = f"INSERT INTO goods(title, category, description, sum, active, color, buttonText, images) VALUES('{title}', '{category}', '{description}', '{sum}', '{active}', '{color}', '{buttonText}', '{images_list}')"
                add_item = await db.execute(query=query_string)

                if len(images_not_uploaded) != 0:
                    if len(images_not_uploaded) > 1:
                        message = f"{message} Крім декількох зображень через невірний формат."
                    else:
                        message = f"{message} Крім одного зображення через невірний формат."
            else:
                images_list = None
                message = 'Додайте хоч одне зображення формату jpg або png!'

            await db.disconnect()
            return JSONResponse(content={'status': status, 'message': message}, status_code=200)

    except Exception as e:
        return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.put('/goods/update/item/{title}', name='goods.add')
async def goods(title: str, new_title: str = None, new_description: str = None, new_category: int = None, new_fullsum: float = None, images: List[UploadFile] = File(None)):
    try:
        status = 500
        message = 'Товар не знайден!'
        db_conn = await db.connect()
        query_string = f"SELECT * FROM goods WHERE title = '{title}'"
        goods = await db.fetch_all(query_string)
        if goods:
            status = 200
            message = 'Товар оновлений!'
            goods = [dict(row) for row in goods][0]
            new_images = goods['images']  
            allowed_types = ['image/png', 'image/jpeg']
            images_list = []
            images_not_uploaded = []

            if images is not None:
                for image in images:
                    image_type = image.content_type  

                    if image_type in allowed_types:
                        image_filename = f"{round(time() * 1000)}_image"
                        s3.upload_fileobj(image.file, Bucket=aws_bucket, Key=image_filename)
                        images_list.append(image_filename)
                    else:
                        images_not_uploaded.append(image_filename)

                if len(images_list) > 0:
                    new_images = f"{goods['images']}, {', '.join(images_list).strip()}"
                    
                if len(images_not_uploaded) != 0:
                    if len(images_not_uploaded) > 1: 
                        message = f"{message} Крім декількох зображень через не вірний формат."
                    else:
                        message = f"{message} Крім одного зображення через не вірний формат."

            if new_title == None or new_title == goods['title']:
                new_title = goods['title']

            if new_description == None or new_description == goods['description']:
                new_description = goods['description']

            if new_category == None or new_category == goods['category']:
                new_category = goods['category']

            if new_fullsum == None or new_fullsum == goods['sum']:
                new_fullsum = goods['sum']

            query_string = f"UPDATE goods SET title = '{new_title}', category = '{new_category}', description = '{new_description}', sum = '{new_fullsum}', images = '{new_images}' WHERE title = '{title}'"
            await db.execute(query=query_string)
            await db.disconnect()

            return JSONResponse(content={'status': status, 'message': message}, status_code=200)

    except Exception as e:
        return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.delete('/goods/delete/item/{title}', name='goods.delete')
async def goods(title: str):
	try:
		status = 500
		message = 'Товар не знайден!'
		db_conn = await db.connect()
		query_string = f"SELECT * FROM goods WHERE title = '{title}'"
		goods = await db.fetch_all(query_string)
		
		if goods:
			message = 'Товар видалений!'
			status = 200
			query_string = f"DELETE FROM goods WHERE title = '{title}'"
			goods = await db.execute(query=query_string)

		await db.disconnect()
		return JSONResponse(content={'status': status, 'message': message}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.get('/goods/delete/{title}/{filename}', name='goods.image.delete')
async def goods(title: str, filename: str):
	try:
		status = 500
		message = 'Товар не знайден!'
		db_conn = await db.connect()
		query_string = f"SELECT * FROM goods WHERE title = '{title}'"
		goods = await db.fetch_all(query_string)
		
		if goods:
			filename = filename.strip()
			item = [dict(row) for row in goods][0]
			images = item['images'].split(', ')
			message = 'Зображення не знайденo!'

			if filename in images:
				message = 'Ви не можете видалити останнє зображення товара! Перед видаленням, додайте інше зображення.'
				if len(images) > 1:
					status = 200
					message = f"Зображення для '{title}' видалено!"
					images.remove(filename)
					query_string = f"UPDATE goods SET images = '{', '.join(images).strip()}' WHERE title = '{title}'"
					goods = await db.execute(query=query_string)

		await db.disconnect()
		return JSONResponse(content={'status': status, 'message': message}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.get('/goods/image/{filename}', name='goods')
async def goods(filename: str):
	try:
		file = s3.get_object(Bucket=aws_bucket, Key=filename)
		file = file['Body'].read()
		return StreamingResponse(io.BytesIO(file), media_type='image/png')

	except Exception as e:
		return str(e)

# API FOR ADMIN:

@app.get('/admin/passwords', name='admin.all.password')
async def admin():
	try:
		await db.connect()
		query = f"SELECT * FROM admin"
		passwords = await db.fetch_all(query)
		await db.disconnect()

		passwords = [dict(row) for row in passwords]
		passwords_decrypt = []
		for password in passwords:
			passwords_decrypt.append(cryptocode.decrypt(password['password'], 'password'))

		return JSONResponse(content={'status': 200, 'message': passwords_decrypt}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)

@app.get('/admin', name='admin')
async def admin(password: str):
	try:
		await db.connect()
		status = 500
		message = 'Пароль не вірний!'
		password = password.strip()
		query = f"SELECT * FROM admin WHERE password is NOT NULL"
		user = await db.fetch_all(query)
		currenty_password = cryptocode.decrypt([dict(row) for row in user][0]['password'], 'password')

		if password == currenty_password:
			status = 200
			message = 'Вхід дозволений!'

		await db.disconnect()

		return JSONResponse(content={'status': status, 'message': message}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.post('/admin', name='admin.password')
async def admin(password: str):
	try:
		await db.connect()
		query = f"INSERT INTO admin(password) VALUES('{cryptocode.encrypt(password.strip(), 'password')}')"
		user = await db.execute(query=query)
		await db.disconnect()

		return JSONResponse(content={'status': 200, 'message': 'Новий пароль створений!'}, status_code=200)

	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


@app.post('/admin/order/notification/{task}', name='admin.notification')
def notification(task: str, data: dict):
	try:
		text = ''

		if task == 'callback':
			name = data.get('name') 
			email = data.get('email') 
			phone = data.get('phone') 
			comment = data.get('comment')  

			text = f"КОЛЛБЕК\n\nІм'я: {name}\nПошта: {email}\nТелефон: {phone}\nПовідомлення: {comment}\n\nЧас відправлення: {datetime.now()}"

		elif task == 'order':
			phone = data.get('phone') 
			orders = data.get('order')
			order_list = [];
			for order in orders:
				total = order['count'] * order['sum']
				order_list.append(f"{order['title']} ({order['count']} шт. на суму {total})\n")

			order_list = ''.join(order_list)

			text = f"ЗАМОВЛЕННЯ\n\nТелефон: {phone}\nТовари:\n{order_list}\nЧас відправлення: {datetime.now()}"

		message = 'Менеджер отримав ваше повідомлення і в найближчий час зателефонує Вам!'
		status = 200

		url = f"https://api.telegram.org/bot{credentials['telegram_key']}/sendMessage"

		payload = {
		    "text": text,
		    "disable_web_page_preview": False,
		    "disable_notification": False,
		    "reply_to_message_id": None,
		    "chat_id": f"{credentials['telegram_chat_id']}"
		}

		headers = {
		    "accept": "application/json",
		    "User-Agent": "Telegram Bot SDK - (https://github.com/irazasyed/telegram-bot-sdk)",
		    "content-type": "application/json"
		}

		response = requests.post(url, json=payload, headers=headers)

		if response.json().get('ok') != True:
			message = 'Упс, щось трапилось! Спробуйте ще раз!'
			status = 500

		return JSONResponse(content={'status': status, 'message': message}, status_code=200)
	except Exception as e:
		return JSONResponse(content={'status': 500, 'message': str(e)}, status_code=500)


if __name__ == '__main__':
	uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=True)