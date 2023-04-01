import json
import copy
import requests

class Unifi:
    """Create a Unifi manager that is able to connect to the API and do several
    action related to Unifi
    """

    def __init__(self, username, password) :
        self.devices = {}
        self.cookie = None
        self.raw_device = {}
        self.downed_devices = []
        self.username = username
        self.password = password
        self.raw_legacy_devices = None
        self.users = {}
        self.connect()

    def connect(self) :
        """Connect the Unifi manager to the API by getting new credentials
        """
        data = {'username':self.username, 'password':self.password}
        headers = {'Content-Type': 'application/json'}
        initial_request = requests.post('https://unifi.yourdomain.com:8443/api/login',
         data = json.dumps(data), headers=headers, timeout=10)
        self.cookie = initial_request.cookies

    def restart(self,mac) :
        """Restart the AP given a mac-address

        Args:
            mac (str): The address mac of the AP you want to restart

        Returns:
            tuple: Tuple containing a message and a 0 or 1 depending on if the AP is restarting
        """
        url = "https://unifi.yourdomain.com:8443/api/s/default/cmd/devmgr"
        headers = {'X-Csrf-Token' : self.cookie.get_dict()['csrf_token']}
        data = {'mac': mac,'reboot_type':'soft','cmd':'restart'}
        try :
            restart_request = requests.post(url, headers= headers,
            data = json.dumps(data), cookies=self.cookie, timeout = 10)
        except :
            return ("Error occured while requesting "+ url)
        if restart_request.json()['meta']['rc'] != 'ok' :
            return ("An error occured while restarting ", 0)
        return ("Restarting device ", 1)

    def update_users(self) :
        """Update users data

        Returns:
            int: The number of current connected users
        """
        url = "https://unifi.yourdomain.com:8443/api/s/default/stat/sta"
        try :
            device_request = requests.get(url, cookies=self.cookie, timeout=10)
            data = device_request.json()
        except :
            return ("Error occured while requesting "+ url)

        self.users = {}
        for user in data['data']:
            hostname = user['hostname'] if 'hostname' in user.keys() else 'unknown'
            mac = user['mac'] if 'mac' in user.keys() else 'unknown'
            ap_mac = user['ap_mac'] if 'ap_mac' in user.keys() else 'unknown'
            vlan = str(user['vlan']).lower() if 'vlan' in user.keys() else 'unknown'
            if 'mac' in user.keys():
                self.users[mac] = {'vlan':vlan, 'hostname':hostname, 'ap_mac':ap_mac}

        return len(self.users)

    def get_ap_from_vlan(self, vlan):
        """Given a vlan, returns the APs to wich this vlan is currently connected

        Args:
            vlan (str): The vlan string

        Returns:
            list: A list of tupple containing for each AP that has this vlan, 
            the name of the device connected by this vlan and the name of the AP
        """
        device_list = []
        for user_device in self.users.items() :
            if user_device[1]['vlan'] == vlan :
                device_list.append(user_device[1])
        device_name_list = [user_device['hostname'] for user_device in device_list]
        ap_mac_list = [user_device['ap_mac'] for user_device in device_list]
        ap_name = {}
        for user_device, device_mac in zip(device_name_list, ap_mac_list) :
            for device in self.devices.items() :
                if device[1]['mac'] == device_mac:
                    ap_name[user_device] = device[0]
        ap_name_for_each_device = list(ap_name.items())
        return ap_name_for_each_device

    def get_near_ap(self, vlan) :
        """Given a vlan, returns AP that are near to this vlan (based on name similarities)

        Args:
            vlan (str): The vlan

        Returns:
            dict: A dictionnary : keys are the device name connected with this vlan 
            and values are a list of APs near that device
        """
        near_ap = {}
        ap_name_for_each_device = self.get_ap_from_vlan(vlan)
        for accessp in self.devices:
            for user_device, ap_name in ap_name_for_each_device :
                if len(accessp) >= 3 and accessp[:3].lower() == ap_name[:3].lower() :
                    try :
                        near_ap[user_device].append(accessp.lower())
                    except :
                        near_ap[user_device] = [accessp.lower()]
        return near_ap, [ap_name.lower() for _, ap_name in ap_name_for_each_device]

    def update_device_data(self):
        """Update data about APs
        """
        url = "https://unifi.yourdomain.com:8443/api/s/default/stat/device"
        try :
            device_request = requests.get(url, cookies=self.cookie, timeout=10)
            data = device_request.json()
        except :
            return("Error occured while requesting "+ url)
        self.raw_legacy_devices = copy.deepcopy(self.raw_device)
        self.raw_device = data
        self.devices = {}
        for device in data['data'] :
            self.devices[device['name'][5:].lower()] = {'mac': device['mac'], 'state' : device['state']}
        return "Found " + str(len(self.devices)) + " devices."
    
    def check_is_alive(self, name):
        """Given an AP name, returns the status of the AP

        Args:
            name (str): The name of the AP

        Returns:
            string: Either the state or 'unexisting' if this AP doesn't exist
        """
        if self.devices[name.lower()]['state'] == 0 :
            return 'disconnected'
        else :
            return 'connected'

    def find_mac_by_name(self, name) :
        """Returns the name of an AP given his mac-address

        Args:
            name (str): The name of the AP

        Returns:
            str: The corresponding mac-address
        """
        try :
            return self.devices[name.lower()]['mac']
        except :
            return "unexisting"

    def get_downed_devices(self) :
        """Returns downed AP, number of new downed AP since last check,
         number of users that got disconnected since last health chek
        """
        downed = []
        lost_users = 0
        for index,name in enumerate(self.devices.keys()) :
            if self.devices[name]['state'] == 0 and self.raw_legacy_devices is not None:
                downed.append(name)
                try :
                    lost_users += int(self.raw_legacy_devices['data'][index]['num_sta'])
                except :
                    lost_users = 0
        delta =  len(downed) - len(self.downed_devices)
        self.downed_devices = downed
        return(downed, delta, lost_users)
