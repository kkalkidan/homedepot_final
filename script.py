from email.header import Header
from re import sub
import requests
from bs4 import BeautifulSoup
import json
import re
import pandas as pd
import os
import argparse 

HOMEDEPOT_URL = 'https://www.homedepot.com'
HEADER = 'headers.json'
DEPARMENTS = 'https://www.homedepot.com/hdus/en_US/DTCCOMNEW/fetch/headerFooterFlyout-8.json'
GRAPHQUERY = 'graphqlQuery.json'
SEARCH_MODEL = 'https://www.homedepot.com/federation-gateway/graphql?opname=searchModel'

# opens and reads json files, for reading header and graphql json objects
def getJson(fileName):
    with open(fileName) as jsonFile:
            content = json.load(jsonFile)
    return content


def filterDict(d, key, value):
    existingValues = []
    for item in d:
        existingValues.append(item[key])
        if(item[key] == value):
            return item
    # user didn't provide valid department names 
    print(f'Department {value} does not exist. Available departments are: {existingValues}')

def getDepartmentURL(d1, d2):
    # loads the headers
    headers = getJson(HEADER)
    # get departments 
    html = requests.get(DEPARMENTS, headers=headers)
    # parse response
    departmentsDict = json.loads(html.text)
    # get list of departments
    departments = departmentsDict['header']['primaryNavigation']
    
    # filter departments object by department and subdepartment 
    subDepartment = filterDict(departments, 'title', d1)
    
    # l2, l3: specify the department levels or subdepartment
    for i in range(len(d2)):
        subDepartment = filterDict(subDepartment['l'+str(i+2)], 'name', d2[i])
    
    # return subdepartment's url
    return HOMEDEPOT_URL + subDepartment['url'].replace('SECURE_SUPPORTED', '')+ '?catStyle=ShowProducts'


def getBrandURL(departmentURL, brand):
    # get header before making any request
    headers = getJson(HEADER)
    # make a request to the subdepartment's url
    html = requests.get(departmentURL, headers=headers)

    soup = BeautifulSoup(html.text, 'html.parser')
    # get the url for the brand
    url = soup.find_all(text=brand)[0].parent.parent.get('href')
    # return brand url
    return HOMEDEPOT_URL + url

def amendGraphQuery(storeId, navParam):
    # update the storeId and navParam parameters before posting request to the graphql?opname=searchModel path
    graphqlQuery = getJson(GRAPHQUERY)
    graphqlQuery['variables']['navParam'] = navParam
    graphqlQuery['variables']['storeId'] = storeId
    return graphqlQuery

def scrape(storeIds, d1, d2, brands, prefix):
    
    # for each store Id
    for storeId in storeIds:
        
        fileName= prefix + '_' + storeId
        # get the navigation url for the subdepartment
        departmentURL = getDepartmentURL(d1, d2)
        brandsURL = departmentURL
        
        # get brand url
        # when making subsequent requests from a brandURL it continues to 
        # appends newly selected options/brands (it doesn't remove our previous selection) 
        for b in brands:
            brandsURL = getBrandURL(brandsURL, b)
        
        # get the navigation parameter from the url 
        navParam = re.sub(r'\?.*', '', brandsURL.split('/')[-1])
        
        # update the storeId and navParam in the graphql query
        graphQuery = amendGraphQuery(storeId, navParam)
        pageSize = graphQuery['variables']['pageSize']
        startIndex = 0
        total = pageSize

        
        while(startIndex + pageSize <= total):
            r = requests.post(url=SEARCH_MODEL, json=graphQuery, headers=getJson(HEADER))
            data = json.loads(r.text)['data']['searchModel']
            productsJson = data['products']
            startIndex += pageSize
            graphQuery['variables']['startIndex'] = startIndex
            total = int(data['searchReport']['totalProducts'])
            df = pd.json_normalize(productsJson)
            if not os.path.isfile(fileName):
                df.to_csv(fileName, index=False)
            else:  # else it exists so append without writing the header
                df.to_csv(fileName, mode='a', header=False, index=False)
 
       
    
# scrape('6845', 'Decor & Furniture', ['Bedroom Furniture', 'Mattresses'], ['Zinus', 'Sealy'], "output")
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='scrape HomeDepot.')
    parser.add_argument( '-s_ids', '--store_ids',  type=str, nargs='+',required=True,
                  help='List of store ids')
    parser.add_argument( '-d1', '--department1', help='Department', required=True)
    parser.add_argument('-d2', '--department2',  type=str, nargs='+',required=True,
                  help='List of sub departments')
    parser.add_argument('-b', '--brands',  type=str, nargs='+', required=True,
                help='List of brands')
    parser.add_argument( '-o', '--output', help='Department', default='output.csv')
    args = parser.parse_args()
    brands = args.brands
    storeIds = args.store_ids
    d1 = args.department1
    d2 = args.department2
    output = args.output
    # print(args.brands)
    scrape(storeIds=storeIds, d1=d1, d2=d2, brands=brands, prefix=output)
    

# How to run
# python script.py -s_ids '6177' '0589' -d1 'Decor & Furniture' -d2 'Bedroom Furniture' 'Mattresses' -b 'Sealy' -o 'Sealy_Mattresses'
# python script.py -s_ids '6177' '0589' -d1 'Appliances' -d2 'Refrigerators' -b 'Whirlpool' 'GE' -o 'Whirlpool_GE_Refrigerators'
# python script.py -s_ids '6177' '0589' -d1 'Appliances' -d2 'Dishwashers' -b 'Samsung' 'LG Electronics' 'LG STUDIO' 'LG SIGNATURE' -o 'LG_SamSung_Dishwasher'

