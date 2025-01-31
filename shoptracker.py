"""
Transmission, redistribution or modification of this software is strictly forbidden.
Copyright 2017, Daniel Newman, All rights reserved.
"""

#!/usr/bin/python3
"shoptracker.py"
"""
Allows user to import products from shopify into a mysql database
"""
import codecs
import copy
import logging, sys
import io
import os.path
import re
import csv

import MySQLdb as mysql

from bs4 import BeautifulSoup
from selenium import webdriver

import config
import googleDefs

# Instantiate logger
logging.basicConfig(filename=config.logging_file, filemode='w', level=logging.DEBUG)

class BoldOptionScraper:
    """
    Scrapes bold product options from a product page (only does dropdowns for now)
    """
    def __init__(self, product_handle, product_url, **kwargs):
        self.product_handle = product_handle
        self.product_url = product_url

        self.options = []
        self.page_source = ''
        self.product_page_source_file = 'cache/product_pages/%s.html' %(product_handle)

        set_no_options = kwargs.get('set_no_options', False)
        if set_no_options == True:
            self.__set_no_options()

        refresh_cache = kwargs.get('refresh_cache', False)
        if refresh_cache == True and self.options_available():
            self.__refresh_cache()

        if self.options_available():
            self.__get_page_source()
            self.__get_options_from_page_source()
        else:
            logging.debug("Product %s is indicated by its cache file not to have product options, skipping" %(self.product_handle))

    def __set_no_options(self):
        "Sets up the cache file to instruct BoldOptionScraper not to retrieve options for this file"
        # Create path if it doesn't exist.
        if not os.path.exists(os.path.dirname(self.product_page_source_file)):
            try:
                os.makedirs(os.path.dirname(self.product_page_source_file))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        page_source_file = open(self.product_page_source_file, 'w+')
        page_source_file.write("NOOPTIONS")

    def options_available(self):
        if os.path.isfile(self.product_page_source_file):
            check_file = open(self.product_page_source_file, 'r')
            if check_file.read() == "NOOPTIONS":
                check_file.close()
                return False
            check_file.close()
        return True

    def __refresh_cache(self):
        "Deletes the cache. Useful for updating products, or downloading the product page again after failed attempts"
        if os.path.isfile(self.product_page_source_file):
            os.remove(self.product_page_source_file)
        else:
            logging.warning("Attempted to delete cache file for product %s, but cache doesn't exist" %(self.handle))


    def __get_page_source(self):
        "Attempts to retrieve page_source from cache, otherwise page_source is downloaded and stored in cache"
        # If cache exists, retrieve options from cache
        if os.path.isfile(self.product_page_source_file):
            logging.debug("Retrieving options for Product %s from cache" %(self.product_handle))
            self.page_source = open(self.product_page_source_file, 'r')
        # Otherwise, retrieve it from shopify
        else:
            # Create path if it doesn't exist.
            if not os.path.exists(os.path.dirname(self.product_page_source_file)):
                try:
                    os.makedirs(os.path.dirname(self.product_page_source_file))
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
            # initiate the browser, grab the page, and store it
            logging.debug("Retrieving options for Product %s from shopify" %(self.product_handle))
            browser = webdriver.PhantomJS('phantomjs')
            browser.get(self.product_url)
            self.page_source = browser.page_source
            page_source_file = open(self.product_page_source_file, 'w+')
            page_source_file.write(self.page_source)

    def __get_options_from_page_source(self):
        soup = BeautifulSoup(self.page_source, "html.parser")
        soup_bold_option_dropdown = soup.find_all('div', {'class':'bold_option_dropdown'})
        for item in soup_bold_option_dropdown:
            # Grab the title, remove the asterisk since it's not needed
            option_title = item.find('span', {'class':'bold_option_title'}).text.replace('*','').strip()
            # Grab the attributes, remove the first option since it's not needed
            attribute_elements = item.find_all('option')
            attributes = [attribute.text.strip() for attribute in attribute_elements]
            del attributes[0]
            self.options.append((option_title, attributes))

    def get_options(self):
        options = []
        for option_attribute_pair in self.options:
            option = option_attribute_pair[0]
            attribute = option_attribute_pair[1]
            options.append(Option(option, attribute))
        return options

class Option:
    attributes = []

    def __init__(self, title, attributes, **kwargs):
        self.title = title
        self.attributes = attributes
        self.handle = Product.get_handle(title)
        self.id = kwargs.get('id', '')

    def __repr__(self):
        return self.handle

    def __get_ids_matching_handle(self):
        with DB() as con:
            cur = con.cursor()
            statement = 'select options_id from options where options_handle = "%s"' %(self.handle)
            cur.execute(statement)
            ids = [int(row[0]) for row in cur.fetchall()]
            return ids

    def __get_option_insert_statement(self):
        insert_statement = 'INSERT INTO options (options_handle, options_title) VALUES ("%s", "%s");' %(self.handle, self.title)
        return insert_statement

    def __get_attribute_insert_statement(self, option_id, attribute_title):
        insert_statement = 'INSERT INTO attributes (options_id, attributes_title) VALUES ("%s", "%s");' %(option_id, attribute_title)
        return insert_statement

    def print(self):
        print(self.title)
        for attribute in self.attributes:
            print("> %s" %(attribute))


    def get_option(id):
        "Returns an option object from the database given an id"
        with DB() as con:
            try:
                cur = con.cursor()
                option_id_statement = 'select options_title from options where options_id = "%s"' %(id)
                attributes_id_statement = 'select attributes_title from attributes where options_id = "%s"' %(id)

                cur.execute(option_id_statement)
                option_title = cur.fetchall()[0][0]
                if option_title == '':
                    raise ValueError("Option ID '%s' doesn't exist in DB")

                cur.execute(attributes_id_statement)
                attributes = [str(attribute[0]) for attribute in cur.fetchall()]

                option = Option(option_title, attributes, id=id)
                return option
            except mysql.Error as e:
                print("Problem while saving an option to database")
                #print("Error %d: %s" % (e.args[0], e.args[1]))
                print(e)
                print(cur)
                raise ValueError('SQL ERROR: %s, \nstatement: %s' %(e, s))

    def __identical_attribute_exists(self):
        "Returns true if an option with an identical title and identical attributes already exists in DB"
        options_with_identical_title = [Option.get_option(id) for id in self.__get_ids_matching_handle()]
        identical_attributes_exists = False
        if options_with_identical_title:
            for option in options_with_identical_title:
                if sorted(self.attributes) == sorted(option.attributes):
                    identical_attributes_exists = True
                    return True
                    break
        return False

    def __get_id(self):
        "Returns true if an option with an identical title and identical attributes already exists in DB"
        options = []
        for id in self.__get_ids_matching_handle():
            option = Option.get_option(id)
            option_id = id
            options.append((option, option_id))

        for option in options:
            if sorted(self.attributes) == sorted(option[0].attributes):
                return option[1]

    def associate_with_product(self, product_handle):
        with DB() as con:
            try:
                # check if id is set on the object, otherwise use __get_id to retrieve it from the database
                if hasattr(self, "id") and self.id != '':
                    option_id = self.id
                else:
                    option_id = self.__get_id()

                # Get product
                product = Product.get_product(product_handle)
                products_id = product.id

                # Check if option is already associated with the product
                product_already_has_option = False
                product_options = product.get_options()
                for product_option in product_options:
                    if product_option.id == option_id:
                        product_already_has_option = True
                        break

                if option_id and products_id and not product_already_has_option:
                    cur = con.cursor()
                    o_p_statement = 'insert into options_products (options_id, products_id) values (%d, %d)' %(option_id, products_id)
                    cur.execute(o_p_statement)
                    con.commit()
                    logging.debug('Associating option "%s: %s" to product "%s"' %(option_id, self.handle, product_handle))
                elif product_already_has_option:
                    logging.debug('Option "%s: %s" already associated to product "%s", skipping' %(option_id, self.handle, product_handle))
                else:
                    raise ValueError("An error occured while associating option with product")
            except mysql.Error as e:
                print("Problem while saving an option to database")
                #print("Error %d: %s" % (e.args[0], e.args[1]))
                print(e)
                print(cur)
                raise ValueError('SQL ERROR: %s, \nstatement: %s' %(e, s))

    def save(self, cur):
        try:
            if not self.__identical_attribute_exists():
                # Insert option into db
                option_s = self.__get_option_insert_statement()
                cur.execute(option_s)
                option_id = cur.lastrowid
                # Set id on object, in case associate_with_product is invoked later
                self.id = option_id
                logging.debug('inserting option "%s" in DB' %(self.handle))

                # Insert attributes into db, and associate them with the option
                for attribute in self.attributes:
                    logging.debug('associating attribute "%s" to option "%s"  in DB' %(attribute, self.handle))
                    option_a = self.__get_attribute_insert_statement(option_id, attribute)
                    cur.execute(option_a)
            else:
                logging.debug('Option with title "%s", and identical attributes exists in db, skipping insert' %(self.handle))
        except mysql.Error as e:
            print("Problem while saving an option to database")
            #print("Error %d: %s" % (e.args[0], e.args[1]))
            print(e)
            print(cur)
            raise ValueError('SQL ERROR: %s, \nstatement: %s' %(e, s))

class ShopifyCSV:
    mappings = {
        "Handle" : "handle",
        "Title" : "title",
        "Body (HTML)" : "desc",
        "Vendor" : "vendor",
        "Type" : "NONE",
        "Tags" : "tags",
        "Published" : "NONE",
        "Option1 Name" : "NONE", # NOTE: For use with datafeedwatch, subject to change
        "Option1 Value" : "g_color", # NOTE: For use with datafeedwatch, subject to change
        "Option2 Name" : "NONE",
        "Option2 Value" : "NONE",
        "Option3 Name" : "NONE",
        "Option3 Value" : "NONE",
        "Variant SKU" : "sku",
        "Variant Grams" : "NONE",
        "Variant Inventory Tracker" : "NONE",
        "Variant Inventory Qty" : "NONE",
        "Variant Inventory Policy" : "NONE",
        "Variant Fulfillment Service" : "NONE",
        "Variant Price" : "price",
        "Variant Compare At Price" : "NONE",
        "Variant Requires Shipping" : "NONE",
        "Variant Taxable" : "NONE",
        "Variant Barcode" : "NONE",
        "Image Src" : "img_url",
        "Image Alt Text" : "NONE",
        "Gift Card" : "NONE",
        "Google Shopping / MPN" : "NONE",
        "Google Shopping / Age Group" : "g_age_group",
        "Google Shopping / Gender" : "g_gender",
        "Google Shopping / Google Product Category" : "g_product_category",
        "SEO Title" : "NONE",
        "SEO Description" : "NONE",
        "Google Shopping / AdWords Grouping" : "NONE",
        "Google Shopping / AdWords Labels" : "NONE",
        "Google Shopping / Condition" : "NONE",
        "Google Shopping / Custom Product" : "NONE",
        "Google Shopping / Custom Label 0" : "NONE",
        "Google Shopping / Custom Label 1" : "NONE",
        "Google Shopping / Custom Label 2" : "NONE",
        "Google Shopping / Custom Label 3" : "NONE",
        "Google Shopping / Custom Label 4" : "NONE",
        "Variant Image" : "NONE",
        "Variant Weight Unit" : "NONE",
    }

    def __tmp_handle_none_defaults(self, mapping, product):
        "to be removed later, for handling none values"
        tmp_none_defaults = {
            "Google Shopping / MPN" : product.sku,
            "Google Shopping / Condition" : "new",
            "Published" : "true",
        }

        for key, value in tmp_none_defaults.items():
            if key == mapping:
                return value

        # If you can't find anything, return nothing
        return ''


    def __init__(self, collections):
        logging.debug('Google shopify_csv instantiated')
        self.collections = collections
        self.products = []
        self.shopify_csv_str = ''
        self.added_product_handles = []

    def export_csv(self, filename):
        "exports csv to a file"
        logging.info('- Exporting Shopify CSV to "%s"'% (filename))
        print('Exporting Shopify CSV to "%s"...'% (filename))
        with codecs.open(filename, 'w', "utf-8") as csv_file:
            csv_file.write(self.shopify_csv_str)

    def build_shopify_csv(self):
        "Builds a google shopify_csv"
        logging.info('- Building Shopify CSV')
        print('Building Shopify CSV...')

        # Add products to the shopify_csv
        for collection in self.collections:
            for product in collection.products:
                if product.handle not in self.added_product_handles:
                    self.__add_product(product)
                else:
                    logging.warn('Skipped product %s: already in shopify_csv' %(product))

        # Create shopify_csv CSV
        self.__build_csv()

    def verify_g_product_category(g_product_category):
        "Verifies that a category is in googleDefs.google_product_category"
        if g_product_category in googleDefs.google_product_category:
            return True
        else:
            return False

    def __verify_product(self, product):
        "Verifies a product can be added to a shopify_Csv"
        can_be_added = True
        failing_condition = None

        conditions = {
            'product_not_duplicate' : (product.handle not in self.added_product_handles),
            'product_has_id' : ( (product.sku and product.sku != '')),
            'product_has_title' : (product.title and product.title != ''),
            'product_has_description' : (product.desc and product.desc != ''),
            'product_has_image_link' : (product.img_url and product.img_url != ''),
            #'product_has_availibility' : (product.img_url and product.img_url != ''),
            'product_has_price' : (product.price and product.price != '') ,
            #'product_has_brand' : (product.brand and product.brand != '') ,
        }

        for condition_name, condition in conditions.items():
            if not condition:
                failing_condition = condition_name
                can_be_added = False
                break

        if can_be_added:
            return True
        else:
            logging.warn('Product %s failed to add due to failing condition %s' %(product, failing_condition))
            return False

    def __set_defaults(self, **kwargs):
        "Used to set default values NONE mappings"

    def __format_csv_tags(self, tags):
            # escape double quotes
            tags = tags.replace('"','""')
            tags = '"%s"' % (tags)
            return tags

    def __format_csv_description(self, description):
            # escape double quotes
            description = description.replace('"','""')
            description = '"%s"' % ( description)
            return description

    def __format_csv_mapping(self, mapping, attribute, product):
        "Returns a properly formatted str representing the attribute of the respective mapping"
        if mapping == "Title":
            return self.__format_csv_description(product.title)
        if mapping == "Body (HTML)":
            return self.__format_csv_description(product.desc)
        if mapping == "Tags":
            return self.__format_csv_tags(product.tags)
        if mapping == "Option1 Name":
            return "GOOGLE_SHOPPING_COLORS"
        if mapping == "Variant Fulfillment Service":
            return "manual"
        if mapping == "Variant Inventory Policy":
            return "continue"
        elif attribute == "NONE":
            return self.__tmp_handle_none_defaults(mapping, product)
        else:
            return product.__getattribute__(attribute)

    def __build_csv(self):
        # Build csv_header
        csv_header = ''
        for i, mapping in enumerate(self.mappings):
            if i < len(self.mappings) - 1:
                csv_header += "%s," % (mapping)
            else:
                csv_header += "%s\n" % (mapping)

        # Build csv_body
        csv_body = ''
        for product in self.products:
            for i, unpacked in enumerate(self.mappings.items()):
                mapping = unpacked[0]; attribute = unpacked[1]
                attribute = attribute.replace(", ","") # get rid of tabs if they have it
                if i < len(self.mappings) - 1:
                    csv_body += "%s," % (self.__format_csv_mapping(mapping, attribute, product))
                else:
                    csv_body += "%s\n" % (self.__format_csv_mapping(mapping, attribute, product))
        self.shopify_csv_str = csv_header + csv_body



    def __add_product(self, product):
        if self.__verify_product(product):
            logging.debug('Adding product %s to the shopify_csv' %(product))
            self.added_product_handles.append(product.handle)
            self.products.append(product)

class GoogleFeed:
    # Current mappings of required google feed fields. Fields that aren't implemented fully yet marked as NONE
    mappings = {
        "id" : "sku",
        "title" : "title",
        "description" :"desc",
        "link" : "url",
        "image_link": "img_url",
        "price" : "price",
        "availability" : "NONE",
        "google_product_category" : "g_product_category",
        "brand" : "vendor",
        "MPN" : "NONE",
        "condition" : "NONE",
        "age_group" : "g_age_group",
        "color" : "g_color",
        "gender" : "g_gender",
    }

    # These map elements to attributes that aren't part of the original Product class
    optional_mappings = {
        "size" : "size",
        "item_group_id" : "item_group_id",
    }

    mappings = dict(mappings, **optional_mappings)

    def __tmp_handle_none_defaults(self, mapping, product):
        "to be removed later, for handling none values"
        tmp_none_defaults = {
            "availability" : "in stock",
            "brand" : "eztuxedo",
            "MPN" : product.sku,
            "condition" : "new",
            "size" : ""
        }

        for key, value in tmp_none_defaults.items():
            if key == mapping:
                return value

    def __init__(self, collections):
        logging.debug('Google feed instantiated')
        self.collections = collections
        self.products = []
        self.sizes = []
        self.feed_str = ''
        self.added_product_handles = []
        self.added_product_ids = []
        self.excluded_product_handles = []
        self.excluded_brands = []
        self.user_defaults = {}
        self.attribute_product_title_filters = {}
        self.include_option_names_in_title_flag = False

    def handle_size(self, size_handle, size_modifiers=None):
        """
        Instructs the Google Feed generator to process products with the specified size option.
        The user may also specify title_filters and attribute_product_title_filters, which allow the user to
        modify size option titles and attributes before they are inserted into the feed
        """
        #title_filters=[], attribute_product_title_filters=[]

        # specification for size_modifiers
        default_size_modifiers = {
            # Regex for extracting price from an attribute. These will be added to the product's price
            # The first paranthesized group will be captured as the price (group(1))
            'price_attribute_extraction_regex' : None,

            # Regexes for filtering text out of an attribute
            'attribute_regexes' : [],

            #Run strip() on attribute str
            'strip_attribute' : True,
        }

        if size_modifiers == None:
            size_modifiers = default_size_modifiers

        self.sizes.append((size_handle, size_modifiers))

    def filter_attribute_title_in_product_title(self, option_handle, filter_method):
        "Allows a user to define a method to filter attribute names for an option"
        self.attribute_product_title_filters[option_handle] = filter_method

    def export_tsv(self, filename):
        "exports tsv to a file"
        logging.info('- Exporting Google Feed to "%s"'% (filename))
        print('Exporting Google feed to "%s"...'% (filename))
        with open(filename, 'w') as tsv_file:
            tsv_file.write(self.feed_str)

    def __get_sizes(self):
        return [size[0] for size in self.sizes]

    def __get_product_size_option(self, product):
        "returns a product size option if it exists, or None if it doesn't"
        product_options = product.get_options()
        sizes = self.__get_sizes()
        size_option = None
        for product_option in product_options:
            if product_option.handle in sizes and self.__verify_product(product):
                size_option = product_option
                break
        return size_option

    def __process_product_size_attribute(self, product,  product_size_option, product_size_attribute):
        "Returns a filtered attribute, and processes any needed changes for product"
        # Get size_modifiers
        size_modifers = None
        for size_option_handle, size_modifier_dict in self.sizes:
            if size_option_handle == product_size_option.handle:
                size_modifiers = size_modifier_dict

        # process size_modifiers
        if size_modifiers:
            new_attribute = product_size_attribute
            if size_modifiers['price_attribute_extraction_regex']:
                regex = size_modifiers['price_attribute_extraction_regex']
                m_price = re.search(regex, product_size_attribute)
                if m_price:
                    price = float(m_price.group(1))
                    old_price = product.price
                    new_price = product.price + price
                    product.price = new_price
                    logging.debug("changing price on %s, old: '%s' new: '%s'" %(product, old_price, new_price))
            if size_modifiers['attribute_regexes']:
                for regex in size_modifiers['attribute_regexes']:
                    match = re.search(regex, product_size_attribute)
                    if match:
                        remove_str = match.group(0)
                        old_attribute = new_attribute
                        new_attribute = old_attribute.replace(remove_str, "")
                        logging.debug("Filtering on %s, old: '%s' new: '%s'" %(product, old_attribute, new_attribute))
            if size_modifiers['strip_attribute']:
                old_attribute = new_attribute
                new_attribute = old_attribute.strip()
                logging.debug("Stripping attribute on  %s, old: '%s' new: '%s'" %(product, old_attribute, new_attribute))
            return new_attribute
        else:
            raise ValueError('Tried processing product size, but size_modifiers does not exist')

    def __add_attribute_to_product_title(self, product, new_attribute):
        "Adds the attribute title to the product title"
        # Check if attribute in product title filters exist, and process them
        option_handles = [option.handle for option in product.get_options()]
        for option_handle, filter_method in self.attribute_product_title_filters.items():
            if option_handle in option_handles:
                old_attribute = new_attribute
                new_attribute = filter_method(new_attribute)
                logging.debug("Attribute title filter found for %s: '%s' changed to '%s'" %(option_handle, old_attribute, new_attribute))

        # Create new title
        new_title = "%s (%s)" %(product.title, new_attribute)
        return new_title

    def __add_product_size_variants(self, product, product_size):
        "Adds product variants for products possessing a handled size option"
        self.added_product_handles.append(product.handle)
        self.added_product_ids.append(product.sku)
        handle = product.handle
        for attribute in product_size.attributes:
            new_product = copy.copy(product)
            # New handle needed because products with sizes are split into seperate products
            new_handle = handle + '-' + Product.get_handle(attribute)
            new_attribute = self.__process_product_size_attribute(new_product, product_size, attribute)
            old_sku = product.sku
            new_sku = product.sku + '-' + Product.get_handle(new_attribute)

            new_product.handle = new_handle
            new_product.size = new_attribute
            new_product.sku = new_sku
            new_product.item_group_id = old_sku
            new_product.mpn = old_sku

            if self.include_option_names_in_title_flag:
                new_product.title = self.__add_attribute_to_product_title(new_product, new_attribute)

            self.__add_product(new_product)

    def __set_optional_element_defaults(self, product):
        for key, value in self.optional_mappings.items():
            setattr(product,value,'')

    def build_feed(self):
        "Builds a google feed"
        logging.info('- Building Google Feed')
        print('Building Google Feed...')

        # Add products to the feed
        for collection in self.collections:
            for product in collection.products:
                self.__set_optional_element_defaults(product)

                product_not_already_added = product.handle not in self.added_product_handles
                product_handle_not_excluded = product.handle not in self.excluded_product_handles
                product_brand_not_excluded = product.vendor not in self.excluded_brands
                if product_not_already_added:
                    if product_handle_not_excluded and product_brand_not_excluded:
                        product_size = self.__get_product_size_option(product)
                        if product_size:
                            self.__add_product_size_variants(product,product_size)
                        else:
                            self.__add_product(product)
                    else:
                        logging.info('Skipped product %s: excluded' %(product))
                else:
                    logging.warn('Skipped product %s: already in feed' %(product))

        # Create feed TSV
        self.__build_tsv()

    def verify_g_product_category(g_product_category):
        "Verifies that a category is in googleDefs.google_product_category"
        if g_product_category in googleDefs.google_product_category:
            return True
        else:
            return False

    def __verify_product(self, product):
        "Verifies a product can be added to a Google Feed"
        can_be_added = True
        warning_issued = False

        failing_condition = None
        warnings = []

        conditions = {
            'product_not_duplicate' : (product.handle not in self.added_product_handles),
            'product_id_not_duplicate' : (product.sku not in self.added_product_ids),
            'product_has_id' : ( (product.sku and product.sku != '')),
            'product_has_title' : (product.title and product.title != ''),
            'product_has_description' : (product.desc and product.desc != ''),
            'product_has_link' : (product.url and product.url != ''),
            'product_has_image_link' : (product.img_url and product.img_url != ''),
            #'product_has_availibility' : (product.img_url and product.img_url != ''),
            'product_has_price' : (product.price and product.price != '') ,
            #'product_has_brand' : (product.brand and product.brand != '') ,
            'product_title_less_or_equal_150' : (len(product.title) <= 150) ,
        }

        warning_conditions = {
            'product_title_less_or_equal_70' : (len(product.title) <= 70) ,
        }

        for condition_name, condition in conditions.items():
            if not condition:
                failing_condition = condition_name
                can_be_added = False
                break

        for condition_name, condition in warning_conditions.items():
            if not condition:
                warning_issued = True
                warnings.append(condition_name)

        if can_be_added:
            if warning_issued:
                for warning in warnings:
                    logging.warn('Warning condition %s issued while processing product %s' %(warning, product) )

            return True
        else:
            logging.warn('Product %s failed to add due to failing condition %s' %(product, failing_condition))
            return False

    def exclude_product(self, handle):
        "Prevents product from being inserted into the feed"
        self.excluded_product_handles.append(handle)

    def exclude_brand(self, brand_title):
        "Prevents product with brand name (vendor name) from being inserted into the feed "
        self.excluded_brands.append(brand_title)

    def set_default_color(self, color):
        "Used to set a default color for products that don't have one"
        self.user_defaults['g_color'] = color

    def include_option_names_in_title(self):
        "For products with options, includes the option name in the title"
        self.include_option_names_in_title_flag = True


    def __set_defaults(self, **kwargs):
        pass
        "Used to set default values NONE mappings"

    def __format_tsv_description(self, description):
        "Responsible for cleaning and formatting descriptions before inserting them into the feed"
        description = BeautifulSoup(description, 'lxml')

        # Remove script, style, img elements from description if they exist
        elements_to_remove = ["img", "script", "style"]
        for element in description(elements_to_remove):
            element.extract()

        # Remove html elements from description
        description = description.text

        # Strip description
        description = description.strip()

        # Escape newlines, tabs, carriage returns, backslashes, and quotes
        description = description.replace("\\","\\\\")
        description = description.replace("\t","\\t")
        description = description.replace("\r","\\r")
        description = description.replace("\"", "\"\"") # Double Quotes to escape quotes in the description

        return description

    def __format_tsv_price(self, price):
        return '{:,.2f} USD'.format(price)

    def __clean_product_attribute(self, product, attribute):
        "Cleans attribute before inserting product into feed"
        if attribute == 'sku':
            # Remove # from sku
            product.sku = product.sku.replace("#", "")


    def __format_tsv_mapping(self, mapping, attribute, product):
        "Returns a properly formatted str representing the attribute of the respective mapping"
        result_attribute = ""
        if mapping == "description":
            result_attribute = self.__format_tsv_description(product.desc)
        elif mapping == "price":
            result_attribute = self.__format_tsv_price(product.price)
        elif mapping == "MPN" and hasattr(product, 'mpn'):
            result_attribute = product.mpn
        elif attribute == "NONE":
            result_attribute = self.__tmp_handle_none_defaults(mapping, product)
        else:
            result_attribute = product.__getattribute__(attribute)

        # Quote wrap the result_attribute
        result_attribute = '"%s"' %(result_attribute)

        return result_attribute

    def __build_tsv(self):
        mappings = self.mappings
        # Build tsv_header
        tsv_header = ''
        for i, mapping in enumerate(mappings):
            if i < len(mappings) - 1:
                tsv_header += "%s\t" % (mapping)
            else:
                tsv_header += "%s\n" % (mapping)

        # Build tsv_body
        tsv_body = ''
        for product in self.products:
            for i, unpacked in enumerate(mappings.items()):
                mapping = unpacked[0]; attribute = unpacked[1]
                attribute = attribute.replace("\t","") # get rid of tabs if they have it
                if i < len(mappings) - 1:
                    tsv_body += "%s\t" % (self.__format_tsv_mapping(mapping, attribute, product))
                else:
                    tsv_body += "%s\n" % (self.__format_tsv_mapping(mapping, attribute, product))
        self.feed_str = tsv_header + tsv_body

    def __process_user_defaults(self, product):
        for attribute, value in self.user_defaults.items():
            if hasattr(product, attribute) and getattr(product, attribute) == '':
                setattr(product, attribute, value)

    def __add_product(self, product):
        "Adds the product to the Google Feed"
        if self.__verify_product(product):
            logging.debug('Adding product %s to the feed' %(product))

            # Clean product attributes before inserting into feed
            self.__clean_product_attribute(product, 'sku')

            # Process defaults for attributes configured by the user
            self.__process_user_defaults(product)

            # Add handles and ids to 'already added' lists so we don't end up adding them again
            self.added_product_handles.append(product.handle)
            self.added_product_ids.append(product.sku)

            # Finally, add the product to the list.
            self.products.append(product)

class DB:
    """
    Sets up a db
    """
    def __init__(self, **kwargs):
        try:
            self.con = mysql.connect(config.db_host, config.db_user, config.db_password, config.db_name)
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
    fields = { "id":"products_id", "handle":"products_handle", "title":"products_title", "price":"products_price", "desc":"products_desc", "vendor":"products_vendor", "sku":"products_sku", "tags":"products_tags", "url":"products_url", "img_url":"products_img_url", "g_age_group":"products_g_age_group", "g_color":"products_g_color", "g_product_category":"products_g_product_category", "g_gender":"products_g_gender" }
    sql_field_type = { "products_id":"%s", "products_handle":"%s", "products_title":"%s", "products_price":"%f", "products_desc":"%s", "products_vendor":"%s", "products_sku":"%s", "products_tags":"%s", "products_url":"%s", "products_img_url":"%s", "products_g_age_group":"%s", "products_g_color":"%s", "products_g_product_category":"%s","products_g_gender":"%s"}
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
        self.g_gender = kwargs.get('g_gender','')
        #logging.debug('Product object instantiated, handle: %s' % (self.handle))

    def print_product(self):
        p_str = "Product Handle: %s" %(self.handle)
        for field in self.fields:
            p_str += "%s: %s\n" %(field,self.__getattribute__(field))
        return p_str

    def get_all_products():
        with DB() as con:
            product_handles = []
            cur = con.cursor()
            statement = "select products_handle from products"
            cur.execute(statement)
            for row in cur.fetchall():
                handle = row[0]
                product_handles.append(handle)
            return [Product.get_product(handle) for handle in product_handles]

    def get_orphans():
        orphans = []
        all_products = Product.get_all_products()
        for product in all_products:
            if not product.has_collection():
                orphans.append(product)
        return orphans

    def has_collection(self):
        with DB() as con:
            cur = con.cursor()
            statement = "select products_handle from products join products_collections on products.products_id=products_collections.products_id where products_handle = '%s'" %(self.handle)
            cur.execute(statement)
            has = cur.fetchall()
            if has:
                return True
            else:
                return False

    def get_options(self):
        "Returns options associated with the product"
        with DB() as con:
            if not hasattr(self, 'id'):
                raise ValueError("Product object doesn't have an associated ID")
            cur = con.cursor()
            statement = "select options_id from options_products where products_id = %d" %(self.id)
            cur.execute(statement)
            option_ids = [row[0] for row in cur.fetchall()]
            options = [Option.get_option(option_id) for option_id in option_ids]
            return options

    def scrape_bold_product_options(self):
        "Scrapes bold product options from product page and inserts them into the DB"
        logging.debug("Scraping product options for %s" %(self.handle))
        attempts = 1

        # First attempt to retrieve product options
        scraper = BoldOptionScraper(self.handle, self.url)
        options = scraper.get_options()

        # If first attempt failed, try again to retrieve product options from web page
        while not options and attempts <= config.max_product_option_retrieval_attempts \
              and scraper.options_available():
            logging.debug("Attempt %d to find options for product %s failed." %(attempts, self.handle))
            print("Attempt %d to find options for product %s failed." %(attempts, self.handle))
            scraper = BoldOptionScraper(self.handle, self.url, refresh_cache=True)
            options = scraper.get_options()
            attempts += 1

        if options:
            with DB() as con:
                cur = con.cursor()
                for option in options:
                    option.save(cur)
                    con.commit()
                    option.associate_with_product(self.handle)
        else:
            logging.info("No options found for product %s" %(self.handle))
            if scraper.options_available():
                BoldOptionScraper(self.handle, self.url, set_no_options=True)

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

    def set_g_age_group(self, g_age_group):
        if g_age_group.lower() in googleDefs.age_group:
            log_str = 'setting g_age_group "%s" for "%s"' %(g_age_group, self.handle)
            logging.debug(log_str)

            self.g_age_group = g_age_group
        else:
            bad_log_str = 'Attempted to set product %s to malformed g_age_group' % (self.handle)
            logging.warn(bad_log_str)

    def set_g_gender(self, g_gender):
        if g_gender.lower() in googleDefs.gender:
            log_str = 'setting g_gender "%s" for "%s"' %(g_gender, self.handle)
            logging.debug(log_str)

            self.g_gender = g_gender
        else:
            bad_log_str = 'Attempted to set product %s to malformed g_gender' % (self.handle)
            logging.warn(bad_log_str)

    def set_g_product_category(self, g_product_category):
        if GoogleFeed.verify_g_product_category(g_product_category):
            log_str = 'setting g_product_category "%s" for "%s"' %(g_product_category, self.handle)
            logging.debug(log_str)

            self.g_product_category = g_product_category
        else:
            bad_log_str = 'Attempted to set product %s to malformed g_product_category' % (self.handle)
            logging.warn(bad_log_str)

    def has_tag(self, tag):
        tags = [tag.lower() for tag in self.get_tags()]
        if tag.lower() in tags:
            return True
        else:
            return False


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
                logging.debug('Updating product "%s" in DB' %(self.handle))
                s = self.__get_save_statement('update', ignore=['products_id', 'products_handle'])
                cur.execute(s)
            # Insert
            else:
                logging.debug('inserting product "%s" in DB' %(self.handle))
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
                logging.debug("Added color %s for %s (before eliminating nested words)" %(color, self.handle))

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
        else:
            # Assign g_color to the output of color_list_to_string which formats it to google's specifications
            colors_str = Product.color_list_to_string(colors)
            logging.debug('Product "%s" assigned colors "%s"' %(self.handle, colors_str))
            self.g_color = colors_str

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

    def set_g_age_group(self, g_age_group):
        "Propogates a g_age_group to all of a collection's products and saves them to db"
        logging.info('- Setting g_age_group "%s" for Collection "%s"' %(g_age_group, self.handle))
        print('Setting g_age_group "%s" for Collection "%s"...'%(g_age_group, self.handle))

        with DB() as con:
            cur = con.cursor()
            if g_age_group.lower() in googleDefs.age_group:
                for product in self.products:
                    product.set_g_age_group(g_age_group)
                    product.save(cur)
            con.commit()

    def set_g_gender(self, g_gender):
        "Propogates a g_gender to all of a collection's products and saves them to db"
        logging.info('- Setting g_gender "%s" for Collection "%s"'%(g_gender, self.handle))
        print('Setting g_gender "%s" for Collection "%s"...'%(g_gender, self.handle))
        with DB() as con:
            cur = con.cursor()
            if g_gender.lower() in googleDefs.gender:
                for product in self.products:
                    product.set_g_gender(g_gender)
                    product.save(cur)
            con.commit()

    def set_g_product_category(self, g_product_category):
        "Propogates a g_product_category to all of a collection's products and saves them to db"
        with DB() as con:
            cur = con.cursor()
            if GoogleFeed.verify_g_product_category(g_product_category):
                logging.info('- Setting g_product_category "%s" for Collection "%s"'%(g_product_category, self.handle))
                print('Setting g_product_category "%s" for Collection "%s"...'%(g_product_category, self.handle)) 
                for product in self.products:
                    product.set_g_product_category(g_product_category)
                    product.save(cur)
                con.commit()
            else:
                bad_log_str = 'Attempted to set collection %s to malformed g_product_category' % (self.handle)
                logging.warn(bad_log_str)

    def scrape_bold_product_options(self):
        "Scrapes options for all products in collection and inserts them into the database"
        logging.info('-Scraping bold product options for Collection "%s"'%(self.handle))
        print('Scraping bold product options for Collection "%s"'%(self.handle))
        for product in self.products:
            product.scrape_bold_product_options()

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
            statement = "SELECT p.products_id FROM (products AS p) LEFT JOIN products_collections AS pc ON p.products_id=pc.products_id RIGHT JOIN collections AS c ON pc.collections_id=c.collections_id WHERE c.collections_handle = '%s' AND p.products_id IS NOT NULL;" %(self.handle)
            cur.execute(statement)
            rows = cur.fetchall()
            if rows:
                product_ids = [row[0] for row in rows]
                self.products = self.__get_products_from_ids(product_ids)
            else:
                pass
            # get_collection_id_statement = "select collections_id from collections where collections_handle = '%s'"
            # get_products_statement = "select products_id from products_collections where collections_id = '%s'"
            # product_ids = []

            # # get ID of collection
            # cur.execute(get_collection_id_statement % (self.handle))
            # collections_id = cur.fetchone()[0]
            # print(collections_id)

            # # get product IDs matching collection ID
            # cur.execute(get_products_statement % (collections_id))
            # for row in cur.fetchall():
            #     product_ids.append(row[0])

            # feed them into get_productsFromIDs


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
        sql_tag_find_regex = "'(^\ *|,\ )%s(,\ *|\ *$)'" % (value)

        if variable == 'tag':
            if relation == 'equals':
                sql_statement_fragment = "products_tags REGEXP %s" % (sql_tag_find_regex)
            if relation == 'does not contain':
                sql_statement_fragment = "products_tags REGEXP %s" % (sql_tag_find_regex)
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
                s = insert_product_into_collection_statement % (product.id, collections_id)
                cur.execute(s)

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
        value = clean_sql(m.group(2))

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
    logging.info('- Importing collections from shopify html files')
    print('Importing collections from shopify html files...')
    # Extract titles and conditions from html, store them in collection_list
    collection_list = []
    # Don't add if collection contains a blacklisted word in the title
    blacklist = ['hidden', 'Hidden', 'HIDDEN', 'internal', 'Internal', 'INTERNAL',
                 'Newest Products', 'Best Selling Products', 'Featured Products', 'Home page', 'Unavailable']
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
                    # strip out apostrophes because they are ignored!!
                    # then append them to conditions list,
                    conditions.append(li.text.replace("'",""))
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
    logging.info('- Importing products from shopify csv: "%s"' %(csv_file.name))
    print('Importing products from shopify csv: "%s"...:' %(csv_file.name))
    with DB() as con:
        p_list = []
        reader = csv.DictReader(csv_file)

        for row in reader:
            isPublished = row["Published"]
            if isPublished == 'true':
                # Check if GShopping colors exists, and if so, grab it
                colors = ''
                if row["Option1 Name"] == 'GOOGLE_SHOPPING_COLORS':
                    colors = row["Option1 Value"]

                logging.debug('Importing product with handle %s from %s' % (row["Handle"], csv_file.name))
                p_list.append(Product(
                    row["Title"],
                    handle=row["Handle"],
                    price=float(row["Variant Price"]),
                    desc=row["Body (HTML)"],
                    vendor=row["Vendor"],
                    tags=row["Tags"],
                    img_url=row["Image Src"],
                    sku=row["Variant SKU"],
                    # -- #
                    g_age_group=row["Google Shopping / Age Group"],
                    g_color=colors,
                    g_product_category=row["Google Shopping / Google Product Category"],
                    g_gender=row["Google Shopping / Gender"],

                    ))
            elif isPublished == 'false':
                logging.debug('Skipped %s, pub value %s' % (row["Handle"], row["Published"]))
            else:
                logging.warn('Skipped %s: malformed Published value'% (row["Handle"]))

        for product in p_list:
            product.save(con.cursor())

        con.commit()
# -- misc functions --
def get_handle(title):
    return re.sub(r'\s', '-', title.lower()).replace("'","")

def clear_db():
    "Wipes the database clean"
    with DB() as con:
        logging.info('- Wiping Database')
        print("Wiping database...")
        cur = con.cursor()
        cur.execute('delete from products')
        cur.execute('delete from collections')
        cur.execute('delete from products_collections')
        con.commit()

def process_colors_for_all_products():
    logging.info('- Processing colors for all products')
    print("Processing colors for all products...",)
    with DB() as con:
        cur = con.cursor()
        for collection in Collection.get_collections():
            for product in collection.products:
                #print("Processing color for: %s" %(product.title))
                product.process_g_colors()
                product.save(cur)
        con.commit()

def set_default_g_age_group(g_age_group):
    with DB() as con:
        cur = con.cursor()
        if g_age_group.lower() in googleDefs.age_group:
            products = Product.get_all_products()
            print('Setting default g_age_group for all products to %s...' %(g_age_group))
            logging.info('- Setting default g_age_group for all products to "%s"' %(g_age_group))
            for product in products:
                #print("Saving g_age_group %s for: %s"%(g_age_group, product))
                product.set_g_age_group(g_age_group)
                product.save(cur)
        else:
            logging.warn('Attempted to set default g_age_group but g_age_group was malformed')
        con.commit()


def set_default_g_gender(g_gender):
    with DB() as con:
        cur = con.cursor()
        if g_gender.lower() in googleDefs.gender:
            products = Product.get_all_products()
            print('Setting default g_gender for all products to %s...' %(g_gender))
            logging.info('- Setting default g_gender for all products to "%s"' %(g_gender))
            for product in products:
                #print("Saving g_gender %s for %s"%(g_gender, product))
                product.set_g_gender(g_gender)
                product.save(cur)
        else:
            logging.warn('Attempted to set default g_gender but g_gender was malformed')
        con.commit()


def set_default_g_product_category(g_product_category):
    with DB() as con:
        if GoogleFeed.verify_g_product_category(g_product_category):
            cur = con.cursor()
            products = Product.get_all_products()
            print('Setting default g_product_category for all products to %s...' %(g_product_category))
            logging.info('- Setting default g_product_category for all products to "%s"' %(g_product_category))
            for product in products:
                product.set_g_product_category(g_product_category)
                product.save(cur)
        else:
            logging.warn('Attempted to set default g_product_category but g_product_category was malformed.')
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
