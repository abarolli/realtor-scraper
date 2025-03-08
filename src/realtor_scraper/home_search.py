
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import json
import math
from pprint import pprint
import re
import requests
from bs4 import BeautifulSoup as BS

from realtor_dataclasses import (
    RealtorProperty,
    RealtorPropertyDetails,
    RealtorPropertyDetailsCommunity,
    RealtorPropertyDetailsConstruction,
    RealtorPropertyDetailsExterior,
    RealtorPropertyDetailsInterior
)
from scrapers import RealtorPropertyPage


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
    __headers =  {
        'authority': 'www.realtor.com',
        'method': 'GET',
        'path': '/realestateandhomes-search/Scottsdale_AZ',
        'scheme': 'https',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }

    def __init__(self, urlbuilder: RealtorSearchURLBuilder):
        self.__urlbuilder = urlbuilder
        self.__total_results_count = -1
        self.__results = self.__fetch_homes(deep_search=True)


    def has_next_page(self):
        return self.__urlbuilder.current_page < self.__page_count()
    

    def for_each(self, f: callable):
        for result in self.__results:
            f(result)


    def __page_count(self):
        return math.ceil(self.__total_results_count / len(self.__results))


    def next_page(self):
        self.__urlbuilder.next_page()
        self.__results = self.__fetch_homes(deep_search=True)


    def __fetch_homes(self, deep_search: bool = False):
        res = requests.get(self.__urlbuilder.url, headers=self.__headers)
        bs = BS(res.text, "html.parser")

        seo_linking_properties = self.__get_seo_linking_properties(bs)
        main_properties = self.__get_properties_and_set_total_count(bs)
        results: list[RealtorProperty] = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures: list[Future] = []
            for n in range(len(main_properties)):
                property = main_properties[n]
                property_url = seo_linking_properties[n].get('url')
                futures.append(executor.submit(self.__get_home_info, property, property_url, deep_search))
            
            for future in as_completed(futures):
                address, description, key_facts, details = future.result()
                results.append(
                    RealtorProperty(
                        price = property.get('list_price'),
                        url = property_url,
                        address = address,
                        baths = float(description.get('baths_consolidated')) if description.get('baths_consolidated') else None,
                        beds = description.get('beds'),
                        lot_sqft = description.get('lot_sqft'),
                        sqft = description.get('sqft'),
                        sold_date = description.get('sold_date'),
                        sold_price = description.get('sold_price'),
                        key_facts = key_facts,
                        details = details
                    )
                )

        return results


    def __get_home_info(self, property, property_url, deep_search):
        address = property.get('location').get('address')
        address = {
                'street': address.get('line'),
                'city': address.get('city'),
                'zip': address.get('postal_code'),
                'state': address.get('state_code')
            }
        description = property.get('description')
        key_facts, details = self.__fetch_more_details(property_url) if deep_search else (None, None)
        return address, description, key_facts, details


    def __fetch_more_details(self, property_url: str) -> dict:
        res = requests.get(property_url, headers=self.__headers)
        property_page = RealtorPropertyPage(res.text)
        try:
            return property_page.parse()
        except Exception as e:
            raise RuntimeError(f'Failed to parse property page at {property_url}').with_traceback(e.__traceback__)
    
    
    def __get_seo_linking_properties(self, bs: BS):
        '''
        Returns a list of properties similar to `__get_properties_and_set_total_count`, except these are
        the seo linking properties so they don't have a lot of the necessary home info. But they appear
        in the same order as the properties returned from `__get_properties_and_set_total_count` and contain
        the url to the home on realtor.com so it is necessary for deep searches.
        '''
        seo_linking_datasrc = bs.find(attrs={'data-testid': "seoLinkingData"})
        seo_linking_data = json.loads(seo_linking_datasrc.text)[1]
        seo_linking_properties = seo_linking_data.get('mainEntity').get('itemListElement')
        return seo_linking_properties


    def __get_properties_and_set_total_count(self, bs: BS):
        datasrc = bs.find(id='__NEXT_DATA__')
        data = json.loads(datasrc.text)
        self.__total_results_count = data.get('props').get('pageProps').get('totalProperties')
        return data.get('props').get('pageProps').get('properties')


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
        
