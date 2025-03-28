from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import json
import re
from typing import TypeAlias
from bs4 import BeautifulSoup as BS
import requests

import realtor_dataclasses as _rdc
from constants import HEADERS

class Scraper(ABC):
    @abstractmethod
    def scrape(self, content: str) -> any:
        ...


class RealtorPropertyPage(Scraper):

    __HomeFeatures: TypeAlias = dict[str, list[str]]


    def scrape(self, content: str):
        return self.__get_property_details(BS(content, 'html.parser'))
    

    def __get_property_details(self, bs: BS):
        
        details: RealtorPropertyPage.__HomeFeatures = self.__get_details_from_dom(bs)
        
        return _rdc.RealtorPropertyDetails(
            self.__get_interior_details(details),
            self.__get_exterior_details(details),
            self.__get_community_details(details),
            self.__get_construction_details(details)
        )


    def __get_construction_details(self, details: __HomeFeatures):
        construction_details_str: str = '\n'.join(details.get('Building and Construction', []))
        stories_count_pattern: re.Pattern = re.compile(r'Building Total Stories: (\d+)')
        architectural_style_pattern: re.Pattern = re.compile(r'Architectural Style: (.*)')
        stories_match = stories_count_pattern.search(construction_details_str)
        architecture_match = architectural_style_pattern.search(construction_details_str)

        return _rdc.RealtorPropertyDetailsConstruction(
            stories=stories_match.group(1) if stories_match else None,
            architectural_style=architecture_match.group(1) if architecture_match else None
        )


    def __get_community_details(self, details: __HomeFeatures):
        return _rdc.RealtorPropertyDetailsCommunity(
            hoa=details.get('Homeowners Association')
        )
        

    def __get_exterior_details(self, details: __HomeFeatures):
        return _rdc.RealtorPropertyDetailsExterior(
            features=details.get('Home Features'),
            lot_features=details.get('Exterior and Lot Features'),
            pool_spa=details.get('Pool and Spa'),
            garage_parking=details.get('Garage and Parking')
        )


    def __get_interior_details(self, details: __HomeFeatures):
        return _rdc.RealtorPropertyDetailsInterior(
            features=details.get('Interior Features'),
            heating_cooling=details.get('Heating and Cooling')
        )

    
    def __get_details_from_dom(self, bs: BS) -> __HomeFeatures:
        datasrc = bs.find(id='__NEXT_DATA__')
        data = json.loads(datasrc.text)
        return {detail.get('category'): detail.get('text') for detail in data \
                                                            .get('props') \
                                                            .get('pageProps') \
                                                            .get('initialReduxState') \
                                                            .get('propertyDetails') \
                                                            .get('details')}


class RealtorSearchResultsPage(Scraper):

    __headers =  HEADERS


    def scrape(self, content: str):
        return self.__get_details(
            BS(content, 'html.parser'),
            deep_scraper=RealtorPropertyPage()
        )


    def __get_details(self, bs: BS, deep_scraper: Scraper | None = None) -> list[_rdc.RealtorProperty]:
        seo_linking_properties = self.__get_seo_linking_properties(bs)
        main_properties, total_results_count = self.__get_properties_and_total_count(bs)
        results: list[_rdc.RealtorProperty] = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures: list[Future] = []
            for n in range(len(main_properties)):
                property = main_properties[n]
                property_url = seo_linking_properties[n].get('url')
                futures.append(executor.submit(self.__get_home_info, property, property_url, deep_scraper))
            
            for future in as_completed(futures):
                address, description, details = future.result()
                results.append(
                    _rdc.RealtorProperty(
                        price = property.get('list_price'),
                        url = property_url,
                        address = address,
                        baths = float(description.get('baths_consolidated')) if description.get('baths_consolidated') else None,
                        beds = description.get('beds'),
                        lot_sqft = description.get('lot_sqft'),
                        sqft = description.get('sqft'),
                        sold_date = description.get('sold_date'),
                        sold_price = description.get('sold_price'),
                        details = details
                    )
                )

        return results, total_results_count


    def __get_home_info(self, property, property_url: str, deep_scraper: Scraper | None = None):
        address = property.get('location').get('address')
        address = {
                'street': address.get('line'),
                'city': address.get('city'),
                'zip': address.get('postal_code'),
                'state': address.get('state_code')
            }
        description = property.get('description')
        details = self.__fetch_more_details(property_url, deep_scraper) if deep_scraper else None
        return address, description, details


    def __fetch_more_details(self, property_url: str, deep_scraper: Scraper) -> any:
        res = requests.get(property_url, headers=self.__headers)
        try:
            return deep_scraper.scrape(res.text)
        except Exception as e:
            raise RuntimeError(f'Failed to scrape property page at {property_url}').with_traceback(e.__traceback__)
    
    
    def __get_seo_linking_properties(self, bs: BS):
        '''
        Returns a list of properties similar to `__get_properties_and_total_count`, except these are
        the seo linking properties so they don't have a lot of the necessary home info. But they appear
        in the same order as the properties returned from `__get_properties_and_total_count` and contain
        the url to the home on realtor.com so it is necessary for deep searches.
        '''
        seo_linking_datasrc = bs.find(attrs={'data-testid': "seoLinkingData"})
        seo_linking_data = json.loads(seo_linking_datasrc.text)[1]
        seo_linking_properties = seo_linking_data.get('mainEntity').get('itemListElement')
        return seo_linking_properties


    def __get_properties_and_total_count(self, bs: BS):
        datasrc = bs.find(id='__NEXT_DATA__')
        data = json.loads(datasrc.text)
        total_results_count = data.get('props').get('pageProps').get('totalProperties')
        return data.get('props').get('pageProps').get('properties'), total_results_count