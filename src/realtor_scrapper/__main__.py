from pprint import pprint
import requests
from bs4 import BeautifulSoup as BS
import json


url = 'https://www.realtor.com/realestateandhomes-search/Scottsdale_AZ/type-single-family-home,townhome/price-250000-500000/hoa-500,known:2'
headers={
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
}
res = requests.get(url, headers=headers)

bs = BS(res.text, "html.parser")
datasrc = bs.find(id='__NEXT_DATA__')
data = json.loads(datasrc.text)
properties = data.get('props').get('pageProps').get('properties')

results: list[dict] = []
for property in properties:
    result = {}
    address = property.get('location').get('address')
    address = {
        'street': address.get('line'),
        'city': address.get('city'),
        'zip': address.get('postal_code'),
        'state': address.get('state_code')
    }
    description = property.get('description')
    result.update({
        'price': property.get('list_price'),
        'address': address,
        'baths': description.get('baths_consolidated'),
        'beds': description.get('beds'),
        'lot_sqft': description.get('lot_sqft'),
        'sqft': description.get('sqft')
    })
    results.append(result)

pprint(results)