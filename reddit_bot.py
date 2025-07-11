# Importing necessary libraries
from __future__ import print_function
import praw
import prawcore
import time
import os
import logging
import gspread

# Configuring logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Authenticate using your service account credentials
gc = gspread.service_account(filename='path/to/your/auth.json')

# Open the spreadsheet by name or URL
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/MYSHEET")

# Select the specific worksheet (e.g., the first sheet)
configWorksheet = spreadsheet.get_worksheet("Config") # Index 0 for the first sheet
postsWorksheet = spreadsheet.get_worksheet("PostIDs")

# set configs
cell = configWorksheet.find("REDDIT_USERNAME")
REDDIT_USERNAME = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("REDDIT_PASSWORD")
REDDIT_PASSWORD = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("REDDIT_CLIENT_ID")
REDDIT_CLIENT_ID = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("REDDIT_CLIENT_SECRET")
REDDIT_CLIENT_SECRET = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("REDDIT_USER_AGENT")
REDDIT_USER_AGENT = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("TARGET_SUBREDDIT")
TARGET_SUBREDDIT = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("SEARCH_STRING")
SEARCH_STRING = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("REPLY_MESSAGE")
REPLY_MESSAGE = configWorksheet.cell(cell.row,2).value
cell = configWorksheet.find("SLEEP_DURATION")
SLEEP_DURATION = configWorksheet.cell(cell.row,2).value
logger.info("Config set from GSpread...")

# Function to handle rate limit with exponential backoff
def handle_rate_limit(api_exception, retry_attempts=3):
    for attempt in range(retry_attempts):
        retry_after = api_exception.response.headers.get('retry-after')
        if retry_after:
            logger.warning(f"Rate limited. Retrying after {retry_after} seconds. Attempt {attempt + 1}/{retry_attempts}")
            time.sleep(int(retry_after) + 1)
        else:
            logger.error(f"API Exception: {api_exception}")
            break
    else:
        logger.error("Exceeded retry attempts. Aborting.")
        raise

# Function to log in to Reddit
def bot_login():
    logger.info("Logging in...")
    
    try:
        reddit_instance = praw.Reddit(
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        logger.info("Logged in!")
        return reddit_instance
    except prawcore.exceptions.ResponseException as e:
        logger.error(f"Login failed: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during login: {e}")
        raise

# Function to run the bot
def run_bot(reddit_instance, comments_replied_to):
    logger.info(f"Searching today's posts in subreddit {TARGET_SUBREDDIT}")

    try:
        eBikes = reddit_instance.subreddit(TARGET_SUBREDDIT)
        process_posts(eBikes, comments_replied_to)
    except praw.exceptions.APIException as api_exception:
        # Handle rate limits
        handle_rate_limit(api_exception)
    except Exception as e:
        # Log other exceptions
        logger.exception(f"An error occurred: {e}")

    logger.info(f"Sleeping for {SLEEP_DURATION} seconds...")
    time.sleep(int(SLEEP_DURATION))

# Function to process posts for today
def process_posts(subreddit_instance, posts_replied_to):
    
    for post in subreddit_instance.search(SEARCH_STRING,"new","lucene","day"):
        try:
            process_single_post(post, comments_replied_to)
        except prawcore.exceptions.Forbidden as forbidden_error:
            logger.warning(f"Permission error for comment {comment.id}: {forbidden_error}. Skipping.")
        except Exception as error:
            logger.exception(f"Error processing comment {comment.id}: {error}")

    # Log when the search is completed
    logger.info("Search Completed.")
    # Log the count of comments replied to
    logger.info(f"Number of posts replied to: {len(posts_replied_to)}")

# Function to process a single comment
def process_single_post(post, posts_replied_to):
    # Verify we haven't commented on this post already
    if (post.id not in posts_replied_to
        and post.author != reddit_instance.user.me()
    ):
        # Log when the target string is found in a comment
        logger.info(f"Found post {post.id}.")
        # Reply to the comment with the predefined message
        try:
            #Build reply message
            #post.reply(REPLY_MESSAGE)
            # Log that the bot has replied to the comment
            logger.info(f"Replied to comment {comment.id}")
            # Add the comment ID to the list of comments replied to
            posts_replied_to.append(comment.id)
            # Save the comment ID to the file
            postsWorksheet.append_row([comment.id])        
        except prawcore.exceptions.Forbidden as forbidden_error:
            logger.warning(f"Permission error for comment {comment.id}: {forbidden_error}. Skipping.")
        except Exception as reply_error:
            logger.exception(f"Error while replying to comment {comment.id}: {reply_error}")
     else:
         logger.info(f"Post {post.id} already replied to.")

# Main block to execute the bot
if __name__ == "__main__":
    # Log in to Reddit
    reddit_instance = bot_login()
    # Get the list of comments the bot has replied to from the file
    posts_replied_to = [item for item in postsWorksheet.col_values(1) if item]
    # Log the number of comments replied to
    logger.info(f"Number of posts replied to: {len(posts_replied_to)}")

    # Run the bot in an infinite loop
    while True:
        try:
            # Attempt to run the bot
            run_bot(reddit_instance, posts_replied_to)
        except Exception as e:
            # Log any general exceptions and sleep for the specified duration
            logger.exception(f"An error occurred: {e}")
            time.sleep(int(SLEEP_DURATION))  # Add a sleep after catching general exceptions
        except KeyboardInterrupt:
            logger.info("Bot terminated by user.")
            break
