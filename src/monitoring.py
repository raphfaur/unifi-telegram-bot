import threading
import time
import copy
import unifi

class Monitoring(threading.Thread):
    """ AP Monitoring

    Args:
        threading ():
    """
    def __init__(self, unifi : unifi.Unifi) :
        super().__init__()
        self.stop_flag = threading.Event()
        self.info = ["Monitoring started !"]
        self.alert = []
        self.state = (0,0,0)
        self.unifi = unifi
        self.last_connect = time.time()
        self.watched = []
        self.downed_devices = []
        self.last_update = time.strftime("%H:%M:%S")

    def run(self):
        self.unifi.connect()
        while True :
            if self.stop_flag.is_set() : #On arrête le thread si le flag stop est set
                break
            #On redemande un cookie de connexion toutes les 60 secondes
            if time.time() - self.last_connect >= 60:
                self.unifi.connect()
                self.last_connect = time.time()
            self.unifi.update_users() #On actualise les données utilisateurs
            self.unifi.update_device_data() #On actualise les données des APs
            #On récupère les données de monitoring
            self.downed_devices, delta, lost_users = self.unifi.get_downed_devices()

            #On surveille les bornes qui rédémarrent
            for device in self.watched :
                if device[0] in self.downed_devices and device[1] :
                    self.info.append(f"Device {device[0]} is now disconnected ❌")
                    device[1] = 0
                if device[0] not in self.downed_devices and not device[1] :
                    self.info.append(f"Device {device[0]} is back ✅")
                    self.watched.remove(device)

            self.last_update = time.strftime("%H:%M:%S")
            self.state = (self.downed_devices, delta, lost_users)
            time.sleep(10) #On attend

    def watch(self, device) :
        """ watch device

        Args:
            device (_type_): _description_
        """
        self.watched.append([device, 1])

    def stop(self):
        """ stop monitoring
        """
        self.stop_flag.set()

    def get_info(self) :
        """get info

        Returns:
            _type_: _description_
        """
        infos = self.info[:]
        self.info = []
        return infos

    def get_state(self) :
        """get state

        Returns:
            _type_: _description_
        """
        state = copy.copy(self.state)
        self.state = (state[0],0,0)
        return state

    def get_alert(self):
        """get alerts

        Returns:
            _type_: _description_
        """
        alerts = self.alert[:]
        self.alert = []
        return alerts
