import logging
import os
from application import APP
import db

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    db.connect()
    db.create_tables()   
APP.run(host='0.0.0.0', port=int(os.environ.get('PORT', 9000)))
