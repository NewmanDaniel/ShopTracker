# ShopTracker
## What is it?
ShopTracker is a script that assists in testing your online store. It scrapes your shopify store for data
(including bold product options) and stores it in a local database. 

## dependencies
mysql, phantomJS, beautifulsoup

## setup
Ensure phantomJS is installed on your system, and the mysql and beautifulsoup dependencies are installed via pip.
Configure database details in config.py, then override the beautifulsoup functions in config_soup.py

## usage 
### Import products from a list of shopify collections
python shoptracker.py urls.txt 

### Display products from a shopify collection (useful for testing beautifulsoup overrides)
python shoptracker.py -c http://shopifyurl.com/somecollection

### Display details from a shopify product (useful for testing beautifulsoup overrides)
python shoptracker.py -t http://shopifyurl.com/
