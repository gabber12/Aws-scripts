import boto.ec2
from collections import defaultdict

regions = {
    'ap-northeast-1': "Asia Pacific (Tokyo)",
    'ap-southeast-1': "Asia Pacific (Singapore)",
    # 'ap-southeast-2': "Asia Pacific (Sydney)",
    # 'eu-central-1': "EU (Frankfurt)",
    # 'eu-west-1': "EU (Ireland)",
    # 'sa-east-1': "South America (Sao Paulo)",
    # 'us-east-1': "US East (N. Virginia)",
    # 'us-west-1': "US West (N. California)",
    # 'us-west-2': "US West (Oregon)"
}
regions = {region.name: region.name for region in boto.ec2.regions()}


def get_volumes_by_region(region, filter=lambda x: True):
    
    conn = boto.ec2.connect_to_region(region)
    volumes = conn.get_all_volumes(volume_ids=None, filters=None)
    return [{'volume': volume.id, 'status': volume.status, 'size': volume.size} for volume in volumes if filter(volume)]


def get_instances_by_region(region, filter=lambda x: True):
    
    conn = boto.ec2.connect_to_region(region)
    instances = conn.get_all_instances()
    reservations = conn.get_all_reservations()
    return [{'id': i.id, 'type': i.instance_type, 'tags': i.tags.get('Name'), 'state': i.state}  for reservation in reservations for i in reservation.instances ]


def get_snapshots_by_region(region, filter=lambda x: True):
    
    conn = boto.ec2.connect_to_region(region)
    snapshots=conn.get_all_snapshots()
    return [{'volume':snaps.volume_id, 'size': snaps.volume_size, 'status': snaps.status} for snaps in snapshots if filter(snaps)]


def get_elastic_ips_by_region(region, filter=lambda x: True):
    
    conn = boto.ec2.connect_to_region(region)
    return [{'public_ip': eip.public_ip, 'private_ip': eip.private_ip_address, 'network_interface_id':eip.network_interface_id} for eip in conn.get_all_addresses() if filter(eip)]


def get_for_all_region(get_by_region, filter):
    return [{'data': get_by_region(region, filter), 'region': {'name': name, 'code': region}} for region, name in regions.items()];


class RegionPricingContext(object):

    def __init__(self, region):
        self.region = region
        self.context = None

    def populate_context(self):
        conn = boto.ec2.connect_to_region(self.region)
        print "Fetching Data for %s" % self.region
        print "\tFetching instances..."
        instances = [i for reservation in conn.get_all_reservations() for i in reservation.instances ]
        print "\tFetching snapsots..."
        snapshots = conn.get_all_snapshots()
        print "\tFetching volumes..."
        volumes   = conn.get_all_volumes()
        print "\tFetching eips..."
        eips      = conn.get_all_addresses()

        self.context = {
            'instances': instances,
            'snapshots': snapshots,
            'volumes': volumes,
            'eips': eips
        }

    def init(self):
        self.populate_context()

    def analyse(self):
        if self.context is None:
            self.init()

        self.print_summary()

    def get_unattached_eips(self):
        eips = self.context['eips']
        filter_unattached = lambda x: x.network_interface_id is None
        return [eip for eip in eips if filter_unattached(eip)]

    def get_unused_ebs(self):
        volumes = self.context['volumes']
        filter_unused = lambda x: x.status == 'available'
        return [ebs for ebs in volumes if filter_unused(ebs)]


    def print_summary(self):
        unattached_eips = self.get_unattached_eips()
        print_banner("Elastic Ips")
        unattached_eips_summary = [{'public_ip': eip.public_ip, 'private_ip': eip.private_ip_address, 'network_interface_id':eip.network_interface_id} for eip in unattached_eips]
        print_table(unattached_eips_summary)

        print_banner("Elastic Block Storage")
        unattached_ebs = self.get_unused_ebs()
        unattached_ebs_summary = [{'volume': volume.id, 'status': volume.status, 'size': volume.size} for volume in unattached_ebs]
        print_table(unattached_ebs_summary)

        print_banner("EBS Volume Snapshots")
        all_snapshots = sorted([{'id': snap.id, 'volume_id': snap.volume_id} for snap in self.context['snapshots']], key=lambda x: x['volume_id'])
        redundant_snapshots = get_redundant_snapshots(all_snapshots)
        print_table(redundant_snapshots)

def get_redundant_snapshots(snaps):
    index_by_volume = dict()
    for snap in snaps:
        if snap['volume_id'] not in index_by_volume:
            index_by_volume[snap['volume_id']] = []
        index_by_volume[snap['volume_id']].insert(-1, snap['id'])
    return sorted([{'volume_id': key, '# snapshots': len(value)} for key, value in index_by_volume.items() if len(value) > 1], key= lambda x: x['# snapshots'], reverse= True)


def print_banner(label):
    len_label = len(label)
    print "="*(40+len_label)
    print "|"+" "*19 + label+" "*19+"|"
    print "="*(40+len_label)
def print_table(data):
    # print data
    if len(data) < 1:
        print "No data"
        return
    row_format ="{:^30}" * (len(data[0]))
    print row_format.format(*data[0].keys())
    for row in data:
        print row_format.format(*row.values())

if __name__ == '__main__':
    for region in regions:
        print_banner("REGION - %s"%(region))
        rpc = RegionPricingContext(region);
        rpc.analyse()

