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
import googleDefs

from bs4 import BeautifulSoup
# -- #
import config

class GoogleFeed:
    def __init__(self, collections):
        self.feed_str = []
        self.collections = []

class DB:
    """
    Sets up a db
    """
    def __init__(self, **kwargs):
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

class Product:
    """
    Describes a shopify product. Fields required for google shopping that don't exist on shopify will be
    marked with g_
    """
    fields = { "id":"products_id", "handle":"products_handle", "title":"products_title", "price":"products_price", "desc":"products_desc", "vendor":"products_vendor", "sku":"products_sku", "tags":"products_tags", "url":"products_url", "img_url":"products_img_url", "g_age_group":"products_g_age_group", "g_color":"products_g_color", "g_product_category":"products_g_product_category" }
    sql_field_type = { "products_id":"%s", "products_handle":"%s", "products_title":"%s", "products_price":"%f", "products_desc":"%s", "products_vendor":"%s", "products_sku":"%s", "products_tags":"%s", "products_url":"%s", "products_img_url":"%s", "products_g_age_group":"%s", "products_g_color":"%s", "products_g_product_category":"%s" }
    def __init__(self, title, **kwargs):
        self.title = title
        self.handle = kwargs.get('handle',Product.get_handle(title))
        self.price = float(kwargs.get('price',0.00))
        self.desc = kwargs.get('desc','')
        self.vendor = kwargs.get('vendor','')
        self.sku = kwargs.get('sku', '')

        self.tags = kwargs.get('tags','')

        self.url= kwargs.get('url','')
        self.img_url = kwargs.get('img_url','')

        # ID, used for collections
        self.id = kwargs.get('id','')

        self.g_age_group = kwargs.get('g_age_group','')
        self.g_color = kwargs.get('g_color','')
        self.g_product_category = kwargs.get('g_product_category','')
        #logging.debug('Product object instantiated, handle: %s' % (self.handle))

    def __repr__(self):
        return self.handle

    def escape_sql_values(values):
        new_values = []
        for value in values:
            if type(value).__name__ == 'str':
                new_values.append(value.replace('\"','\\\"'))
            else:
                new_values.append(value)
        return new_values

    def get_tags(self):
        "Returns a list containing each tag"
        return self.tags.split(", ")

    def set_tags(self, tags):
        "Stores a list of tags into a product object"
        tags_str = ''
        for i, tag in enumerate(tags):
            if i < len(tags) - 1:
                tags_str += "%s, " %(tag)
            else:
                tags_str += "%s" %(tag)
        self.tags = tags_str

    def __get_save_statement(self, statement_type, ignore=['products_id']):
        """
        Returns tuple containing sql statement and formatter.
        Must be given either 'update' or 'insert' statement type.
        sql column names should be added as an argument to the ignore list keyword.
        products_id is ignored by default
        """
        sql_fields = {}

        # Get each sql field and its value
        for object_field, sql_field in self.fields.items():
            sql_fields[sql_field] = self.__getattribute__(object_field)

        if statement_type == 'update':
            update_statement = 'UPDATE products\nSET %s\nWHERE products_handle = "%s";'
            fragment = ''; values = []
            for i, unpacked in enumerate(sql_fields.items()):
                field = unpacked[0]; val = unpacked[1]
                if field not in ignore:
                    if i < len(sql_fields) - 1:
                        fragment += '%s = "%s", ' % (field, self.sql_field_type[field])
                        values.append(val)
                    else:
                        fragment += '%s = "%s" ' % (field, self.sql_field_type[field])
                        values.append(val)
            update_statement = update_statement % (fragment, self.handle)
            values = Product.escape_sql_values(values)
            return update_statement % tuple(values)

        elif statement_type == 'insert':
            insert_statement = 'INSERT INTO products (%s) VALUES (%s);'
            first_fragment = ''; second_fragment = ''; values = []
            for i, unpacked in enumerate(sql_fields.items()):
                field = unpacked[0]; val = unpacked[1]
                if field not in ignore:
                    if i < len(sql_fields) - 1:
                        first_fragment += '%s, ' % (field)
                        second_fragment += '"%s", ' % (self.sql_field_type[field])
                        values.append(val)
                    else:
                        first_fragment += '%s' % (field)
                        second_fragment += '"%s"' % (self.sql_field_type[field])
                        values.append(val)
            insert_statement = insert_statement % (first_fragment, second_fragment)
            values = Product.escape_sql_values(values)
            return insert_statement % tuple(values)
        else:
            raise ValueError('__GetSaveStatement received invalid statement_type')

    def save(self, cur):
        try:
            # Update
            if Product.get_product(self.handle):
                s = self.__get_save_statement('update', ignore=['products_id', 'products_handle'])
                cur.execute(s)
            # Insert
            else:
                s = self.__get_save_statement('insert')
                cur.execute(s)
        except mysql.Error as e:
            print("Problem while saving a product to database")
            #print("Error %d: %s" % (e.args[0], e.args[1]))
            print(e)
            print(cur)
            raise ValueError('SQL ERROR: %s, \nstatement: %s' %(e, s))

    def get_product(product_ident, **options):
        "Gets a product based on its handle, can find a product based on id if id=True keyword is passed"
        kwargs = {}
        with DB() as con:
            cur = con.cursor(mysql.cursors.DictCursor)
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

            # Return NoneType if product not found
            if not result:
                return None

            # Finds all columns that exist in products table and matches them up with object definition
            t_columns = []
            for column in cur.description:
                t_columns.append(column[0])

            for p_attribute, p_column in Product.fields.items():
                if p_column in t_columns:
                    kwargs[p_attribute] = result[p_column]

            return Product(**kwargs)

    def color_list_to_string(colors):
        color_str = ''
        if len(colors) == 1:
            return colors[0]
        elif len(colors) > 1:
            for i, color in enumerate(colors):
                if i < len(colors) - 1:
                    color_str += '%s/' %(color)
                else:
                    color_str += '%s' %(color)
        return color_str

    def process_g_colors(self):
        "Processes colors from title and inserts into g_colors field"
        logging.debug("Processing colors for %s" %(self.handle))
        colors = []
        title_words = self.title.lower().split(" ")

        colorsAppended = 0
        # Scan through to find all colors in Product Title
        for color in googleDefs.color:
            color_in_title_str = color.lower() in self.title.lower()
            if color_in_title_str:
                colors.append(color.lower())
                colorsAppended += 1
                logging.debug("Added color %s for %s" %(color, self.handle))

        # Eliminate colors words nested inside other colors

        # word in word case
        for color in colors:
            if color not in title_words and len(color.split(" ")) < 2:
                colors.remove(color)
                colorsAppended -= 1

        # word in multi word case

        # get multiwords
        multi_colors = []
        for color in colors:
            color_words = color.split(" ")
            if len(color_words) > 1:
                multi_colors.append(color_words)

        # go through multiwords
        for fragments in multi_colors:
            for fragment in fragments:
                for color in colors:
                    cond1 = color == fragment
                    cond2 = fragment in colors
                    if cond1 and cond2:
                        colors.remove(color)
                        colorsAppended -= 1

        # check if colors > 3, and if so, pop the colors off until colors is correct length
        if len(colors) > 3:
            for i in range(len(colors) - 3):
                logging.info("Too many colors for %s, popping color" %(self.handle))
                colors.pop()

        # Did not find a color, log it
        if not colors:
            logging.info("Could not find a color for %s" %(self.handle))

        # Assign g_color to the output of color_list_to_string which formats it to google's specifications
        self.g_color = Product.color_list_to_string(colors)

    def get_handle(title):
        return re.sub(r'\s', '-', title.lower()).replace("'","")

class Collection:
    """
    Represents a collection on shopify. Can be constructed using conditions once products are imported in DB.
    Conditions are represented as 3 element tuples, comprised of the variable (tag, title, vendor), relation
    (equals, does not contain), and value.

    Google product attributes, such as age group, gender, and taxonomy, can be defined in a collection then propogated to its products.
    """
    # condition values
    variables = ['tag', 'title', 'vendor']
    relations = ['equals', 'does not contain', 'less than', 'greater than']

    def __init__(self, title=None, **kwargs):
        # FIX ME.. just use Collection.get_collection instead of this silliness
        self.products = []
        if kwargs.get('handle'):
            self.handle = kwargs.get('handle')
        else:
            self.title = title
            self.handle = Product.get_handle(title)
        logging.debug('Collection instantiated: %s' %(self.handle))

    def __repr__(self):
        return self.handle


    def __get_collection_handles():
        with DB() as con:
            cur = con.cursor()
            statement = "select collections_handle from collections"
            cur.execute(statement)
            handles = [x[0] for x in cur.fetchall()]
            return handles


    def get_collections():
        collections = []
        handles = Collection.__get_collection_handles()
        for handle in handles:
            collections.append(Collection.get_collection(handle))
        return collections


    def get_collection(collection_handle):
        with DB() as con:
            cur = con.cursor()
            c = Collection(handle=collection_handle)
            statement = "select collections_id, collections_title from collections where collections_handle = '%s'"
            cur.execute(statement %(collection_handle))
            row = cur.fetchone()
            id = row[0]; title = row[1]

            c.id = id
            c.title = title
            c.__gather_products()
            return c

    def process_conditions(self, *conditions):
        self.conditions = []

        # Verify conditions
        for condition in conditions:
            if Collection.is_condition(condition):
                self.conditions.append(condition)
            else:
                raise ValueError("Attempted to instantiate collection with malformed condition")

        # Build SQL statement
        sql_statement = self.__build_statement_from_conditions(self.conditions)

        # Get product handle list
        product_handles = self.__get_product_handles(sql_statement)

        # Build product List
        self.products = self.__get_products_from_handles(product_handles)

        self.product_count = len(self.products)

    def get_products(self):
            return self.products

    def generate_urls(self, cur):
        "Used to generate urls for products within a collection and save them in database"
        for product in self.products:
            url = 'https://%s/collections/%s/products/%s' % (config.domain_name, self.handle, product.handle)
            product.url = url
            product.save(cur)

    def __gather_products(self):
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

            # feed them into get_productsFromIDs
            self.products = self.__get_products_from_ids(product_ids)


    def __get_products_from_ids(self, product_ids):
        products = []
        for product_id in product_ids:
            products.append(Product.get_product(product_id, id=True))
        return products


    def __get_products_from_handles(self, product_handles):
        "Feeds product handles into Product's get_product method"
        products = []
        for product_handle in product_handles:
            products.append(Product.get_product(product_handle))
            logging.debug('Collection %s added product %s' %(self.handle, product_handle))
        return products

    def __get_product_handles(self, sql_statement):
        "Used with the constructed SQL statement to return a filtered list of product handles"
        with DB() as con:
            product_handles = []
            cur = con.cursor()
            cur.execute(sql_statement)
            for product in cur.fetchall():
                product_handles.append(product[0])
            return product_handles

    def __build_statement_fragment(self, condition):
        "Returns an sql statement fragment for use in the __build_statement_from_conditions method"
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

    def __build_statement_from_conditions(self, conditions):
        "Returns an sql_statement to match products given a condition"
        sql_statement = 'SELECT products_handle FROM products WHERE '
        for i, condition in enumerate(conditions):
            sql_statement += self.__build_statement_fragment(condition)
            if i < len(conditions) - 1:
                sql_statement += ' AND '
            else:
                sql_statement += ';'
        return sql_statement

    def is_condition(condition):
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

    def bulk_process_g_colors(self):
        with DB() as con:
            cur = con.cursor()
            for product in self.products:
                product.process_g_colors()
                product.save(cur)
            con.commit()

def import_collections_print_collection_list(collection_list):
    for collection in collection_list:
        print("Title: %s" % (collection['title']))
        for condition in collection['conditions']:
            print("    " + condition)

def clean_sql(sql_str):
    return sql_str.replace('"','').replace("'","\\'").strip()

def parse_condition_str(condition_str):
    "Helper function to translate condition strs to tuples that can be accepted by collection object"
    # Need to implement greater than, less than

    variables = {
        "Product tag":"tag",
        "Product title":"title",
        "Product vendor":"vendor",
    }

    relations = {
        "is equal to":"equals",
        "contains":"equals",
        "does not contain":"does not contain",
    }

    condition = ''
    variable = ''; relation = ''; value = ''

    # get variable
    for original, replacement in variables.items():
        m = re.search('(%s)' % (original), condition_str)
        if m:
            variable = replacement
            original_variable = original

    # get relation
    for original, replacement in relations.items():
        m = re.search('(%s)' % (original), condition_str)
        if m:
            relation = replacement
            original_relation = original

    # get value
    m = re.search('(%s.*%s)(.*)' %(original_variable, original_relation), condition_str)
    if m:
        value = clean_sql(m[2])

    # check if everything is set
    if variable and relation and value:
        return (variable, relation, value)
    else:
        raise ValueError('Could not parse condition_str')

def collection_bulk_import(collection_dl):
    """
    Accepts a list of dicts containing the title of a collection and its conditions,
    and saves it to the database. Products will be updated with urls
    """
    with DB() as con:
        collections = []
        titles = []
        for collection in collection_dl:
            if collection['title'] not in titles:
                c = Collection(clean_sql(collection['title']))
                c.process_conditions(*collection['conditions'])
                collections.append(c)
                titles.append(collection['title'])
            else:
                logging.info("Duplicate collection, skipping: %s" %(collection['title']))

        for collection in collections:
            collection.generate_urls(con.cursor())
            collection.save(con.cursor())

        con.commit()

def import_collections_from_shopify(*html_files):
    """
    Imports arguments from collection html pages from the shopify admin
    """
    # Extract titles and conditions from html, store them in collection_list
    collection_list = []
    # Don't add if collection contains a blacklisted word in the title
    blacklist = ['hidden', 'Hidden', 'HIDDEN', 'internal', 'Internal', 'INTERNAL',
                 'Newest Products', 'Best Selling Products', 'Home page']
    for html_file in html_files:
        soup = BeautifulSoup(html_file, 'lxml')
        trs = soup.find_all('tr')
        # navigate through TRs
        for tr in trs:
            if tr.has_attr('data-bind-class'):

                collection = {
                    'title':'',
                    'condition_strs':[],
                }

                # get title
                collection['title'] = tr.find_all('td')[2].text.strip()
                # get conditions
                conditions = []
                for li in tr.find_all('td')[3].find_all('li'):
                    # append them to conditions list
                    conditions.append(li.text)
                collection['condition_strs'] = conditions

                # check blacklist
                has_bad_word = False
                for bad_word in blacklist:
                    if bad_word in collection['title']:
                        has_bad_word = True

                # append to collection list if does not contain bad word
                if not has_bad_word:
                    collection_list.append(collection)

    # Parse through the condition strs and transform them into 3-element tuples
    for collection in collection_list:
        conditions = []
        for condition_str in collection['condition_strs']:
            conditions.append(parse_condition_str(condition_str))
        collection['conditions'] = conditions

    # Give dict with collection titles and tuples to collection_bulk_import function
    collection_bulk_import(collection_list)

    #import_collections_print_collection_list(collection_list)

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
# -- misc functions --
def clear_db():
    with DB() as con:
        cur = con.cursor()
        cur.execute('delete from products')
        cur.execute('delete from collections')
        cur.execute('delete from products_collections')
        con.commit()

def process_colors_for_all_products():
    with DB() as con:
        cur = con.cursor()
        for collection in Collection.get_collections():
            for product in collection.products:
                print("Processing color for: %s" %(product.title))
                product.process_g_colors()
                product.save(cur)
        con.commit()
# --
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

    #Test Block
    #clear_db()
    #import_csv_from_shopify(open('misc/products_export.csv', 'r'))
    #import_collections_from_shopify(open('misc/c1.htm', 'r'), open('misc/c2.htm', 'r'), open('misc/c3.htm', 'r'))
    #process_colors_for_all_products()
    p = Product.get_product('air-force-blue-clip-suspenders')
    p.set_tags(['these', 'are', 'some', 'cool tags'])
    print(p.get_tags())
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
