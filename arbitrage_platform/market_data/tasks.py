# arbitrage_platform/market_data/tasks.py
from celery import shared_task
from .models import TrackedExchangePair
from .exchange_interface import (
    update_all_exchange_pairs as update_all_exchange_pairs_util, # Renamed to avoid clash
    get_binance_pair_volume_and_price,
    get_bybit_pair_volume_and_price
)
from django.utils import timezone # Correct import for timezone
import time
import decimal # Ensure decimal is imported for any direct Decimal usage if needed.
import logging

logger = logging.getLogger(__name__)

@shared_task(name="market_data.tasks.update_all_pairs_from_exchanges_task")
def update_all_pairs_from_exchanges_task():
    """Celery task to update all tracked exchange pairs from exchange APIs."""
    logger.info("Task: Updating all exchange pairs...")
    update_all_exchange_pairs_util() # Calls the function from exchange_interface.py
    logger.info("Task: Finished updating all exchange pairs.")
    return "All exchange pairs discovery process completed."

@shared_task(name="market_data.tasks.update_single_pair_volume_task")
def update_single_pair_volume_task(tracked_pair_id):
    """
    Celery task to fetch and update 24h volume and last price for a single TrackedExchangePair
    and save it to the database.
    """
    try:
        pair = TrackedExchangePair.objects.get(id=tracked_pair_id)
        logger.info(f"Task: Updating volume for {pair.exchange_name} - {pair.symbol} (ID: {tracked_pair_id})")

        success = False
        if pair.exchange_name == 'Binance':
            success = get_binance_pair_volume_and_price(pair) # This function updates pair instance from cache/API
        elif pair.exchange_name == 'Bybit':
            success = get_bybit_pair_volume_and_price(pair)
        # Add other exchanges here if they have specific volume functions
        # else:
        #     logger.warning(f"Task Warning: No specific volume fetch function for {pair.exchange_name} on pair {pair.symbol}")

        if success and pair.last_volume_update: # Check if data was actually fetched/updated in the instance
            # Now save the updated data (volume, price, last_volume_update) from the instance to DB
            pair.save(update_fields=['last_price', 'volume_24h_base', 'volume_24h_quote', 'last_volume_update'])
            logger.info(f"Task: Successfully updated and saved volume for {pair.symbol} (ID: {tracked_pair_id})")
            return f"Volume updated for {pair.symbol} (ID: {tracked_pair_id})"
        else:
            logger.warning(f"Task: Failed to fetch volume data or no update for {pair.symbol} (ID: {tracked_pair_id}) via exchange_interface")
            return f"Failed to update volume for {pair.symbol} (ID: {tracked_pair_id}) via exchange_interface"

    except TrackedExchangePair.DoesNotExist:
        logger.error(f"Task Error: TrackedExchangePair with ID {tracked_pair_id} not found.")
        return f"Pair ID {tracked_pair_id} not found."
    except Exception as e:
        logger.error(f"Task Error: Updating volume for pair ID {tracked_pair_id}: {e}", exc_info=True)
        # Consider re-queueing or specific error handling based on exception type
        return f"Error updating volume for pair ID {tracked_pair_id}: {e}"


@shared_task(name="market_data.tasks.schedule_all_active_pair_volume_updates_task")
def schedule_all_active_pair_volume_updates_task():
    """
    Celery task (intended to be run by Celery Beat) to queue individual
    volume update tasks for all active pairs.
    Includes staggering.
    """
    active_pairs = TrackedExchangePair.objects.filter(is_active_for_scan=True)
    logger.info(f"Task: Scheduling volume updates for {active_pairs.count()} active pairs.")

    # Basic staggering: delay between queuing each task.
    stagger_delay_seconds = 1 # Delay 1 second between queuing each task to spread load

    for pair in active_pairs:
        update_single_pair_volume_task.delay(pair.id)
        # logger.debug(f"Queued volume update for {pair.symbol} (ID: {pair.id})")
        time.sleep(stagger_delay_seconds) # Simple stagger

    logger.info(f"Task: Finished scheduling volume updates for active pairs.")
    return f"Scheduled volume updates for {active_pairs.count()} pairs."
