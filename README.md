# ShopTracker
## What is it?
ShopTracker can assist with managing your shopify store and is compatible with the bold productoptions plugin. It can use the data retrieved from shopify to create a feed for Google Shopping.

## dependencies
python 3.x (python-virtualenv, python-pip), mysql, phantomJS
Python extensions: mysqlclient, selenium, beautifulsoup4, lxml

## setup
Ensure python 3.x, python-virtualenv, python-pip, phantomJS, and mysql are installed on your system.

The python extensions mysqlclient, selenium, beautifulsoup4, and lxml python extensions should be installed in a virtualenv via pip.

### configuring a virtualenv and installing python dependencies:
*Always ensure you're in venv when running the program, or shoptracker may fail to start*
*(venv) should appear before your prompt*
~~~
virtualenv -p python3 venv

source venv/bin/activate

pip install mysqlclient

pip install selenium

pip install beautifulsoup4

pip install lxml
~~~

### Create database and add a shoptracker user
~~~
mysql -u root_user -pPassword
CREATE DATABASE `shoptracker_demo`;
GRANT ALL PRIVILEGES ON shoptracker_demo.* TO 'shoptracker_user'@'localhost' IDENTIFIED BY 'sh0ptr4ck3r';
~~~

### Configure database details in config.py
Copy config.py.example to config.py and configure db information, i.e.
~~~
...
# Database config
db_host = 'localhost'
db_name = 'shoptracker_demo'
db_user = 'shoptracker_user'
db_password = 'sh0ptr4ck3r'
...
~~~
Please take this time to look over other values in config.py.

### Run setup.py to create the database
Ensure you're in venv, and run
~~~
python setup.py
~~~

## usage 
### Overview
In order for ShopTracker to process your shopify site, you need two components: a shopify CSV export of your products, and collection data. 
Once you've retrieved these files, you must create one or more drivers. All operations are declared in drivers; it defines how ShopTracker processes your data and how the feed is generated. 
You are free to divide operations into however many drivers you'd like.

### Retrieving shopify export csv
In the shopify admin, go to Products -> All Products -> Export. Ensure the radio boxes "All Products" and "Plain CSV file" are ticked. Save the exported csv in the ShopTracker directory.

If the CSV is in a zip, extract it before proceeding

### Retrieving shopify collection data.
*WARNING: ShopTracker is not yet compatible with 'manual' collections. It only works with collections that are defined by conditions*
In the shopify admin, go to Collections. Save a copy of the collection html in the ShopTracker directory (in firefox, right click and save page as...).
If there are additional pages, repeat for each page. 

### Drivers
Drivers define all operations to be performed on your data. 
They must begin with the line
~~~
from shoptracker import *
~~~

Operations can be split into one or more driver files.
*For instance, it may be useful to split up your driver files initially to expedite testing to bypass computationally expensive tasks, such as importing products and collections, but combine them into one file once in production*

#### Initial setup and import
Create a file called driver_import.py, and add the following lines:
~~~ 
from shoptracker import *

# -- Initalization and importing --
# Clears the database
clear_db()

# Import shopify csv
import_csv_from_shopify(open('misc/products_export.csv', 'r'))

# Import shopify html pages containing collections
import_collections_from_shopify(open('c1.htm', 'r'), open('c2.htm', 'r'), open('c3.htm', 'r'))
~~~
This creates a driver file which clears the db and imports product and collection data into the database. Run it with python driver_import.py 

#### Helper functions
To get started, it's highly recommended to add these helper functions to your driver (to be added to the code at a later date):
~~~
# Helper functions
collections = Collection.get_collections()
def search_collections(search_str, negative_str=None):
    if negative_str:
        return [collection for collection in collections if collection.handle.find(search_str) != -1 and collection.handle.find(negative_str) == -1]
    else:
        return [collection for collection in collections if collection.handle.find(search_str) != -1]

def set_g_product_category_for_collections(collections, g_product_category):
    for collection in collections:
        collection.set_g_product_category(g_product_category)
~~~

These helper functions will assist when working with scraping bold product options, or google product attributes and related functions. 

search_collections accepts a string as input, and returns a list of collections that have a title containing the string

set_g_product_category_for_collections simply applies a g_product_category to a list of collections (explained in Google Product attributes and related functions)

#### Scraping bold product options
The bold product options plugin for shopify has not yet exposed their API to the public, so in order to retrieve product option data you must get them directly from the shopify pages. ShopTracker can automate this.

If you're using bold product options on your shopify site, you should define the operations to scrape options and attributes and import them into the database before proceeding. 

The options and attributes imported into the database affect how the feed is generated, so it's recommended to scrape product options only where they are relevant to the feed (i.e. shirt sizes are mandatory for shirt listings on google, so you should scrape those) 

It's highly recommended to create a seperate driver for scraping bold product options, as this may take a long time to complete depending on how many items are in your store.

Here's an example driver scraping collections with 'tuxedos', 'vests', and 'shirts' in the title.
~~~ 
from shoptracker import *
collections = Collection.get_collections()
def search_collections(search_str, negative_str=None):
    if negative_str:
        return [collection for collection in collections if collection.handle.find(search_str) != -1 and collection.handle.find(negative_str) == -1]
    else:
        return [collection for collection in collections if collection.handle.find(search_str) != -1]

tuxedos = search_collections('tuxedos')
for tuxedo in tuxedos:
    tuxedo.scrape_bold_product_options()

vests = search_collections('vests')
for vest in vests:
    vest.scrape_bold_product_options()

shirts = search_collections('shirts')
for shirt in shirts:
    shirt.scrape_bold_product_options()
~~~ 

The scraper may fail to retrieve any options while attempting to scrape a product that has them. *max_product_option_retrieval_attempts* in config.py defines how many times to scrape a product before giving up. This should be set to a minimum of 3, 5 or more is recommended. 

If you need to configure a path to phantomjs, this can be configured using the phantomjs_path variable on config.py 

#### Bold product Option scraping cache

Scraped pages are cached on the file system. If a scraped product is cached, it will not attempt to retrieve the page from the internet, and retrieves data from the cached copy instead. Likewise, If BoldOptionScraper failed to retrieve data for a product after max_product_option_retrieval_attempts, a file for that product containing the text 'NOOPTIONS' is created, informing BoldOptionScraper to skip that product.

If you'd like bold product options to scrape a product from the internet after its been cached, simply delete the respective html file from cache/product_pages

#### Google Product attributes and related functions
ShopTracker allows you to easily assign attributes such as as g_color, g_age_group, and g_product_category to collections of products. 

It's recommended to begin by setting default options, i.e. if you know most of your products are targetted for male adults, and are in the catagory 'Apparel & Accessories'
Once this is done, you may proceed with defining various google_attributes for your products.

*You can utilize the helper function set_g_product_category_for_collections to apply a g_product_category to a list of collections*

Here's a short example:
~~~
from shoptracker import *
# Helper functions
collections = Collection.get_collections()
def search_collections(search_str, negative_str=None):
    if negative_str:
        return [collection for collection in collections if collection.handle.find(search_str) != -1 and collection.handle.find(negative_str) == -1]
    else:
        return [collection for collection in collections if collection.handle.find(search_str) != -1]

def set_g_product_category_for_collections(collections, g_product_category):
    for collection in collections:
        collection.set_g_product_category(g_product_category)

# Set default options
set_default_g_age_group('adult')
set_default_g_gender('male')
set_default_g_product_category('Apparel & Accessories') 

# Looks at every product, extracts colors from title, and places google friendly colors into g_color field
process_colors_for_all_products()

# Set Boys Vests and Ties to 'kids' age group
c = Collection.get_collection(get_handle("Boys Vests and Ties"))
c.set_g_age_group("kids") 

# Set product_category for collections
# hats
hats = search_collections('hats')
set_g_product_category_for_collections(hats, 'Apparel & Accessories > Clothing Accessories > Hats')

# shoes
shoes = search_collections('shoes')
set_g_product_category_for_collections(shoes, 'Apparel & Accessories > Shoes')

# tuxedos
tuxedos = search_collections('tuxedos')
set_g_product_category_for_collections(tuxedos, 'Apparel & Accessories > Clothing > Suits > Tuxedos') 
~~~

#### Feed output
ShopTracker can currently export Google TSVs. A feed export can be defined in a driver as follows:
~~~ 
from shoptracker import *
# Create google feed and export
feed = GoogleFeed(Collection.get_collections())
feed.build_feed()
feed.export_tsv('feed.tsv')
~~~ 

#### Handling sizes in Google feed
If you want to handle sizes in Google feeds they must be explicity declared using handle_size. handle_size accepts two parameters, product option handle (i.e. 'jacket-size') and a "size modifier".

Size modifiers allow ShopTracker to perform automations on product options, such as extracting a price from the product option title and adding it to the price in the feed, and removing price or other extraneous information from the product option title. Size Modifiers use regex for text filtering.

Here's an example 
~~~ 
from shoptracker import *
# -- Feeds --

# Create google feed and export
feed = GoogleFeed(Collection.get_collections())
size_modifiers = {
    # Regex for extracting price from an attribute. These will be added to the product's price
    'price_attribute_extraction_regex' : r"\$(\d+\.\d\d)",

    # Regexes for filtering text out of an attribute
    'attribute_regexes' : [r"(\ \[.*\])"],

    #Run strip() on attribute str
    'strip_attribute' : True,
}
feed.handle_size('jacket-size', size_modifiers)
feed.handle_size('vest-size', size_modifiers)
feed.handle_size('child-sizes', size_modifiers)
~~~

## List of functions (for use in drivers)
### Initialization and importing
#### clear_db()
Wipes the database. Note: does NOT clear bold product option scraping cache, which is stored in the filesystem.
#### import_csv_from_shopify(file) 
Accepts exported shopify csv as input. Used to import a product export csv from shopify.
#### import_collections_from_shopify(files*)
Accepts one or more shopify collection html pages. Used to construct collection data for products.

### BoldOptionScraper
#### Collection.scrape_bold_product_options()
Scrapes bold product options for all options in collection, store the html page in cache, stores options and their associated attributes in the database

### Google Options and related functions 
#### process_colors_for_all_products()
Extracts colors for all products using list of color values defined in googleDefs.py, and inserts them into g_color field in database. Up to 3 colors are inserted into the field, and the rest are discarded.
#### set_default_g_age_group('age_group')
Sets the default age group for all products in database. Restricted to the age_group variable in googleDefs.py
#### set_default_g_gender('gender')
Sets the default gender for all products in database. Restricted to the gender variable in googleDefs.py
#### set_default_g_product_category('gender')
Sets the default g_product_category for all products in database. Restricted to the google_product_category variable in googleDefs.py 
#### Collection.set_g_age_group('age_group')
Collection.Sets the age group for all products in collection. Restricted to the age_group variable in googleDefs.py
#### Collection.set_g_gender('gender')
Collection.Sets the gender for all products in collection. Restricted to the gender variable in googleDefs.py
#### Collection.set_g_product_category('gender')
Collection.Sets the g_product_category for all products in collection. Restricted to the google_product_category variable in googleDefs.py


### Feed options and functions
#### feed = GoogleFeed(Collection.get_collections()) 
Instantiates a feed using all collections in database
#### size_modifier dict
Contains the following:
price_attribute_extraction_regex: regular expression to detect price from attribute title
attribute_regexes: a list of regular expressions that determine what to be filtered out of the attribute title
strip_attribute: True/False determines whether or not attribute title str should be processed with strip method (recommended)
#### Feed.handle_size(size_handle, size_modifier)
Instructs feed generator to handle a size given a size handle and size modifier
#### Feed.exclude_brand('brand_name')
Instructs feed generator to exclude products containing given brand name
#### Feed.exclude_product('product_handle')
Instructs feed generator to exclude product containing given product_handle
#### Feed.set_default_color('color')
Instructs feed generator to set g_color field to given color for products that don't have them.
#### Feed.include_option_names_in_title()
Instructs feed generator to include Product option name at the end of the product title.
#### Feed.build_feed()
Begins building the feed. This operation should be performed after configuration of feed is complete.
#### Feed.export_tsv('feed.tsv')
Exports the feed file.
