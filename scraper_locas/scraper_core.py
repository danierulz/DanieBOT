
import datetime
import logging
import sys
import psycopg2
from requests import Session
from sqlalchemy import Column, Engine, String, create_engine, select, text
from typing_extensions import deprecated
import time
import os
from database.dto.ProductDto import ProductDto
from database.models.Products import Products
from database.models.ProductImages import ProductImages
from fastapi import FastAPI, BackgroundTasks
from scraper_locas import Locas
from pywa import WhatsApp
from dotenv import load_dotenv
from logger import Logger
from database.base import Base
from scraper_locas.constants import BUCKET_NAME

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5433") # Default PostgreSQL port
DB_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


os.environ['WDM_SSL_VERIFY'] = '0'
load_dotenv()
print("Create_engine scraper_core.py")
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
log = Logger.Logger(__name__, level='debug', fmt='%(asctime)s - %(levelname)s - %(message)s')


def scraper_code_main():
    print("main() __name__: ", __name__)

    #Inicio sesion y me dirijo a la web de DENIM para obtener la lista de jeans de la primera página
    log.logger.debug("Inicio de Main")
    inst = Locas.Locas()
    
    #inst.d2_ficha_take_gallery("https://laslocas.com/ficha-224-jogger-blue-ribb")
    #inst.insert_product()8
    #sys.exit() 
    inst.land_login_page()
    
    #Inicia proceso de logueo
    inst.init_login()
    log.logger.debug('2: page_source OK: %s ', inst.page_source)

    #Figure out how quantity of pages there are available
    inst.verify_qty_of_pages_denim()

    #Iterate each of pages to obtain links of each it
    i = 1
    while( i < inst.pages):
        i+=1
        #TODO: REVISAR QUE TIENE UN CORTE DE 4 PAGINAS 
        inst.take_jeans_denim_per_page(i)
 
    #Con la lista de links de cada denim voy a scrapear su contenido y guardarlo en PostgreSQL
    for url_ficha in inst.list_denim:
        inst.product = ProductDto()
                #Create folder to store one model of jean
        #   EXAMPLE =>  C:\Projects\LasLocas\images/denim/ficha-710-oxford-sech 
        path_full_ficha = inst.create_folder_ficha(url_ficha)
    
        #Save in product object the content of each denim
        #Save images in local folder
        inst.d2_ficha_take_gallery(url_ficha, path_full_ficha)

        print("logueando antes del get_db_session scraper_core.py")

        with inst.get_db_session() as db:
            print("🔎 Verificando productos existentes...")
        
            # SELECT moderno (No devuelve None, devuelve lista vacía si no hay nada)
            stmt = select(Products.cod_product)
            codigos_en_db = db.execute(stmt).scalars().all()
        
            # Create Products object from scraped data
            if inst.product.cod_product not in codigos_en_db:
            
                nuevo = Products(
                    description=inst.product.description,
                    price=int(inst.product.price),
                    status=False,
                   # gallery_photos=inst.product.gallery_photos,
                    cod_product=inst.product.cod_product,
                    item_title=inst.product.item_title,
                    name=inst.product.name,
                    sku=inst.product.sku,
                    extract_date=datetime.datetime.now()
                )
                db.add(nuevo)

   #             nuevo.sku = inst.product.sku
                for idx, foto in enumerate(inst.product.gallery_photos):
                    image_url = inst.upload_to_gcs_from_filename(BUCKET_NAME, path_full_ficha, foto)
                    # Crear objeto ProductImages enlazado
                    product_image = ProductImages(
                    product=nuevo,
                    filename=inst.product.gallery_photos[0],
                    url=image_url,
                    is_main=(idx == 0)
                    )
                    db.add(product_image)
                


               
                print(f"✅ Se insertó 1 denim nuevo en la nube.")
            else:
                print("ℹ️ No hay novedades para cargar.")

    print("PROGRAMA FINALIZA CON ÉXITO, SE CIERRA CONEXIÓN A DB Y SE CIERRA PROGRAMA.")


        
"""

        cur, con = inst.connect_db()
        print("logueando despues del connect_db en main.py")
        try:
            result = cur.execute(stmt2)
            print("imprimiendo resultado: ")
            print(result)
            inst.logs.logger.debug("RowCount: %s" , cur.rowcount)
            for row in result:
                print(f"{row.description}")
        except(Exception,psycopg2.Error) as e:
            print("Exception in SELECT  products " , e)
            sys.exit(1)
        finally:
            con.commit()
            con.close()



    
        inst.insert_product()


    sys.exit()
"""

def test_select_sqlalchemy():
    with engine.connect() as connection:
        results = connection.execute(text("select description, price, status, cod_product, item_title from products"))
        #print(results.fetchall())
        for row in results:
            print("description:", row.description)
            print("price:", row.price)
            print("status:", row.status)
        #    print("gallery_photos:", row.gallery_photos)
            print("cod_product:", row.cod_product)
            print("item_title:", row.item_title)
        print("termino el commit")


if __name__ == '__main__':
    scraper_code_main()

#@deprecated
def  configure_logging():
    logging.basicConfig(filename='debug.log', filemode='w',encoding='utf-8', level=logging.DEBUG)

    CURRENT_DIR = os.getcwd()  # Ruta actual de trabajo
    
    # change the current directory to specified directory
    os.chdir('logs')
    
    fh = logging.FileHandler('debug.log', mode='w')
    #fh.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to fh
    fh.setFormatter(formatter)

    #logger.addHandler(fh)
    #logger.debug('1: configure_logging')
    #logger.debug('  CURRENT_DIR : %s ', CURRENT_DIR)
    """
    print("1", os.listdir())
    print("2",os.getcwd())
    print("3",os.getcwd())
    print("4",completeName)
    """
