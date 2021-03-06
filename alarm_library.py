"""
Author Emanuele Gallone, 05-2020

a bunch of useful methods retrieving alarms from SDN devices using NETCONF.
uses a façade pattern exposing only one method.

"""

import threading, time, traceback, logging, os

from models.database_manager import DBHandler
from models.config_manager import ConfigManager
from models.device import Device
from models.customXMLParser import CustomXMLParser

from ncclient import manager
from typing import List

####################setting up globals###################

logging.basicConfig(filename="log.log", level=logging.ERROR)

config_m = ConfigManager()

# reading the config.json and creating the devices
devices = [Device(d['device_ip'],
                  d['netconf_fetch_rate_in_sec'],
                  d['netconf_port'],
                  d['netconf_user'],
                  d['netconf_password'])
           for d in config_m.get_network_params()]

lock = threading.Lock()


#########################################


def _worker(_delay, task, *args):
    # todo specify thread's stop condition? maybe through a SIGINT
    """
    worker definition for thread task

    @param _delay: it specifies the delay in which the task will be performed
    @param task: pointer to the function that will be executed by the thread
    @param args: list of arguments that will be passed to the task's parameters
    @return: void
    """
    next_time = time.time() + _delay
    while True:
        time.sleep(max(0, next_time - time.time()))  # making the threads not wasting CPU cycles

        try:
            task(*args)
        except Exception:
            traceback.print_exc()

            logging.exception("Problem while trying to retrieve alarms' data.")
            # skip tasks if we are behind schedule: todo: refactor using schedule library
        next_time += (time.time() - next_time) // _delay * _delay + _delay


def _detail_dummy_data_fetch() -> str:
    """
    I created this method to have a dummy data in case a device goes down or VPN isn't working
    NB: for testing purpose only
    @return: xml in string format
    """

    filename = os.path.join(os.path.dirname(__file__), 'dummy_data.xml')
    string_result = ''

    with open(filename, 'r') as _file:
        for _line in _file:
            # if "<?xml " in line:  # remove the xml prolog
            #     continue

            string_result += (_line.rstrip())

    return string_result


def _thread_get_alarms(device):
    """
    this method is ran by the various threads. It is the core concept of the alarm library
    @param device: Device object containing all the informations. (see models/device.py)
    @return: void
    """
    try:
        _xml = _get_alarms_xml(device)  # try to connect to netconf

    except Exception as e:  # in case the device or vpn are down, load dummy data (Testing Purpose)

        logging.log(logging.ERROR, "Could not retrieve data from netconf! switching to dummy data\n" + str(e))
        _xml = _detail_dummy_data_fetch()

    alarms_metadata = CustomXMLParser(_xml).parse_all_alarms_xml()

    #_check_if_alarm_has_ceased(host, alarms_metadata) # to be implemented

    _thread_save_to_db(device.ip, alarms_metadata)  # finally save the information in DB


def _thread_save_to_db(host, parsed_metadata):
    """
    method used by the various threads to save inside the local.db all the metadata that we need.
    Here the things gets a little tricky:
    basically, parsed_metadata is a list of dictionaries. Each dictionary is an alarm.
    If you want to know how the dictionary is built look at _parse_all_alarms_xml(_root)

    @param host: specifies the host IP
    @param parsed_metadata: is a list of dictionaries that is coming from the method '_parse_all_alarms_xml(_root)'
    @return: void
    """

    _config_manager = ConfigManager()
    flag = _config_manager.get_alarm_dummy_data_flag()

    if flag == True:  # we do not want to save again the same alarms (DEBUG), should refactor this to be clearer
        parsed_metadata = __filter_if_alarm_exists_in_db(host, parsed_metadata)

    for alarm_dict in parsed_metadata:

        try:
            lock.acquire()  # need to lock also here because sqlite is s**t

            severity_levels = config_m.get_severity_levels()
            severity = severity_levels[alarm_dict['notification-code']]
            description = alarm_dict['condition-description']
            timestamp = alarm_dict['ne-condition-timestamp']

            db_handler = DBHandler().open_connection()

            db_handler.insert_row_alarm(device_ip=host,
                                        severity=severity,
                                        description=description,
                                        _time=timestamp)
            db_handler.close_connection()

        except Exception as e:
            logging.log(logging.ERROR, str(e))

        finally:
            lock.release()


def _check_if_alarm_has_ceased(host, alarms):
    """
    if some alarm from the same device does not show up in the new netconf data fetch,
    it means that it has ceased and we set the table attribute 'ceased' to 1
    so that we can notify that the specific alarm has ceased
    @param host: device ip
    @param alarms: list of dict where each dict is an alarm
    @return: void
    """

    raise NotImplementedError

    _db_handler = DBHandler()

    _db_handler.open_connection()

    # get the alarms of that particular host
    alarms_in_db = _db_handler.select_alarm_by_device_ip(host)

    if len(alarms_in_db) == 0:  # return because is a useless check
        return

    # get only the alarm id and timestamp
    id_and_timestamp = set([(_tuple[0], _tuple[4]) for _tuple in alarms_in_db])
    # there is a more clever way to do this

    temp = set(_alarm['ne-condition-timestamp'] for _alarm in alarms)

    for alarm in id_and_timestamp:
        _alarm_id = alarm[0]
        _timestamp = alarm[1]
        if _timestamp not in temp:
            print("alarm ceased: " + str(_alarm_id))


def __filter_if_alarm_exists_in_db(host, array) -> List:
    """
    helper method to avoid the repetition of inserting existing alarms in db.
    It is used due to not having the possibility to create alarms ourselves.
    By not using this filter, every new alarms fetched through netconf will be seen as a 'new' alarm.

    @param host: device ip
    @param array: list of dict where each dict is an alarm
    @return: list of dict alarms, where these alarms are not present in db
    """

    _filtered_alarms = []

    _db_handler = DBHandler()
    _db_handler.open_connection()

    _severity_levels = config_m.get_severity_levels()  # needed for parsing the alarm notification code from text to int

    for _dict in array:  # element of array is a dict, each dict is an alarm
        severity = _severity_levels[_dict['notification-code']]
        timestamp = _dict['ne-condition-timestamp']

        _result = _db_handler.select_alarm_by_host_time_severity(host, timestamp, severity)

        if len(_result) == 0:
            _filtered_alarms.append(_dict)

    _db_handler.close_connection()

    return _filtered_alarms


def _get_alarms_xml(device) -> str:
    """
    method that connect to the specified host,port using the credentials specified in user,password to retrieve
    alarm information
    @param device: Device object containing all the informations (see models/device.py)
    @return: xml from netconf, as a string
    """
    with manager.connect(host=device.ip,
                         port=device.netconf_port,
                         username=device.user,
                         password=device.password,
                         timeout=10,
                         hostkey_verify=False) as conn:

        retrieve_all_alarms_criteria = """
        <managed-element xmlns:acor-me="http://www.advaoptical.com/aos/netconf/aos-core-managed-element"> 
        <alarm/> </managed-element>
        """

        filter = ("subtree", retrieve_all_alarms_criteria)
        result = conn.get(filter).xml

    return result


def start_threads() -> List:
    """
    method available on the outside. it start all the magic to retrieve the alarms on the devices
    listed inside the config.json. It starts a thread for each device found in the config.json file

    @return: List of threads that need to be joined outside
    """
    _threads = []

    for device in devices:
        _t = threading.Thread(target=lambda: _worker(device.netconf_rate, _thread_get_alarms, device))
        _t.start()
        _threads.append(_t)

    return _threads


if __name__ == "__main__":
    # DEBUG

    threads = start_threads()

    for t in threads:
        t.join()


    result = ''
    with open('dummy_data.xml', 'r') as file:
        for line in file:
            result += line.rstrip()

    temp = CustomXMLParser(result).parse_all_alarms_xml()
    res = _check_if_alarm_has_ceased('10.11.12.21', temp)
