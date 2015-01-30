import bs4
import urllib.request
import re

# for retry decorator
import time
from functools import wraps

# Shamelessly stolen from http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
# Slightly modified for use with Python 3
def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry

# Every review will have its text contained in a <div class="reviewText">
# The parent of the <div> mentioned above will have as descendants exactly one of each:
#     1. (optional) a div containing a string "X of Y people found the following review helpful"
#     2. <span>X out of 5 stars</span>

HELPFULNESS_REGEX = re.compile(r"(\d+(,\d+)*) of (\d+(,\d+)*) people found the following review helpful")
STAR_REGEX = re.compile(r"(\d\.?\d) out of 5 stars")

@retry(urllib.error.URLError, tries=10, delay=3, backoff=2)
def url_read_with_retry(url):
    return urllib.request.urlopen(url).read()

def get_review_divs(soup):
    review_texts = soup.find_all("div", class_="reviewText")
    return [r_t.parent for r_t in review_texts]

def get_helpfulness_ratings(review):
    navigable_text = review.find(text=HELPFULNESS_REGEX)
    if navigable_text is not None:
        text = str(navigable_text).strip()
        m = HELPFULNESS_REGEX.match(text)
        helpful = int(m.group(1).replace(',',''))
        total = int(m.group(3).replace(',',''))
        return helpful, total
    else:
        return 0, 0

def get_review_stars(review):
    span = review.find("span", text=STAR_REGEX)
    text = str(span.string)
    m = STAR_REGEX.match(text)
    stars = int(float(m.group(1)))
    return stars

def get_next_page(soup):
    span = soup.find("span", class_="paging")
    a = span.find("a", text=re.compile("Next"))
    if a is None:
        return None
    else:
        return a['href']

def get_review_data(first_url, print_status=False):
    url = first_url
    page_num = 0
    review_data = []

    while url is not None and page_num < 10:
        page_num += 1
        data = url_read_with_retry(url)
        soup = bs4.BeautifulSoup(data)
        reviews = get_review_divs(soup)

        if print_status:
            print("-----Page %d: %d reviews-----" % (page_num, len(reviews)))
        
        for r in reviews:
            help_ratings = get_helpfulness_ratings(r)
            stars = get_review_stars(r)
            help_ratings_str = "%d of %d" % help_ratings
            stars_str = "%d stars" % stars
            review_data.append((help_ratings, stars))

            if print_status:
                print(help_ratings_str + ", " + stars_str)

        url = get_next_page(soup)

    return review_data

def write_review_data_to_file(data, fname):
    f = open(fname, 'w')
    for help, stars in review_data:
        good, total = help
        f.write("%d %d %d\n" % (good, total, stars))
    f.close()

def read_review_data_from_file(fname):
    review_data = []
    f = open(fname)
    for line in f:
        good, total, stars = [int(x) for x in line.split()]
        review_data.append((good, total), stars)
    f.close()
    return review_data


affc_first_url = 'http://www.amazon.com/Feast-Crows-Song-Fire-Thrones/product-reviews/055358202X/ref=cm_cr_pr_top_link_1?ie=UTF8&showViewpoints=0&sortBy=byRankDescending'
review_data = get_review_data(affc_first_url, True)
print("Num reviews:", len(review_data))
write_review_data_to_file(review_data, "affc_review_data.txt")
