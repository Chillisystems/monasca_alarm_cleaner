import shade
import logging

from monascaclient import client
import monascaclient.exc as exc

log = logging.getLogger(__name__)

class MonascaCleaner(object):
    '''
        Monasca Leftover Alarms cleaner class
    '''
    def __init__(self, cloud_name, api_version, monasca_url, verbose, debug):
        self.cloud = shade.OpenStackCloud(cloud=cloud_name)
        self.client = self._get_monasca_client(api_version, monasca_url, self.cloud.auth_token)
        self._setup_logging(debug)
        self._setup_verbose(verbose)

    def clean_alarms(self):
        ''' Remove alarms from monasca which are in UNDEERMINED state
            and do not belong to any active VM '''

        alarms_to_delete = self.list_vm_undetermined_alarms()

        for alarm in alarms_to_delete:
            log.info("Removing alarm id: %s with state %s",
                     alarm.get('alarm_id'), alarm.get('state'))
            self.client.alarms.delete(**{'alarm_id': alarm.get('alarm_id')})

    def list_vm_undetermined_alarms(self):
        ''' Get list of alarms in undetermined state, if this alarm has and
            dimension assigned resource_id(nova vm id) we add it to vm_ids list.

            TODO: Write unit tests here
                    - test UNDETERMINED alarm for live VM
                    -
        '''
        data = self.client.alarms.list()
        vms = self._list_active_vms()

        alarm_info = []

        for alarm in data:
            if alarm.get('state') == 'UNDETERMINED':
                vm_ids = self._list_filter_resource_ids(alarm.get('metrics', []), vms)
                if vm_ids:
                    alarm_info.append({'alarm_id': alarm.get('id'),
                                       'state': alarm.get('state'),
                                       'vm_ids': vm_ids,
                                      })

        return alarm_info

    def _list_active_vms(self):
        ''' Return list of active vm ids '''
        return list(server.id for server in self.cloud.nova_client.servers.list(
            search_opts={'all_tenants': 1}, limit=-1))

    @classmethod
    def _list_filter_resource_ids(cls, metrics, active_vm_ids=[]):
        '''
            Return dimension resource ids for metrics which
                - component is 'vm'
                - resource_id is not in active_vm list
        '''
        get_dim = lambda resource, entity: resource.get('dimensions', {}).get(entity)

        ids = []

        for res in metrics:
            resource_id = get_dim(res, 'resource_id')
            if get_dim(res, 'component') == 'vm' and (resource_id not in ids or
                                                      resource_id not in active_vm_ids):
                ids.append(resource_id)
        return ids
        #return {get_dim(res, 'resource_id') for res in metrics
         #       if get_dim(res, 'component') == 'vm'}

    @classmethod
    def _get_monasca_client(cls, api_ver, monasca_url, auth_token):
        return client.Client(api_ver, monasca_url, token=auth_token)

    @classmethod
    def _setup_logging(cls, debug):
        log_lvl = logging.DEBUG if debug else logging.ERROR
        logging.basicConfig(
            format="%(levelname)s (%(module)s:%(lineno)d) %(message)s",
            level=log_lvl)
    @classmethod
    def _setup_verbose(cls, verbose):
        if verbose:
            exc.verbose = 1
