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
    def __init__(self, **kwargs):
        try:
            if 'CursorClass' in kwargs and kwargs['CursorClass'] == 'DictCursor':
                self.con = mysql.connect(config.db_host, config.db_user, config.db_password, config.db_name, cursorclass=mysql.cursors.DictCursor)
            else:
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
    fields = {"handle":"products_handle", "title":"products_title", "price":"products_price", "desc":"products_desc", "vendor":"products_vendor", "sku":"products_sku", "tags":"products_tags", "url":"products_url", "img_url":"products_img_url"}
    def __init__(self, title, **kwargs):
        self.title = title
        self.handle = kwargs.get('handle',Product.get_handle(title))
        self.price = float(kwargs.get('price',0))
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

    def getProduct(product_handle): 
        kwargs = {}
        with DB(CursorClass='DictCursor') as con:
            cur = con.cursor()
            sql_statement = "select * from products where products_handle='%s'" % (product_handle)
            cur.execute(sql_statement)
            result = cur.fetchone()

            # Finds all columns that exist in products table and matches them up with object definition
            t_columns = []
            for column in cur.description:
                t_columns.append(column[0])

            for p_attribute, p_column in Product.fields.items(): 
                if p_column in t_columns:
                    kwargs[p_attribute] = result[p_column] 

            return Product(**kwargs)


    def get_handle(title):
        return re.sub(r'\s', '-', title.lower())

class Collection:
    """
    Represents a collection on shopify. Can be constructed using conditions once products are imported in DB.
    Conditions are represented as 3 element tuples, comprised of the variable (tag, vendor), relation  
    (i.e. equals, lessthan), and value.
    """ 
    #e = Collection("Neil Allyn", ("vendor", "equals", "Neil Allyn"), ("tag", "equals", "Tuxedo"), ("title", "does not contain", "big and tall"))
    variables = ['tag', 'title', 'vendor']
    relations = ['equals', 'does not contain', 'less than', 'greater than']

    def __init__(self, title, *conditions):
        self.title = title

        self.conditions = []
        self.products = []

        # Verify conditions
        for condition in conditions:
            if Collection.isCondition(condition):
                self.conditions.append(condition)
            else:
                raise ValueError("Attempted to instantiate collection with malformed condition") 

        # Build SQL statement
        sql_statement = self.processConditions(self.conditions)

        # Get product handle list
        product_handles = self.getProductHandles(sql_statement)

        # Build product List
        self.products = self.getProducts(product_handles)

    def __repr__(self):
        return self.title

    def getProducts(self, product_handles):
        products = []
        for product_handle in product_handles:
            products.append(Product.getProduct(product_handle))
        return products

    def getProductHandles(self, sql_statement):
        with DB() as con:
            product_handles = []
            cur = con.cursor()
            cur.execute(sql_statement)
            for product in cur.fetchall():
                product_handles.append(product[0])
            return product_handles

    def processCondition(self, condition):
        "Returns an sql statement fragment for use in the processConditions method"
        sql_statement_fragment= ''
        variable = condition[0]; relation = condition[1]; value = condition[2]

        if variable == 'tag':
            if relation == 'equals': 
                sql_statement_fragment = "products_tags LIKE '%%%s%%'" % (value)
            if relation == 'does not contain':
                sql_statement_fragment = "products_tags NOT LIKE '%%%s%%'" % (value)
        if variable == 'title':
            if relation == 'equals':
                sql_statement_fragment = "products_title LIKE '%%%s%%'" % (value)
            if relation == 'does not contain':
                sql_statement_fragment = "products_title NOT LIKE '%%%s%%'" % (value)
        if variable == 'vendor':
            if relation == 'equals':
                sql_statement_fragment = "products_vendor LIKE '%%%s%%'" % (value)

        if sql_statement_fragment == '':
            raise ValueError("Condition could not be processed")
        else:
            return sql_statement_fragment

    def processConditions(self, conditions):
        "Returns an sql_statement to match products given a condition"
        sql_statement = 'SELECT products_handle FROM products WHERE ' 
        for i, condition in enumerate(conditions):
            sql_statement += self.processCondition(condition)
            if i < len(conditions) - 1:
                sql_statement += ' AND '
            else:
                sql_statement += ';'
        return sql_statement

    def isCondition(condition):
        correct_length = len(condition) == 3
        correct_variable = condition[0] in Collection.variables
        correct_relation = condition[1] in Collection.relations
        if correct_length and correct_variable and correct_relation:
            return True
        else:
            return False


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
    with DB() as con:
        cur = con.cursor()
        cur.execute('delete from products') 
        con.commit()
    import_csv_from_shopify(open('misc/products_export.csv', 'r')) 
    c = Collection("Tapestry Satin Vests", ("tag", "equals", "tapestry satin"), ("tag", "equals", "vest"))
    d = Collection("Hardwick Tuxedo", ("vendor", "equals", "hardwick"), ("tag", "equals", "tuxedo"))
    e = Collection("Neil Allyn", ("vendor", "equals", "Neil Allyn"), ("tag", "equals", "Tuxedo"), ("title", "does not contain", "big and tall"))
    print(e)
    for product in e.products:
        print(product)
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
