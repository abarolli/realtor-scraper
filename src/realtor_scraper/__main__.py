from pprint import pprint
import json

from home_search import RealtorProperties
from realtor_dataclasses import RealtorProperty


realtorproperties = RealtorProperties()

results_iterator = realtorproperties.find('Scottsdale_AZ')

results = []
def build_results(home: RealtorProperty):
    results.append(home.to_dict())

results_iterator.for_each(build_results)


# count = 0
# while (results_iterator.has_next_page() and count < 10):
#     results_iterator.for_each(build_results)
#     results_iterator.next_page()

# with open('results.json', 'w', encoding='utf-8') as f:
#     json.dump(results, f)