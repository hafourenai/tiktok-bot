# -*- coding: utf-8 -*-
import time
import logging
from datetime import datetime
from generate_menu import main as generate_menu, fetch_csv_data, filter_menu_items
from config import POLLING_INTERVAL

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def start_polling():
    """Start polling untuk check perubahan stok"""
    logger.info("="*50)
    logger.info("[*] Stok Change Polling Service Started")
    logger.info(f"Polling interval: {POLLING_INTERVAL} seconds ({POLLING_INTERVAL//60} minutes)")
    logger.info("="*50)
    
    poll_count = 0
    
    try:
        while True:
            poll_count += 1
            current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            
            logger.info(f"\n[Poll #{poll_count}] {current_time}")
            logger.info("Checking for stok changes...")
            
            try:
                # Fetch dan filter data
                df = fetch_csv_data()
                if df is not None:
                    filtered_df = filter_menu_items(df)
                    
                    # Generate menu akan otomatis check apakah ada perubahan
                    # dan hanya regen jika ada perubahan
                    generate_menu()
                else:
                    logger.warning("[!] Failed to fetch data")
            
            except Exception as e:
                logger.error(f"[ERROR] Error during polling: {e}")
            
            # Wait untuk interval berikutnya
            logger.info(f"Next poll in {POLLING_INTERVAL} seconds...")
            time.sleep(POLLING_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("\n" + "="*50)
        logger.info("[*] Polling service stopped by user")
        logger.info("="*50)
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}")
        raise

if __name__ == "__main__":
    start_polling()
