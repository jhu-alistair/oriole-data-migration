#!/usr/bin/env python3

# This script load the xml exported from MySQL and fast terms
# data from the Access database and load them into oriole
# via the REST interface.

# Usage:
# In the /data directory, run
# ../scripts/load.py

import xml.etree.ElementTree as ET
import requests
import json
import uuid
import csv
import settings

# Parse XML
tree = ET.parse('data/data.xml')
root = tree.getroot()

# Read DB data
db_map = {}
total_in_file = 0

for child in root:
    id = str(uuid.uuid4())
    jhu_id_elem = child.find('metalib_id')
    jhu_id = jhu_id_elem.text if jhu_id_elem is not None else ''

    title_elem = child.find('title_display')
    if title_elem is None:
        title_elem = child.find('title_full')
    title = title_elem.text if title_elem is not None else ''

    url_elem = child.find('link_native_home')
    url = url_elem.text if url_elem is not None else ''

    description_elem = child.find('description')
    description = description_elem.text if description_elem is not None else ''

    publisher_elem = child.find('publisher')
    publisher = publisher_elem.text if publisher_elem is not None else ''

    creator_elem = child.find('creator')
    creator = creator_elem.text if creator_elem is not None else ''

    coverage_elem = child.find('coverage')
    coverage = coverage_elem.text if coverage_elem is not None else ''

    search_hints_elem = child.find('search_hints')
    search_hints = search_hints_elem.text if search_hints_elem is not None else ''

    alt_title_elems = child.findall('title_alternate')
    alt_titles = []
    if alt_title_elems is not None:
        for alt_title_elem in alt_title_elems:
            alt_titles.append(alt_title_elem.text)
    payload = {}

    if title == '' and url == '':
        print(f'ID {jhu_id}: no title and url.')
    else:
        payload = {
            'id': id,
            'title': title,
            'url': url,
            'description': description,
            'altId': jhu_id,
            'terms': [],
            'publisher': publisher,
            'creator': creator,
            'tags': { 'tagList': [] },
            'coverage': coverage,
            'searchHints': search_hints,
            'altTitles': alt_titles
        }
        db_map[jhu_id] = payload
    total_in_file += 1

# Read fast terms
csv.register_dialect('comma', delimiter=',', quoting=csv.QUOTE_ALL)
terms_map = {}
with open('data/fast_terms.txt', 'r') as terms_file:
    for row in csv.DictReader(terms_file, dialect='comma', fieldnames=['id', 'term', 'facet', 'uri']):
        id = str(uuid.uuid4())
        fast_id = row['id']
        payload = {'id': id, 'fastId': fast_id, 'term': row['term'], 'uri': row['uri'], 'facet': row['facet']}
        terms_map[fast_id] = payload

# Read access id to metalib id mapping
csv.register_dialect('piper', delimiter='|', quoting=csv.QUOTE_ALL)
id_map = {}  # access db ID to metalib id map
with open('data/oriole_dbs.txt', 'r', encoding='latin-1') as csvfile:
    for row in csv.DictReader(csvfile, dialect='comma', fieldnames=['id', 'metalib_id', 'title', 'description', 'note']):
            id_map[int(row['id'])] = row['metalib_id']

term_cores = {} # term-core_db
db_terms = {}  # database (metalib_id) - list of terms (fast_id)

# build database to terms mapping and add terms to databases
with open('data/oriole_map_db_to_terms.txt', 'r', encoding='latin-1') as csvfile:
    for row in csv.DictReader(csvfile, fieldnames=['db', 'fastid', 'core']):
        metalib_id = id_map[int(row['db'])]  #Gets the JHUID
        fast_id = row['fastid']
        # add term to database
        subject = {'subject': terms_map[fast_id]}
        # subject['category'] = 'core' if row['core'] == '1' else 'none'
        subject['score'] = 1
        if metalib_id in db_map:
            db_map[metalib_id]['terms'].append(subject)
        else:
            print(f'metalib_id in fast term mapping not found: {row["db"]}, {metalib_id}')

# Read tags
terms_map = {}
with open('data/xerxes_tags.csv', 'r') as tags_file:
    for row in csv.DictReader(tags_file, dialect='comma'):
        metalib_id = row['database_id']
        if metalib_id in db_map:
            db_map[metalib_id]['tags']['tagList'].append(row['catname'] + ' -- ' + row['subname'])

headers={'x-okapi-tenant': settings.ORIOLE_API_TENANT, 'content-type': 'application/json'}
if settings.OKAPI_ENABLED:
    payload = {'username': settings.ORIOLE_API_USERNAME, 'password': settings.ORIOLE_API_PASSWORD}
    response = requests.post(f'{settings.ORIOLE_API_ROOT}/authn/login', data=json.dumps(payload), headers=headers, verify=False)
    headers['x-okapi-token'] = response.headers['x-okapi-token'] # 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkaWt1X2FkbWluIiwidXNlcl9pZCI6IjI2OWM4MzU5LTliMTYtNDRlYi05Y2VmLWFjYzkxNTYxOTk2NCIsImNhY2hlX2tleSI6ImMwZmNmOTE3LTU4MGQtNDg2Mi04ODJhLWU4YTE2ZmVlNjVhNyIsImlhdCI6MTU1NjE1NjQ1MiwidGVuYW50IjoiZGlrdSJ9.jSvPFcoj-TZhZEd_Yxl0JETOjfhZPrEx5cTQAOToFAE' #

api_url = f'{settings.ORIOLE_API_ROOT}/oriole-subjects'
for fast_id, payload in terms_map.items():
    response = requests.post(api_url, headers=headers, data=json.dumps(payload), verify=False)
    if response.status_code != 201:
        print(response.status_code, response.text)

api_url = f'{settings.ORIOLE_API_ROOT}/oriole/resources'
for metalib_id, payload in db_map.items():
    response = requests.post(api_url, headers=headers, data=json.dumps(payload), verify=False)
    if response.status_code != 201:
        print(response.status_code, response.text)
        print(payload)
