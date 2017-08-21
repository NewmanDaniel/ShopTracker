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
    fields = {"id":"products_id", "handle":"products_handle", "title":"products_title", "price":"products_price", "desc":"products_desc", "vendor":"products_vendor", "sku":"products_sku", "tags":"products_tags", "url":"products_url", "img_url":"products_img_url"}
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

        # ID, used for collections
        self.id = kwargs.get('id','')

        self.g_age_group = kwargs.get('g_age_group','')
        self.g_color= kwargs.get('g_color','')
        self.g_product_category = kwargs.get('g_product_category','')
        #logging.debug('Product object instantiated, handle: %s' % (self.handle))

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

    def getProduct(product_ident, **options): 
        kwargs = {}
        with DB(CursorClass='DictCursor') as con:
            cur = con.cursor()
            if options.get('id') == True:
                # Select product by ID
                sql_statement = "select * from products where products_id=%d" % (product_ident)
            elif options.get('handle') == True:
                # Select product by handle
                sql_statement = "select * from products where products_handle='%s'" % (product_ident)
            else:
                # Default behavior, Select product by handle
                sql_statement = "select * from products where products_handle='%s'" % (product_ident)
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
    Conditions are represented as 3 element tuples, comprised of the variable (tag, title, vendor), relation  
    (equals, does not contain), and value.
    """ 
    variables = ['tag', 'title', 'vendor']
    relations = ['equals', 'does not contain', 'less than', 'greater than']

    def __init__(self, title=None, **kwargs):
        self.products = [] 
        if kwargs.get('handle'): 
            self.handle = kwargs.get('handle')
            self.__gatherProducts()

        else:
            self.title = title
            self.handle = Product.get_handle(title) 
        logging.debug('Collection instantiated: %s' %(self.handle))

    def __repr__(self):
        return self.handle 

    def getCollection(collection_handle):
        with DB() as con:
            cursor = con.cursor() 

    def processConditions(self, *conditions):
        self.conditions = []

        # Verify conditions
        for condition in conditions:
            if Collection.isCondition(condition):
                self.conditions.append(condition)
            else:
                raise ValueError("Attempted to instantiate collection with malformed condition")

        # Build SQL statement
        sql_statement = self.__buildStatementFromConditions(self.conditions)

        # Get product handle list
        product_handles = self.__getProductHandles(sql_statement)

        # Build product List
        self.products = self.__getProductsFromHandles(product_handles)

        self.product_count = len(self.products)

    def getProducts(self):
            return self.products

    def __gatherProducts(self):
        "Used to build a products list for a collection that exists in the database"
        with DB() as con:
            cur = con.cursor()
            get_collection_id_statement = "select collections_id from collections where collections_handle = '%s'"
            get_products_statement = "select products_id from products_collections where collections_id = '%s'"
            product_ids = []

            # get ID of collection
            cur.execute(get_collection_id_statement % (self.handle))
            collections_id = cur.fetchone()[0]

            # get product IDs matching collection ID
            cur.execute(get_products_statement % (collections_id))
            for row in cur.fetchall():
                product_ids.append(row[0])

            # feed them into getProductsFromIDs
            self.products = self.__getProductsFromIDs(product_ids)


    def __getProductsFromIDs(self, product_ids):
        products = []
        for product_id in product_ids:
            products.append(Product.getProduct(product_id, id=True))
        return products


    def __getProductsFromHandles(self, product_handles):
        "Feeds product handles into Product's getProduct method"
        products = []
        for product_handle in product_handles:
            products.append(Product.getProduct(product_handle))
            logging.debug('Collection %s added product %s' %(self.handle, product_handle))
        return products

    def __getProductHandles(self, sql_statement):
        "Used with the constructed SQL statement to return a filtered list of product handles"
        with DB() as con:
            product_handles = []
            cur = con.cursor()
            cur.execute(sql_statement)
            for product in cur.fetchall():
                product_handles.append(product[0])
            return product_handles

    def __buildStatementFragment(self, condition):
        "Returns an sql statement fragment for use in the __buildStatementFromConditions method"
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

    def __buildStatementFromConditions(self, conditions):
        "Returns an sql_statement to match products given a condition"
        sql_statement = 'SELECT products_handle FROM products WHERE ' 
        for i, condition in enumerate(conditions):
            sql_statement += self.__buildStatementFragment(condition)
            if i < len(conditions) - 1:
                sql_statement += ' AND '
            else:
                sql_statement += ';'
        return sql_statement

    def isCondition(condition):
        "Verifies the condition is correctly formed"
        correct_length = len(condition) == 3
        correct_variable = condition[0] in Collection.variables
        correct_relation = condition[1] in Collection.relations
        if correct_length and correct_variable and correct_relation:
            return True
        else:
            return False

    def save(self, cur):
        try:
            select_statement = "SELECT collections_handle FROM collections WHERE collections_handle = '%s'"
            select_id_statement = "SELECT collections_id FROM collections WHERE collections_handle = '%s'"
            insert_collection_statement = "INSERT INTO collections (collections_handle, collections_title) VALUES ('%s', '%s')"
            insert_product_into_collection_statement = "INSERT INTO products_collections (products_id, collections_id) VALUES (%d, %d)" 

            # Check if collection exists, insert into collections table if it doesn't
            cur.execute(select_statement %(self.handle))
            if not cur.fetchall():
                cur.execute(insert_collection_statement % (self.handle, self.title))

            # Get ID for collection
            cur.execute(select_id_statement %(self.handle))
            collections_id = cur.fetchone()[0]

            # Insert products into the collection
            for product in self.products:
                cur.execute(insert_product_into_collection_statement % (product.id, collections_id))


        except mysql.Error as e:
            print("Problem while saving a collection to database")
            #print("Error %d: %s" % (e.args[0], e.args[1]))
            print(e)

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
        cur.execute('delete from collections') 
        cur.execute('delete from products_collections') 
        con.commit()
    import_csv_from_shopify(open('misc/products_export.csv', 'r')) 
    c = Collection("Tapestry Satin Vests")
    c.processConditions(("tag", "equals", "tapestry satin"), ("tag", "equals", "vest"))
    d = Collection("Hardwick Tuxedo")
    d.processConditions(("vendor", "equals", "hardwick"), ("tag", "equals", "tuxedo"))
    e = Collection("Neil Allyn")
    e.processConditions(("vendor", "equals", "Neil Allyn"), ("tag", "equals", "Tuxedo"), ("title", "does not contain", "big and tall"))
    #print(e)
    #for product in e.products:
    #    print("id: " + str(product.id) + " handle: " + product.handle)
    with DB() as con:
        c.save(con.cursor())
        d.save(con.cursor())
        e.save(con.cursor())
        con.commit()
    f = Collection(handle="Nei")
    print(f.products)
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
