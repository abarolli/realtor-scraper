import json
import re
from bs4 import BeautifulSoup as BS

from realtor_dataclasses import (
    RealtorPropertyDetails,
    RealtorPropertyDetailsCommunity,
    RealtorPropertyDetailsConstruction,
    RealtorPropertyDetailsExterior,
    RealtorPropertyDetailsInterior,
)


class RealtorPropertyPage:

    def __init__(self, content: str):
        self.bs = BS(content, 'html.parser')

    
    def get_property_details(self):
        
        details: dict = self.__get_details_from_dom()
        
        interior_details = RealtorPropertyDetailsInterior(
            features=details.get('Interior Features'),
            heating_cooling=details.get('Heating and Cooling')
        )
        
        exterior_details = RealtorPropertyDetailsExterior(
            features=details.get('Home Features'),
            lot_features=details.get('Exterior and Lot Features'),
            pool_spa=details.get('Pool and Spa'),
            garage_parking=details.get('Garage and Parking')
        )

        community_details = RealtorPropertyDetailsCommunity(
            hoa=details.get('Homeowners Association')
        )

        construction_details_str: str = '\n'.join(details.get('Building and Construction'))
        stories_count_pattern: re.Pattern = re.compile(r'Building Total Stories: (\d+)')
        architectural_style_pattern: re.Pattern = re.compile(r'Architectural Style: (.*)')
        stories_match = stories_count_pattern.search(construction_details_str)
        architecture_match = architectural_style_pattern.search(construction_details_str)

        construction_details = RealtorPropertyDetailsConstruction(
            stories=stories_match.group(1) if stories_match else None,
            architectural_style=architecture_match.group(1) if architecture_match else None
        )

        return RealtorPropertyDetails(
            interior_details,
            exterior_details,
            community_details,
            construction_details
        )

    
    def __get_details_from_dom(self) -> dict:
        datasrc = self.bs.find(id='__NEXT_DATA__')
        data = json.loads(datasrc.text)
        return {detail.get('category'): detail.get('text') for detail in data \
                                                            .get('props') \
                                                            .get('pageProps') \
                                                            .get('initialReduxState') \
                                                            .get('propertyDetails') \
                                                            .get('details')}


    def __get_key_facts(self):
        result: dict = {}
        key_facts = self.bs.find(attrs={'data-testid': 'key-facts'})
        listitems = key_facts.find_all('li')
        for li in listitems:
            label: str = li.select_one('.listing-key-fact-item-label').next.text
            value: str = li.select_one('.listing-key-fact-item-value').text
            result.update({label.lower().replace(' ', '_'): value})
        
        return result


    def parse(self):
        key_facts = self.__get_key_facts()
        property_details = self.get_property_details()
        return key_facts, property_details