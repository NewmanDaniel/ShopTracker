#!/usr/bin/python3
"shoptracker.py"
"""
Allows user to import products from shopify into a mysql database
"""
import logging, sys
import io
import re
import MySQLdb as mysql
import csv
# -- #
import config

class DB:
    """
    Sets up a db
    """
    def __init__(self):
        try:
            self.con = mysql.connect(config.db_host, config.db_user, config.db_password, config.db_name)
            self.cursorInUse = False
        except mysql.Error as e:
            print("Problem connecting to database")
            print("Error %d: %s" % (e.args[0], e.args[1]))

    def __enter__(self):
        return self.con

    def __exit__(self, type, value, traceback):
        self.con.close()

    def commit(self):
        self.con.commit()

    def getCursor(self):
        if self.cursorInUse == True:
            raise ValueError('Database cursor is already in use', 'cursorException', 'cursorInUseException')
        else:
            self.cursorInUse = True
            self.cur = self.con.cursor()
            return self.cur

    def relinquishCursor(self):
        if self.cursorInUse == False:
            raise ValueError('Tried to relinquish cursor when it was not in use', 'cursorException', 'cursorNotInUseExeption')
        else:
            self.cursorInUse = False
            del self.cur

    def close(self):
        self.con.close()

class Product:
    """
    Describes a shopify product. Fields required for google shopping that don't exist on shopify will be
    marked with g_
    """
    def __init__(self, title, **kwargs):
        self.title = title
        self.handle = kwargs.get('handle',Product.get_handle(title))
        self.price = kwargs.get('price',0)
        self.desc = kwargs.get('desc','')
        self.vendor = kwargs.get('vendor','')
        self.sku = kwargs.get('sku', '')

        self.tags = kwargs.get('tags','')

        self.url= kwargs.get('url','')
        self.img_url = kwargs.get('img_url','') 


        #self.collections = kwargs.get('collections', [])
        self.g_age_group = kwargs.get('g_age_group','')
        self.g_color= kwargs.get('g_color','')
        self.g_product_category = kwargs.get('g_product_category','')
        logging.debug('Product object instantiated, handle: %s' % (self.handle))

    def __repr__(self):
        return self.handle

    def save(self, cur):
        try:
            cur.execute("""
            INSERT INTO products (products_handle, products_title, products_price, products_desc, products_vendor, products_SKU, products_tags, products_url, products_img_url)
            VALUES ("%s", "%s", "%d", "%s", "%s", "%s", "%s", "%s", "%s")
            """ % (self.handle, self.title, self.price, self.desc.replace('\"','\\"'), self.vendor, self.sku, self.tags.replace('\"','\\"'), self.url, self.img_url))
            logging.debug('Product object saved to db, handle: %s' % (self.handle))
        except mysql.Error as e:
            print("Problem while saving a product to database")
            #print("Error %d: %s" % (e.args[0], e.args[1]))
            print(e)

    def get_handle(title):
        return re.sub(r'\s', '-', title.lower())

def import_csv_from_shopify(csv_file):
    """
    Imports shopify product CSV from shopify
    """
    with DB() as con:
        p_list = []
        reader = csv.DictReader(csv_file)

        for row in reader:
            isPublished = row["Published"]
            if isPublished == 'true':
                logging.info('Importing handle %s from %s' % (row["Handle"], csv_file.name))
                p_list.append(Product(
                    row["Title"],
                    handle=row["Handle"],
                    price=float(row["Variant Price"]),
                    desc=row["Body (HTML)"],
                    vendor=row["Vendor"],
                    tags=row["Tags"],
                    img_url=row["Image Src"],
                    sku=row["Variant SKU"]))
            elif isPublished == 'false':
                logging.debug('Skipped %s, pub value %s' % (row["Handle"], row["Published"]))
            else:
                logging.debug('Skipped %s: malformed Published value'% (row["Handle"]))

        for product in p_list:
            product.save(con.cursor())

        con.commit()


def print_error():
    """
    Prints the error if command wasn't formatted correctly
    """
    print("Invalid Syntax,") 

def main(): 
    """
    Handles command arguments
    """
    # Instantiate logger
    logging.basicConfig(filename=config.logging_file, filemode='w', level=logging.DEBUG)
    #logging.debug('debug msg')
    #logging.info('info msg')
    #logging.warning('warning msg')
    #logging.critical('critical msg')

    # Test Block
    import_csv_from_shopify(open('misc/products_export.csv', 'r')) 
    # End test block

    # Argument handling
    if len(sys.argv) == 2:
        # Read in url text file and perform operations
        pass
    elif len(sys.argv) == 3:
        print("bla")
    else:
        pass
        #print_error() 

if __name__ == '__main__':
    main()
