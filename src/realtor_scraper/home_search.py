
import math
from pprint import pprint
import re
import requests

from scrapers import Scraper, RealtorSearchResultsPage
from constants import HEADERS


class RealtorSearchURLBuilder:
    __base_url: str = 'https://www.realtor.com/realestateandhomes-search'
    __page_pattern = re.compile(r'/pg-(\d+)/?$')

    def __init__(self):
        self.__final_url: str = self.__base_url
        self.__is_location_added: bool = False

    def location(self, location: str):
        if self.__is_location_added:
            raise RuntimeError('Can only call location once for each lookup.')

        self.__final_url += f'/{location}'
        self.__is_location_added = True
        return self
    
    def __validate_loc_added(self):
        if not self.__is_location_added:
            raise RuntimeError('location must be called before any other methods')
    
    def price_range(self, min: int = 0, max: int = 0):
        self.__validate_loc_added()
        self.__final_url += f'/price-{min or "na"}{f"-{max}" if max else ""}'
        return self
    
    def property_types(self, *property_types):
        self.__validate_loc_added()
        self.__final_url += f'/type-{"-".join(property_types)}'
        return self

    def beds(self, min: int = 0, max: int = 0):
        self.__validate_loc_added()
        self.__final_url += f'/beds-{min or "na"}{f"-{max}" if max else ""}'
        return self
    
    def baths(self, min: int = 0, max: int = 0):
        self.__validate_loc_added()
        self.__final_url += f'/baths-{min or "na"}{f"-{max}" if max else ""}'
        return self
    
    def listing_status(self, status: str):
        self.__validate_loc_added()
        self.__final_url += f'/show-{status}'
        return self
    
    def next_page(self):
        match = self.__page_pattern.search(self.__final_url)
        if match:
            next_page = int(match.group(1)) + 1
            self.__final_url = self.__page_pattern.sub(f'/pg-{next_page}', self.__final_url)
        else:
            self.__final_url += '/pg-2'

    @property
    def current_page(self):
        match = self.__page_pattern.search(self.__final_url)
        return int(match.group(1)) if match else 1
            
    @property
    def url(self):
        return self.__final_url


class RealtorSearchResultsIterator:
    __headers = HEADERS

    def __init__(self, urlbuilder: RealtorSearchURLBuilder):
        self.__urlbuilder = urlbuilder
        self.__update_results()


    def has_next_page(self):
        return self.__urlbuilder.current_page < self.__page_count()
    

    def for_each(self, f: callable):
        for result in self.__results:
            f(result)


    def __page_count(self):
        return math.ceil(self.__total_results_count / len(self.__results))


    def next_page(self):
        self.__urlbuilder.next_page()
        self.__update_results()


    def __update_results(self):
        page_results, total_results_count = self.__fetch_homes(scraper=RealtorSearchResultsPage())
        self.__results = page_results
        self.__total_results_count = total_results_count


    def __fetch_homes(self, scraper: Scraper):
        res = requests.get(self.__urlbuilder.url, headers=self.__headers)
        return scraper.scrape(res.text)


class RealtorProperties:

    def find(
        self,
        location: str,
        price_range: tuple[int, int] = None,
        property_types: tuple[str] = None,
        beds: tuple[int, int] = None,
        baths: tuple[int, int] = None,
        listing_status: str = None
    ) -> RealtorSearchResultsIterator:
        urlbuilder = RealtorSearchURLBuilder().location(location)
        if price_range:
            urlbuilder.price_range(*price_range)
        if property_types:
            urlbuilder.property_types(*property_types)
        if beds:
            urlbuilder.beds(beds[0], beds[1])
        if baths:
            urlbuilder.baths(baths[0], baths[1])
        if listing_status:
            urlbuilder.listing_status(listing_status)

        return RealtorSearchResultsIterator(urlbuilder)
        
