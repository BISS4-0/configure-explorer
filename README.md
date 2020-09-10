# Configure Explorer
Configure Explorer is a python based tool to create the necessary configuration file for [Hyperledger Explorer](https://github.com/hyperledger/blockchain-explorer).

## Requirements

Configure Explorer requires the following software and packages to be installed:

### Linux Software

- Python3 with pip

### Python packages

- barley_json
- docker

Python packages can be installed via `pip3 install -r requirements.txt` .

### Usage

0. Install required software and packages
1. Make sure that your Hyperledger Fabric is running
2. Copy the `connection.json` files of your Hyperledger Fabric (may be more then one depending on the number of Orgs) to `configure-explorer/configuration/fabric`
3. Run `python3 configure-explorer.py`
4. Copy the created `first-network.json` to your Hyperledger Explorer folder. To be more specific `blockchain-explorer/example/net1/connection-profile`
5. Start Hyperledger Explorer (`docker-compose up -d`) and wait until it started
6. Run `python3 get_explorer_ip_addr.py` to get the IP address of the Explorer Dashboard
