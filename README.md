# ShopTracker
## What is it?
ShopTracker is a script that assists in testing your online store. It scrapes your shopify store for product data
(including bold product options) and stores it in a local mysql database. 

## dependencies
mysql, phantomJS, beautifulsoup

## setup
Ensure phantomJS is installed on your system, and the mysql and beautifulsoup dependencies are installed via pip.

It's recommended to use a virtual environment to install these dependencies:

`
virtualenv -p python3 venv

pip install mysqlclient

pip install beautifulsoup4
`

PhantomJS can be found here: http://phantomjs.org/ or installed with your package manager of choice

Configure database details in config.py, then override the beautifulsoup functions in config_soup.py

## usage 
### Import products from a list of shopify collections
python shoptracker.py urls.txt 

### Display products from a shopify collection (useful for testing beautifulsoup overrides)
python shoptracker.py -c http://shopifyurl.com/somecollection

### Display details from a shopify product (useful for testing beautifulsoup overrides)
python shoptracker.py -t http://shopifyurl.com/
