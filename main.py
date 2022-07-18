import argparse
import logging
import sys

import bibtexparser
import requests
import yaml
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import *
from mendeley import Mendeley


def load_bibtex(config_file):
    config = yaml.full_load(config_file)

    logging.info("Performing OAuth authentication")
    mendeley = Mendeley(config['clientId'], redirect_uri="http://localhost:8080/bibtexexport")
    auth = mendeley.start_implicit_grant_flow()
    login_url = auth.get_login_url()
    response = requests.post(login_url, allow_redirects=False, data={
        'username': config["username"],
        'password': config["password"]
    })

    if response.status_code != 302:
        raise Exception("OAuth authentication failed")

    auth_link = response.headers['Location']
    session = auth.authenticate(auth_link)

    logging.info("Downloading bibtex")
    access_token = session.token['access_token']
    headers = {
        "Authorization": "Bearer %s" % access_token,
        "Accept": "application/x-bibtex"
    }
    page = requests.get("https://api.mendeley.com/documents", headers=headers, params={
        "view": "bib",
        "limit": 500
    }, timeout=10)
    if page.status_code != 200:
        raise Exception("Could not fetch first page")
    bibtex_content = page.content

    while "next" in page.links:
        page = requests.get(page.links["next"]["url"], headers=headers)

        if page.status_code != 200:
            raise Exception("Could not fetch later page")

        bibtex_content += page.content

    return bibtex_content.decode("utf-8")


def clean_record(record):
    record = type(record)
    record = page_double_hyphen(record)
    record = convert_to_unicode(record)

    if record["ENTRYTYPE"] in ["inproceedings", "article"]:
        record.pop("url", None)

    return record


parser = argparse.ArgumentParser(description='Mendeley Bibtex dump.')
parser.add_argument('-l', '--loglevel', default='warning',
                    help='Provide logging level. Example --loglevel debug, default=warning')
parser.add_argument('-c', '--config', default="config.yml", type=argparse.FileType('r', encoding='UTF-8'))
args = parser.parse_args()

logging.basicConfig(format='%(levelname)s: %(message)s', level=args.loglevel.upper(), stream=sys.stderr)

bibtex = load_bibtex(args.config)

logging.info("Cleaning bibtex")
parser = BibTexParser(common_strings=False)
parser.homogonise_fields = True

parser.customization = clean_record

bib_database = bibtexparser.loads(bibtex, parser)

bibtex_str = bibtexparser.dumps(bib_database)
print(bibtex_str)
