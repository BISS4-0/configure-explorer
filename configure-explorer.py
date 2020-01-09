import ast
import json
import os
import re
import shutil
import sys

import barely_json
import docker

CONTENT = {}

CURRENT_DIR = os.getcwd()

REGTAGLEADING = '\'\&'
REGTAGTAILING = '\&\''

REGTAG = '\&'

TAGS_REQUIRING_QUOTES = ["NAME", "MSPID", "PEER_URL", "PEER_NAME", "CA_NAME", "URL", "CERT"]

CHECKREGEX = '\&.*\&'

CA_REDUCED_TEMPLATE = 'ca_reduced.json'
NETWORK_TEMPLATE = 'network_profile.json'
ORG_REDUCED_TEMPLATE = 'org_reduced.json'
PEER_REDUCED_TEMPLATE = 'peer_reduced.json'

TEMPLATE_DIR = '/templates/'
BASE_CONFIG_DIR = '/configuration/'
FABRIC_CONFIG_DIR = 'fabric/'
EXPLORER_CONFIG_BASE_DIR = 'explorer/'
EXPLORER_CONFIG_PROFILE_DIR = 'connection-profile/'
EXPLORER_CRYPTO_DIR = 'crypto/'

EXPLORER_CONFIG_FILE = 'config.json'
EXPLORER_NETWORK_FILE = 'first-network.json'

"""
Creates the following structure:

configure-explorer/
├── configuration                   <- Configuration files for explorer and fabric
│   ├── explorer
│   │   ├── config.json
│   │   ├── connection-profile
│   │   │   └── first-network.json
│   │   └── crypto
│   └── fabric                      <-  Connection profile of each org of fabric
│       ├── connection-org1.json
│       └── connection-org2.json
├── configure-explorer.py
├── first-network.json              <- Connection profile for explorer, created by configure-explorer.py
├── templates                       <- Templates
│   ├── ca_reduced.json
│   ├── config.json
│   ├── first-network.json
│   ├── network_profile.json
│   ├── org_reduced.json
│   └── peer_reduced.json

"""


def _ensure_path(path):
    if not os.path.exists(path):
        print('%s does not exist, creating' % path)
        os.makedirs(path)
    else:
        print('%s exists, skipping' % path)


def _move_files(file, source_path, target_path):
    if not _check_file_exists(target_path + file):
        print('Copy %s to %s' % (file, target_path))
        shutil.copyfile(source_path + file, target_path + file)
    else:
        print('%s exists, skipping' % (target_path + file))


def _open_file(filename):
    return open(CURRENT_DIR + TEMPLATE_DIR + filename, "r").read()


def _read_json(path):
    with open(path) as json_file:
        return json.load(json_file, strict=False)


def _read_invalid_json(path):
    return barely_json.parse(_open_file(path))


def _write_file(content, filename):
    print("Fixing json")
    # Remove empty }: '' thing
    content = content.replace("}: ''", "")
    # Change ' to "
    content = content.replace("\'", "\"")
    # Change True to true
    content = content.replace("True", "true")
    # Change False to false
    content = content.replace("False", "false")

    content_as_json = json.loads(content)

    print("Writing json to %s" % (os.getcwd() + "/" + filename + ".json"))
    with open(os.getcwd() + "/" + filename + ".json", 'w+') as jsonfile:
        json.dump(content_as_json, jsonfile, indent=4)


def _create_orderers(orderer_containers):
    orderers = []

    for container in orderer_containers:
        if 'orderer' in container.attrs['Name']:
            print("Creating Orderer: %s" % container.attrs['Name'].strip('/'))
            orderers.append(container.attrs['Name'].strip('/'))

    CONTENT['ORDERER_URLS'] = orderers


def _create_org(connection_profile):
    template = _read_invalid_json(ORG_REDUCED_TEMPLATE)

    dictoforgs = dict()
    dictorgs = dict()
    listoforgurls = list()

    for org in connection_profile:
        print("Creating Org: %s" % org['client']['organization'])

        listoforgurls.append(org['client']['organization'])

        dictoforgs['NAME'] = org['client']['organization']
        dictoforgs['MSPID'] = org['organizations'][org['client']['organization']]['mspid']
        dictoforgs['PEER_URLS'] = org['organizations'][org['client']['organization']]['peers']
        dictoforgs['CA_URLS'] = org['organizations'][org['client']['organization']]['certificateAuthorities']

        content = {org['client']['organization']: ast.literal_eval(_replace_content(dictoforgs, template))}
        dictorgs.update(content)

    CONTENT['LIST_ORG'] = listoforgurls
    CONTENT['ORGS'] = dictorgs


def _build_peers(connection_profile, peer_containers):
    template = _read_invalid_json(PEER_REDUCED_TEMPLATE)

    peers = dict()
    dictpeers = dict()
    dictofpeercerts = dict()

    for org in connection_profile:
        arrayofpeers = []
        for peer in org['peers']:
            print("Creating Org: %s - Peer: %s" % (org['client']['organization'], peer))

            content = {peer: {}}
            peers.update(content)
            arrayofpeers.append(peer)
        for element in arrayofpeers:
            dictofpeers = dict()
            dictofpeers['PEER_NAME'] = element
            dictofpeercerts['CERT'] = org['peers'][element]['tlsCACerts']['pem']
            for container in peer_containers:
                if element == container.attrs['Name'].strip('/'):
                    for i in range(0, len(container.attrs['NetworkSettings']['Ports'])):
                        if container.attrs['NetworkSettings']['Ports'][
                            list(container.attrs['NetworkSettings']['Ports'])[i]] is not None:
                            url = "grpcs://" + container.attrs['NetworkSettings']['Networks'][
                                list(container.attrs['NetworkSettings']['Networks'])[0]]['IPAddress'] + ":" + \
                                  container.attrs['NetworkSettings']['Ports'][
                                      list(container.attrs['NetworkSettings']['Ports'])[i]][0]['HostPort']
                            dictofpeers['URL'] = url

                            content = {element: ast.literal_eval(_replace_content(dictofpeers, template))}
                            dictpeers.update(content)

                            cert = {'pem': dictpeers[element]['tlsCACerts']['pem'].replace("&CERT&", repr(
                                dictofpeercerts['CERT'])[1:-1])}
                            dictpeers[element]['tlsCACerts'].update(cert)

    CONTENT['PEER_URLS'] = peers
    CONTENT['PEERS'] = dictpeers


def _create_ca(connection_profile, ca_containers):
    template = _read_invalid_json(CA_REDUCED_TEMPLATE)

    dictofcas = dict()
    dictca = dict()
    dictofcert = dict()
    listofcaurls = list()

    for ca in connection_profile:
        print("Creating: %s" % ca['certificateAuthorities'][
            ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]]['caName'])

        listofcaurls.append(ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0])

        dictofcas['CA_NAME'] = ca['certificateAuthorities'][
            ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]]['caName']
        dictofcert['CERT'] = ca['certificateAuthorities'][
            ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]]['tlsCACerts']['pem']

        for container in ca_containers:
            if ca['client']['organization'] in container.attrs['Name']:
                for i in range(0, len(container.attrs['NetworkSettings']['Ports'])):
                    if container.attrs['NetworkSettings']['Ports'][
                        list(container.attrs['NetworkSettings']['Ports'])[i]] is not None:
                        url = "https://" + container.attrs['NetworkSettings']['Networks'][
                            list(container.attrs['NetworkSettings']['Networks'])[0]]['IPAddress'] + ":" + \
                              container.attrs['NetworkSettings']['Ports'][
                                  list(container.attrs['NetworkSettings']['Ports'])[i]][0]['HostPort']
        try:
            dictofcas['URL'] = url
        except UnboundLocalError:
            print("Cannot find Fabric CA Docker Containers")
            sys.exit()

        content = {
            ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]: ast.literal_eval(
                _replace_content(dictofcas, template))}
        dictca.update(content)

        dictca[ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]]['tlsCACerts'][
            'pem'] = repr(ca['certificateAuthorities'][
                              ca['organizations'][list(ca['organizations'].keys())[0]]['certificateAuthorities'][0]][
                              'tlsCACerts']['pem'])[1:-1]

    CONTENT['CA_URL'] = listofcaurls
    CONTENT['CAS'] = dictca


def _replace_value(input_file, tag, value):
    if tag in TAGS_REQUIRING_QUOTES:
        regex = REGTAG + tag + REGTAG
    else:
        regex = REGTAGLEADING + tag + REGTAGTAILING
    return re.sub(regex, value, str(input_file))


def _replace_content(value_dict, input_file):
    for key in value_dict:
        input_file = _replace_value(input_file, key, str(value_dict[key]))
    return input_file


def _add_to_content(key, value):
    CONTENT[key] = value


def _check_for_remaining_tags(input_file):
    if len(re.findall(CHECKREGEX, input_file)):
        return True
    else:
        return False


def _check_for_valid_json(input_file):
    try:
        json.loads(input_file)
    except ValueError:
        return False
    return True


def _check_file_exists(path):
    return os.path.isfile(path)


def _read_folder_content(path):
    return os.listdir(path)


def create_folder_structure():
    _ensure_path(CURRENT_DIR + BASE_CONFIG_DIR)
    _ensure_path(CURRENT_DIR + BASE_CONFIG_DIR + FABRIC_CONFIG_DIR)
    _ensure_path(CURRENT_DIR + BASE_CONFIG_DIR + EXPLORER_CONFIG_BASE_DIR)
    _ensure_path(CURRENT_DIR + BASE_CONFIG_DIR + EXPLORER_CONFIG_BASE_DIR + EXPLORER_CONFIG_PROFILE_DIR)
    _ensure_path(CURRENT_DIR + BASE_CONFIG_DIR + EXPLORER_CONFIG_BASE_DIR + EXPLORER_CRYPTO_DIR)

    _move_files(EXPLORER_CONFIG_FILE, CURRENT_DIR + TEMPLATE_DIR,
                CURRENT_DIR + BASE_CONFIG_DIR + EXPLORER_CONFIG_BASE_DIR)

    _move_files(EXPLORER_NETWORK_FILE, CURRENT_DIR + TEMPLATE_DIR,
                CURRENT_DIR + BASE_CONFIG_DIR + EXPLORER_CONFIG_BASE_DIR + EXPLORER_CONFIG_PROFILE_DIR)


def _create_output_json():
    template = _read_invalid_json(NETWORK_TEMPLATE)
    _write_file(_replace_content(CONTENT, template), 'first-network')


if __name__ == '__main__':

    client = docker.from_env()
    containers = client.containers.list()

    print('=' * 35 + ' Creating folder structure and moving configuration files ' + '=' * 35)
    create_folder_structure()
    print('=' * 128)

    print('PLEASE COPY THE FABRIC CONNECTION PROFILES TO: %s' % (CURRENT_DIR + BASE_CONFIG_DIR + FABRIC_CONFIG_DIR))
    input('Press Enter to continue...')

    print('=' * 128)
    print('Found Fabric connection profiles:')
    fabric_folder_content = _read_folder_content(CURRENT_DIR + BASE_CONFIG_DIR + FABRIC_CONFIG_DIR)
    print(fabric_folder_content)

    print('=' * 46 + ' Reading Fabric connection profiles ' + '=' * 46)
    fabric_connection_jsons = []
    for item in fabric_folder_content:
        print('Reading Fabric connection file: %s' % item)
        fabric_connection_jsons.append(_read_json(CURRENT_DIR + BASE_CONFIG_DIR + FABRIC_CONFIG_DIR + item))

    print('=' * 57 + ' Creating Orgs ' + '=' * 56)

    _create_org(fabric_connection_jsons)

    print('=' * 56 + ' Creating peers ' + '=' * 56)

    _build_peers(fabric_connection_jsons, containers)

    print('=' * 57 + ' Creating Cas ' + '=' * 57)

    _create_ca(fabric_connection_jsons, containers)

    print('=' * 55 + ' Creating Orderers ' + '=' * 54)

    _create_orderers(containers)

    print('=' * 57 + ' Writing json ' + '=' * 57)

    _create_output_json()

    print('=' * 128)
