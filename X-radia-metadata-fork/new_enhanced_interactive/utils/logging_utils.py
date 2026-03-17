import logging
import os
from datetime import datetime

def setup_logger(output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    log_file = os.path.join(
        output_dir,
        'processing_{0}.log'.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    )
    
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    return logging.getLogger(__name__) 