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

    def __repr__(self):
        return self.handle

    def save(self, cur):
        try:
            statement = "INSERT INTO PRODUCTS (!PRODUCTS_PLACEHOLDER!) VALUES (!VALUES_PLACEHOLDER!)"
            products_placeholder = ""
            values_placeholder = ""
            for variable in vars(self):
                print(variable)
            print("saving to db: %s"% (self.handle))
            cur.execute("""
            INSERT INTO products (products_handle, products_title, products_price, products_desc, products_vendor)
            VALUES ("%s", "%s", %d, "%s", "%s")
            """ % (self.handle, self.title, self.price, self.desc, self.vendor))
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
            p_list.append(Product(
                row["Title"],
                handle=row["Handle"],
                price=row["Variant Price"],
                desc=row["Body (HTML)"],
                vendor=row["Vendor"],
                tags=row["Tags"],
                img_url=row["Image Src"],
                sku=row["Variant SKU"]
            ))

        for product in p_list:
            product.save(con.cursor())


def print_error():
    """
    Prints the error if command wasn't formatted correctly
    """
    print("Invalid Syntax,") 

def main(): 
    """
    Handles command arguments
    """
    # Test Block
    with DB() as con:
        product = Product("Pearl White Skyfall Tuxedo by Michael Craig", description="dazzle in this top of the line", price=495.00, vendor="Michael Craig" )
        product.save(con.cursor())
        con.commit() 
    #import_csv_from_shopify(open('misc/products_export.csv', 'r'))


    # End test block

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
