import requests
import time
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Annotated, List
import os
import re
from .alpaca_utils import AlpacaUtils


def get_company_name(ticker: str) -> str:
    """
    Get company name from ticker symbol using Alpaca API.
    The fallback logic is handled in AlpacaUtils.
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        Company name or the original ticker if not found
    """

    return AlpacaUtils.get_company_name(ticker)


def get_search_terms(ticker: str) -> List[str]:
    """
    Generate a list of search terms for a company based on ticker symbol
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        List of search terms including company name, ticker, and common variations
    """
    search_terms = [ticker]  # Always include the ticker symbol itself
    
    # Get company name from Alpaca
    company_name = get_company_name(ticker)
    
    if company_name == ticker:
        # If we couldn't get a company name, just return the ticker
        return search_terms
    
    # Handle company names with "Common Stock", "Class A", etc.
    if isinstance(company_name, str):
        # Add the full company name
        search_terms.append(company_name)
        
        # Split by "Common Stock", "Class A", etc.
        name_parts = re.split(r'\s+(?:Common Stock|Class [A-Z]|Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC)', company_name)
        if name_parts and name_parts[0].strip():
            search_terms.append(name_parts[0].strip())
        
        # If company name has OR, split into separate terms
        if " OR " in company_name:
            or_terms = company_name.split(" OR ")
            search_terms.extend([term.strip() for term in or_terms])
    
    return search_terms


def fetch_top_from_category(
    category: Annotated[
        str, "Category to fetch top post from. Collection of subreddits."
    ],
    date: Annotated[str, "Date to fetch top posts from."],
    max_limit: Annotated[int, "Maximum number of posts to fetch."],
    query: Annotated[str, "Optional query to search for in the subreddit."] = None,
    data_path: Annotated[
        str,
        "Path to the data folder. Default is 'reddit_data'.",
    ] = "reddit_data",
):
    base_path = data_path

    all_content = []

    if max_limit < len(os.listdir(os.path.join(base_path, category))):
        raise ValueError(
            "REDDIT FETCHING ERROR: max limit is less than the number of files in the category. Will not be able to fetch any posts"
        )

    limit_per_subreddit = max_limit // len(
        os.listdir(os.path.join(base_path, category))
    )

    for data_file in os.listdir(os.path.join(base_path, category)):
        # check if data_file is a .jsonl file
        if not data_file.endswith(".jsonl"):
            continue

        all_content_curr_subreddit = []

        with open(os.path.join(base_path, category, data_file), "rb") as f:
            for i, line in enumerate(f):
                # skip empty lines
                if not line.strip():
                    continue

                parsed_line = json.loads(line)

                # select only lines that are from the date
                post_date = datetime.utcfromtimestamp(
                    parsed_line["created_utc"]
                ).strftime("%Y-%m-%d")
                if post_date != date:
                    continue

                # if is company_news, check that the title or the content has the company's name (query) mentioned
                if "company" in category and query:
                    # Get search terms including company name and ticker
                    search_terms = get_search_terms(query)

                    found = False
                    for term in search_terms:
                        # Only search if we have a valid term
                        if term and isinstance(term, str):
                            if re.search(
                                re.escape(term), parsed_line["title"], re.IGNORECASE
                            ) or re.search(
                                re.escape(term), parsed_line["selftext"], re.IGNORECASE
                            ):
                                found = True
                                break

                    if not found:
                        continue

                post = {
                    "title": parsed_line["title"],
                    "content": parsed_line["selftext"],
                    "url": parsed_line["url"],
                    "upvotes": parsed_line["ups"],
                    "posted_date": post_date,
                }

                all_content_curr_subreddit.append(post)

        # sort all_content_curr_subreddit by upvote_ratio in descending order
        all_content_curr_subreddit.sort(key=lambda x: x["upvotes"], reverse=True)

        all_content.extend(all_content_curr_subreddit[:limit_per_subreddit])

    return all_content
