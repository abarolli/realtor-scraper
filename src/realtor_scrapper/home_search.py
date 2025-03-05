
from dataclasses import dataclass
import json
import math
import re
from dataclasses_json import dataclass_json
import requests
from bs4 import BeautifulSoup as BS

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

@dataclass_json
@dataclass
class RealtorProperty:
    price: int
    address: dict[str, str]
    baths: float = None
    beds: float = None
    lot_sqft: int = None
    sqft: int = None
    sold_date: str = None
    sold_price: int = None


class RealtorSearchResultsIterator:
    __headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    }

    def __init__(self, urlbuilder: RealtorSearchURLBuilder):
        self.__urlbuilder = urlbuilder
        self.__total_results_count = -1
        self.__results = self.__fetch_homes()

    def has_next_page(self):
        return self.__urlbuilder.current_page < self.__page_count()
    
    def for_each(self, f: callable):
        for result in self.__results:
            f(result)

    def __page_count(self):
        return math.ceil(self.__total_results_count / len(self.__results))

    def next_page(self):
        self.__urlbuilder.next_page()
        self.__results = self.__fetch_homes()

    def __fetch_homes(self):
        res = requests.get(self.__urlbuilder.url, headers=self.__headers)
        bs = BS(res.text, "html.parser")

        datasrc = bs.find(id='__NEXT_DATA__')
        data = json.loads(datasrc.text)

        properties = data.get('props').get('pageProps').get('properties')
        self.__total_results_count = data.get('props').get('pageProps').get('totalProperties')
        results: list[RealtorProperty] = []
        for property in properties:
            description = property.get('description')
            address = property.get('location').get('address')
            address = {
                'street': address.get('line'),
                'city': address.get('city'),
                'zip': address.get('postal_code'),
                'state': address.get('state_code')
            }
            results.append(
                RealtorProperty(
                    price = property.get('list_price'),
                    address = address,
                    baths = float(description.get('baths_consolidated')) if description.get('baths_consolidated') else None,
                    beds = description.get('beds'),
                    lot_sqft = description.get('lot_sqft'),
                    sqft = description.get('sqft'),
                    sold_date = description.get('sold_date'),
                    sold_price = description.get('sold_price')
                )
            )

        return results

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
        
