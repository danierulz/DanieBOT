    #https://pypi.org/project/webdriver-manager/
from contextlib import contextmanager
import datetime
import json
import os
from ssl import Options
import sys
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import pg8000
import requests
from selenium import webdriver
from sqlalchemy import DateTime, Null, create_engine
import urllib3
from webdriver_manager.chrome import ChromeDriverManager
#import src.logger.Logger as Logger
from database.models.Products import Products
from database.models.ProductImages import ProductImages
from logger import Logger
from database.dto.ProductDto import ProductDto
from sqlalchemy.orm import sessionmaker, declarative_base
from scraper_locas import Locas
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from google.cloud import storage
import scraper_locas.constants as const

import logging
import re
import os
import psycopg2

#logger = logging.getLogger('__main__')
#   Clase utilizada para extraer denims de "Las Locas"
#   
#
#   land_first_page(self)               Hace un get de laslocas.com/login
#   init_login(self)                    Introduce correo, clave y hace login
#   verify_qty_of_pages_denim(self)     Extrae todos los links igual a productos/denim?page= para luego 
#                                           solo tomar la pagina mayor
#   take_jeans_denim_per_page           Recibe un número de pagina de denim y accede a ella para luego
#                                           tomar cada enlace de cada denim y guardarlos en una lista

os.environ['WDM_SSL_VERIFY'] = '0'
chrome_options = webdriver.ChromeOptions()
PROXY = "http://internet.ford.com:83"
chrome_options.add_argument('--proxy-server=%s' % PROXY)
options = {
    'proxy': {
        'http': 'http://internet.ford.com:83',
        'https': 'https://internet.ford.com:83',
        'no_proxy': 'localhost,127.0.0.1,19.0.0.0/8,10.0.0.0/8,172.16.0.0/12,.ford.com'
    }
}
DB_USER = os.getenv("PG_USER", "bot_laslocas")
DB_PASSWORD = os.getenv("PG_PASSWORD", "Neverl0l")
DB_HOST = os.getenv("PG_HOST", "127.0.0.1")
DB_PORT = os.getenv("PG_PORT", "5433")
DB_NAME = os.getenv("PG_DATABASE", "laslocas_db")
DB_HOST_DOCKER = os.getenv("DB_HOST_DOCKER", "host.docker.internal")  # For Docker connectivity
# Create the database URL
DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST_DOCKER}:{DB_PORT}/{DB_NAME}"

print("create_engine Locas.py" )
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Locas(webdriver.Chrome):
    pages = 0
    list_denim = []
    def __init__(self, driver_path = ChromeDriverManager().install(), tearDown=False):
        self.logs = Logger.Logger(self.__class__.__name__, level='debug', fmt='%(asctime)s - %(levelname)s - %(message)s')
        self.logs.logger.debug("Class Locas __init__ __name__: %s" , self.__class__.__name__) 
        self.driver_path = driver_path
        self.product = ProductDto()
        self.tearDown = tearDown
        super(Locas, self).__init__()
        
    def __exit__(self):
        if self.tearDown:
            self.quit()
    
    def land_login_page(self):
        self.get(const.BASE_URL)
    
    def init_login(self):
        self.logs.logger.debug("verify_quantity_of_pages_denim() %s" , "init_login")
        print("Se esta iniciando el proceso de logueo")
        inputEmail = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.ID, 'inputEmail')))
        inputEmail.send_keys(os.getenv("LOGIN_EMAIL"))
        
        inputPassword = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.ID, 'inputPassword')))
        inputPassword.send_keys(os.getenv("LOGIN_PASS"))
        
        typeSubmit = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[type='submit']")))
        typeSubmit.click()
        self.set_script_timeout(5)

    def verify_qty_of_pages_denim(self):
        self.logs.logger.debug('verify_quantity_of_pages_denim()')
        self.set_script_timeout(5)
        self.get(const.PAGE_PRODUCTOS_DENIM)
        
        webelement_pages = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.ID, 'pag')))
        #webelement_pages.find_elements(By.CSS_SELECTOR, "a[href*='page']")
        #self.logs.logger.debug("Presence of element By.ID, pag %s ", webelement_pages.get_attribute('innerHTML'))

        web_pages_hrefs = webelement_pages.find_elements(By.CSS_SELECTOR,"a[href*='page']")

        extract_pages = re.compile(r'([\d]+)')
         
        qty_pages = []
        for urls in web_pages_hrefs:

            mo = extract_pages.search(urls.get_attribute("href"))
        #    self.logs.logger.debug(urls.get_attribute("href"))
            qty_pages.append(int(mo.group()))
        
        self.pages = max(qty_pages)
        #print("hardcodeando pages a 2 para testear: ", self.pages)
        self.pages = 2
        print("Máximo valor de número de paginas en demim es:  ", self.pages)

    def take_jeans_denim_per_page(self, i):
        #self.logs.logger.debug("Tomando la lista de jeans de denim per page")
        self.set_script_timeout(5)
        self.get(f'https://laslocas.com/productos/denim?page={i}')

        lnks=self.find_elements(By.CSS_SELECTOR,"a[href*='ficha']")
        
        self.set_script_timeout(2)
        #logger.debug('10: find_elements_CSS_SELECTOR div.module: %s ', lnks)
        new_list = []
        i = 0
        for lnk in lnks:
            i+=1
            # get_attribute() to get all hre
            #   self.logs.logger.debug('6: lnk href: %s ', lnk.get_attribute("href"))
            if lnk not in new_list:
                new_list.append(lnk.get_attribute("href"))
                #self.logs.logger.debug('danie5 text: %s ', lnk.text)
            if(i>4):
                break
                
        [self.list_denim.append(list) for list in new_list if list not in self.list_denim]
        print("total de elementos en lista denim: ", len(self.list_denim))

    def d2_ficha_take_gallery(self, page_ficha,path_full_ficha): 
        #self.logs.logger.debug('URL ficha:  %s', page_ficha)
        #self.logs.logger.debug("page source: %s", self.page_source )
                
        self.get(page_ficha)

        #***********************************************************************************************
        #Get gallery of photos defined how <div class="d2">
        div_d2 = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "d2")))
        #Get all of href links
        web_pages_hrefs = div_d2.find_elements(By.CSS_SELECTOR,"a[href]")
        #***********************************************************************************************
        #*************************************************************************************************************
        # NOT DELETE => Not delete this timeout because 2 seconds are sufficient for avoid to get incorrect of codProd 
        # for example will taken this value => <span id="codProd">2023100423161466960
        # An error was => Exception in INSERT INTO products  el valor es demasiado largo para el tipo character varying(20)
        # set_script_timeout(3) NOT WORK WELL
        #**************************************************************************************************************
        #self.set_script_timeout(3)
        time.sleep(5)


        #***********************************************************************************************
        #Get self.codProd          EXAMPLE =>      <span id="codProd">BSPOR</span>
        span_codProd = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.ID, "codProd")))
        #self.logs.logger.debug("span_codProd: %s" , span_codProd)
        self.product.cod_product = span_codProd.get_attribute('innerHTML')
        #self.logs.logger.debug("span_codProd: %s" , self.product.cod_product)
        #print("codProd_element length: ", len(self.product.cod_product))
        #self.logs.logger.debug("codProd_element %s", self.product.cod_product)
        #***********************************************************************************************

        #***********************************************************************************************
        #Get item-Title of ficha        Example      =>       <h1 class="item-title inline">BLUE SPORTY</h1>
        item_title_element = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "item-title")))
        self.product.item_title = item_title_element.get_attribute('innerHTML')
        #print("item_title: ", self.product.item_title)
        #***********************************************************************************************

        #***********************************************************************************************
        #Get    	Deprecated because price already taken in other side
        #precioPromo_element = WebDriverWait(self, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "b2")))
        #self.logs.logger.debug('  precioPromo_element: %s ', precioPromo_element.is_displayed())
        #self.precioPromo = precioPromo_element.get_attribute('innerHTML')
        #self.product.price= precioPromo_element.get_attribute('innerHTML')
        #***********************************************************************************************

        
# GET_SCRIPT_AND_EXTRACT_JSON() => This method fill the following attributes of self.product:
#         self.product.sku = int(d["sku"])
#         self.product.name = d["name"]
#         self.product.description = d["description"]
#         self.product.price = float(d["offers"]["price"])
        self.get_script_and_extract_json()
        
        
        # Create a PoolManager instance
        http = urllib3.PoolManager()
        # Download all images of gallery d2
        for href_element in web_pages_hrefs:
            #Get URL of photo
            url = href_element.get_attribute("href")
            # Send an HTTP GET request to the URL
            response = http.request('GET', url)

            # Retrieve the content (image data)
            #Not more save into Locas imagen gallery, only save into GCS and save the URL in DB
            #self.product.gallery_photos.append(response.data) 
            name_of_photo = url.rsplit('/', 1)[-1]
            name_of_photo_only = url.split('/')[-1]

#            self.upload_to_gcs(page_ficha,name_of_photo_only, response.data)
#            self.product.page_ficha = page_ficha
            self.product.gallery_photos.append(name_of_photo_only);
            with open(os.path.join(path_full_ficha,name_of_photo),"wb") as temp_file:
                temp_file.write(response.data)
        
#*****************************************************************************************************
#***    UPLOAD IMAGE TO GCS      *********************************************************************
#*****************************************************************************************************        
    def upload_to_gcs_binary(self,page_ficha, nombre_archivo, datos_binarios, bucket_name="bucket_laslocas_prod"):
        url2parse = urlparse(page_ficha)
        name_folder = url2parse.path.replace('/', '')
    # Al no pasarle argumentos, busca el login de tu terminal automáticamente
        client = storage.Client() 
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(f"images/{name_folder}/{nombre_archivo}")
        blob.upload_from_string(datos_binarios, content_type='image/jpeg')
        blob.make_public()  # Opcional: hacer que el archivo sea público para obtener una URL accesible públicamente
        return blob.public_url        

#*****************************************************************************************************
#***    UPLOAD IMAGE TO GCS      *********************************************************************
#*****************************************************************************************************        
    def upload_to_gcs_from_filename(self,bucket_name, path_full_ficha, nombre_archivo):
        url2parse = urlparse(path_full_ficha)
        url_ficha_path = url2parse.path.replace('/', '')     
        #/images/denim/ficha-710-oxford-sech   
        newfolder_and_photoname = const.PATH_IMAGE_DENIM +  url_ficha_path

#        name_folder = url2parse.path.replace('/', '')
        print("url2parse: ", url2parse)
    # Al no pasarle argumentos, busca el login de tu terminal automáticamente
        
        client = storage.Client() 
        print("bucket_name: ", bucket_name  )
        bucket = client.get_bucket(bucket_name)
    #    blob = bucket.blob(f"images/{self.product.page_ficha}/{nombre_archivo}")
     #   blob.upload_from_filename(f"{newfolder_and_photoname}/{nombre_archivo}", content_type='image/jpeg')
        print("os.path.join(path_full_ficha, nombre_archivo): ", os.path.join(path_full_ficha, nombre_archivo)  )
        blob = bucket.blob(f"images/{self.product.page_ficha}/{nombre_archivo}")
        blob.upload_from_filename(os.path.join(path_full_ficha, nombre_archivo), content_type="image/jpeg")
    
        blob.make_public()  # Opcional: hacer que el archivo sea público para obtener una URL accesible públicamente
        return blob.public_url        

#*****************************************************************************************************
#***    INSERT PRODUCT           *********************************************************************
#*****************************************************************************************************
    # def insert_product(self):
    #     cur, con = self.connect_db()
    #     dt = datetime.datetime.now()
    #     dt_obj_w_tz = datetime.datetime.now()
    #     dt_obj_wo_tz = dt_obj_w_tz.replace(tzinfo=None)
    #     try:
    #         #cur.execute("INSERT INTO products (product_id,description, unit_price, status, gallery_photos)" +
    #         #            "VALUES (default, 'test 3333' , 111, false, NULL);")
    #         cur.execute("INSERT INTO products (description, price, status, gallery_photos, cod_product, item_title, " +
    #                     "name, sku, extract_date, create_date ) " +
    #                     "VALUES (%s , %s, %s, %s, %s, %s, %s, %s, %s, %s);",
    #                      (self.product.description, self.product.price, 'true', self.product.gallery_photos,
    #                        self.product.cod_product, self.product.item_title, self.product.name, self.product.sku, 
    #                        dt, dt_obj_wo_tz))
    #         self.logs.logger.debug("RowCount: %s" , cur.rowcount)
    #     except(Exception,psycopg2.Error) as e:
    #         print("Exception in INSERT INTO products " , e)
    #         sys.exit(1)
    #     finally:
    #         con.commit()
    #         con.close()
#*****************************************************************************************************
#***    CONNECT DB               *********************************************************************
#*****************************************************************************************************
    # @contextmanager
    # def connect_db(self):
    #     with SessionLocal() as session:
    #         try:
    #             # Verificamos si el producto ya existe por su código
    #             stmt = select(Products).where(Products.cod_product == product_data['cod_product'])
    #             existing_product = session.execute(stmt).scalar_one_or_none()

    #             if existing_product:
    #                 self.logs.logger.debug(f"Actualizando producto: {product_data['cod_product']}")
    #                 for key, value in product_data.items():
    #                     setattr(existing_product, key, value)
    #             else:
    #                 self.logs.logger.debug(f"Insertando nuevo producto: {product_data['cod_product']}")
    #                 nuevo = Products(**product_data)
    #                 session.add(nuevo)
                
    #             session.commit()
    #         except Exception as e:
    #             session.rollback()
    #             self.logs.logger.error(f"Error guardando en DB: {e}")

#
 #       try:
  #          self.connection = pg8000.connect(                                                  
  #              user = os.getenv("PG_USER"),                                      
  ####              password = os.getenv("PG_PASSWORD"),                                  
   #             host = os.getenv("PG_HOST"),                                            
   ##             port = os.getenv("PG_PORT"),                                          
   #             database = os.getenv("PG_DATABASE"))##

#            self.connection.autocommit = True  # Ensure data is added to the database immediately after write commands
#            self.cursor = self.connection.cursor()
#            
 #       except psycopg2.DatabaseError:
  #          if self.connection:
   #             self.connection.rollback()
    #            print("PostgreSQL DatabaseError ")
     #           sys.exit(1)
        #finally:
        #    if self.connection:
        #        self.cursor.close()
        #        self.connection.close()
        #        print("PostgreSQL connection is closed")
  #      return self.cursor, self.connection


    #Paragraph that contains validation of folders to save images of denims
    # page_ficha        => https://laslocas.com/ficha-710-oxford-sech
    # url_ficha_path    => ficha-710-oxford-sech
    # newfolder_and_photoname   => images/denim/ficha-710-oxford-sech
    # os.getcwd()               => C:\Projects\LasLocas

    @contextmanager
    def get_db_session(self):
        """Generador de sesiones que se cierran solas."""
        session = SessionLocal()
        try:
            yield session
            session.commit() # Si todo sale bien, guarda
        except Exception as e:
            session.rollback() # Si hay error, deshace
            print(f"❌ Error en la DB: {e}")
            raise
        finally:
            session.close() # Siempre cierra la conexión


    def create_folder_ficha(self, url_ficha):
        url2parse = urlparse(url_ficha)
        url_ficha_path = url2parse.path.replace('/', '')    
        print("url_ficha_path: ", url_ficha_path)
        #/images/denim/ficha-710-oxford-sech   
        newfolder_and_photoname = const.PATH_IMAGE_DENIM +  url_ficha_path
        self.product.page_ficha = url_ficha_path

        # get current directory
        path = os.getcwd()
        path_full_ficha =  os.path.join(path, newfolder_and_photoname)
        #self.logs.logger.debug("Carpeta ficha: %s" , path_full_ficha)
        if not os.path.exists(path_full_ficha):
            os.makedirs(path_full_ficha)
            self.logs.logger.debug("Folder %s created!" % path_full_ficha)
        else: 
            self.logs.logger.debug("Folder %s already exists" % path_full_ficha)
        return path_full_ficha
        
    #This method find a <script> type="application/ld+json"
    #Into this script its contains info that i need, for example:
    # Sku, Name, Price, Description, image, 
    def get_script_and_extract_json(self):
        soup = BeautifulSoup(self.page_source, "html.parser")
        
        try:
            all_data = soup.find_all("script", {"type": "application/ld+json"})
            
            for data in all_data:
                jsn = json.loads(data.string)
                self.logs.logger.debug('test_get_script() %s', json.dumps(jsn, indent=4))
            data = [
            json.loads(x.string) for x in soup.find_all("script", type="application/ld+json")
            ]
        except Exception as e:
            self.logs.logger.debug('all_data %s', all_data)
            print("aca tenemos un error severo: ", e)
        
        for d in data:
            #print("sku: ", d["sku"])
            #print("name: ", d["name"])
            #print("description: ",d["description"])
            #print("image: ", d["image"])
            #print("priceCurrency", d["offers"]["priceCurrency"] )
            #print("price: ", d["offers"]["price"])
            #print("availability: ", d["offers"]["availability"])
            #print("itemCondition: ", d["offers"]["itemCondition"])

            self.product.sku = int(d["sku"])
            self.product.name = d["name"]
            self.product.description = d["description"]
            self.product.price = float(d["offers"]["price"])
            
    #def insert_products(self):
    
    if __name__ == "__main__":  
        print ("Locas.py is being run directly: ", __name__) 
    else:  
        print ("Locas.py is being imported", __name__) 

                  

