import docker

if __name__ == '__main__':
    client = docker.from_env()
    containers = client.containers.list()

    for container in containers:
        if "explorer.mynetwork.com" in container.attrs['Name']:
            print("IP address of Hyperledger Explorer: %s" % container.attrs['NetworkSettings']['Networks'][
                list(container.attrs['NetworkSettings']['Networks'])[0]]['IPAddress'])
