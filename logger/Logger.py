import logging
from logging import handlers
import os

class Logger(object):
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }  # relationship mapping

    def __init__(self, filename, level='debug', when='D', backCount=3,
                 fmt='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'):
        
        print("Class Logger __init__:  __name__: ", __name__)
        print("testing: ", Logger.__module__)

        #parth_act = os.getcwd()  # Ruta actual de trabajo
        #print("path_Act: ", parth_act)
        # change the current directory to specified directory
        #parth_act = os.getcwd()  # Ruta actual de trabajo
        #print("path_Act: ", parth_act)
        
        self.logger = logging.getLogger(filename)
        format_str = logging.Formatter(fmt)  # Setting the log format
        self.logger.setLevel(self.level_relations.get(level))  # Setting the log level
        console_handler = logging.StreamHandler()  # on-screen output
        console_handler .setFormatter(format_str)  # Setting the format
        
        path = os.path.join(os.getcwd(), 'logs', filename)
        th = handlers.TimedRotatingFileHandler(filename=path, when=when, backupCount=backCount,encoding='utf-8')  # automatically generates the file at specified intervals
        th.setFormatter(format_str)  # Setting the format
        self.logger.addHandler(th)  # Add the object to the logger
        self.logger.debug("Logger __init__ iniciado en: %s", __name__)
