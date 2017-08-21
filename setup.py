"""
Sets up the database for use with ShopTracker
"""
import MySQLdb as mysql
import config

def main():
    try:
        con = mysql.connect(config.db_host, config.db_user, config.db_password, config.db_name)
        cur = con.cursor()

        cur.execute("DROP TABLE IF EXISTS `products_collections`;")
        cur.execute("DROP TABLE IF EXISTS `products`; ")
        cur.execute("DROP TABLE IF EXISTS `collections`;")
        cur.execute("""
        CREATE TABLE `products`  (
            `products_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
            `products_handle` varchar(512) NOT NULL DEFAULT '',
            `products_title` varchar(512) NOT NULL DEFAULT '',
            `products_price` decimal(20) NULL DEFAULT '0',
            `products_desc` TEXT NULL,
            `products_vendor` varchar(512) NULL DEFAULT '',
            `products_SKU` varchar(512) NULL DEFAULT '',
            `products_tags` varchar(2096) NULL DEFAULT '',
            `products_url` varchar(512) NULL DEFAULT '',
            `products_img_url` varchar(512) NULL DEFAULT '',
            `products_g_age_group` varchar(1024) NULL DEFAULT '',
            `products_g_color` varchar(1024) NULL DEFAULT '',
            `products_g_product_category` varchar(1024) NULL DEFAULT '',
            PRIMARY KEY (`products_id`)
        );
        """)

        cur.execute("""
        CREATE TABLE `collections`  (
            `collections_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
            `collections_handle` varchar(512) NOT NULL DEFAULT '',
            `collections_title` varchar(512) NOT NULL DEFAULT '',
            PRIMARY KEY (`collections_id`)
        );
        """)

        cur.execute("""
        CREATE TABLE `products_collections`  (
            `products_id` int(10) unsigned NOT NULL,
            `collections_id` int(10) unsigned NOT NULL,
            PRIMARY KEY (`products_id`,`collections_id`),
        FOREIGN KEY (products_id) REFERENCES products (products_id)
          ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (collections_id) REFERENCES collections (collections_id)
          ON UPDATE CASCADE ON DELETE CASCADE
        );
        """)

    except mysql.Error as e:
        print("Error %d: %s" % (e.args[0], e.args[1]))
    finally:
        print("finally")

if __name__ == '__main__':
    main()
