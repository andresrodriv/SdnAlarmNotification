"""
Author Emanuele Gallone, 05-2020

Unfortunately I discovered that the python implementation of SQLITE is not thread safe.
To cope with this issue, I created a wrapper class that is thread-safe (hopefully)
by creating methods that resembles atomic operations.

To avoid SQLInjections, NEVER append the parameters directly inside the SQL statements.

Issue #2: Performances.
Sqlite is known for its poor performances but it's simple to implement and for the purpose of this project
is more than enough. You want to change this with another DB as soon as you can. trust me.

"""
import sqlite3
import threading
import logging
import os
from datetime import datetime

MAX_NUM_OF_THREADS_PER_OPERATION = 1
semaphore = threading.Semaphore(MAX_NUM_OF_THREADS_PER_OPERATION)  # creating a global lock mechanism

dirname = os.path.dirname(__file__)
default_url = os.path.join(dirname, '../local.db')


class DBHandler(object):

    def __init__(self, db_url=default_url):
        self._db_url = db_url
        self._connection = None
        self._cursor = None

    def open_connection(self):
        #  should I check here if table exists?

        if self._cursor is None:
            self._connection = sqlite3.connect(self._db_url)
            self._cursor = self._connection.cursor()
        return self

    def close_connection(self):
        semaphore.acquire()

        if self._connection is not None:
            self._connection.commit()  # save all changes
            self._connection.close()

        del self  # prevent memory leak

        semaphore.release()

    def create_alarm_table(self):
        semaphore.acquire()
        # from here on, thread-safe environment!
        try:
            self._cursor.execute('''CREATE TABLE IF NOT EXISTS alarm
                         (ID INTEGER PRIMARY KEY ,deviceIP text , severity text,
                          description text, time timestamp, notified integer, ceased integer)''')

        except Exception as e:
            print("something wrong creating alarm table" + str(e))

        finally:
            semaphore.release()  # avoiding deadlock

    def select_alarm_by_ID(self, ID='0'):
        semaphore.acquire()

        result = ''

        try:
            t = (ID,)
            self._cursor.execute('SELECT * FROM alarm WHERE ID=?', t)
            result = self._cursor.fetchone()

        except Exception as e:
            logging.log(logging.ERROR, "something wrong selecting alarm by ID" + str(e))

        finally:
            semaphore.release()

        return result

    def select_alarm_by_severity_unnotified(self, severity):
        semaphore.acquire()

        if severity is None:
            severity = '0'

        notified = 0
        t = (severity, notified)

        self._cursor.execute('SELECT * FROM alarm WHERE (severity>=?) AND (notified=?) ORDER BY severity desc', t)
        result = self._cursor.fetchall()

        semaphore.release()

        return result

    def select_count_by_device_ip(self, description, host):
        semaphore.acquire()

        if description is None or host is None:
            description=''
            host=''

        t =(description, host)

        self._cursor.execute('SELECT COUNT() FROM alarm WHERE DESCRIPTION=? AND deviceIP=?', t)
        result = self._cursor.fetchall()

        semaphore.release()

        return result

    def select_alarm_by_host_time_severity(self, host, timestamp, severity):
        semaphore.acquire()

        t = (host, timestamp, severity)

        self._cursor.execute('SELECT * FROM alarm WHERE (deviceIP=?) AND (time =?) AND (severity=?)', t)
        result = self._cursor.fetchall()

        semaphore.release()

        return result

    def select_alarm_by_device_ip(self, host):
        semaphore.acquire()

        t = (host,)

        self._cursor.execute('SELECT * FROM alarm WHERE (deviceIP=?)', t)
        result = self._cursor.fetchall()

        semaphore.release()

        return result

    def select_ceased_alarms(self):
        semaphore.acquire()

        ceased = 1
        t = (ceased,)

        self._cursor.execute('SELECT * FROM alarm WHERE (ceased=?)', t)
        result = self._cursor.fetchall()

        semaphore.release()

        return result


    def select_all(self):
        semaphore.acquire()

        self._cursor.execute('SELECT * FROM alarm')
        result = self._cursor.fetchall()

        semaphore.release()

        return result

    def insert_row_alarm(self, device_ip='0.0.0.0', severity='0', description='debug', _time=None, notified=0, ceased=0):
        semaphore.acquire()

        if _time is None:
            _time = datetime.now()

        t = (device_ip, severity, description, _time, notified, ceased)

        self._cursor.execute('''INSERT INTO alarm 
            (deviceIP, severity, description, time, notified, ceased) VALUES (?, ?, ?, ?, ?, ?)''', t)

        semaphore.release()

    def count_alarms(self):
        semaphore.acquire()

        self._cursor.execute('''SELECT count(ID), severity FROM alarm GROUP BY severity''')
        _result = self._cursor.fetchall()

        semaphore.release()

        return _result

    def update_ceased_alarms(self, ID):
        semaphore.acquire()

        ceased = 1
        t = (ID, ceased)

        self._cursor.execute('UPDATE alarm SET ceased = ? WHERE ID = ?', t)

        semaphore.release()

    def update_notified_by_ID(self, ID):
        semaphore.acquire()

        notified = 1

        if len(ID) == 0:
            semaphore.release()
            return

        t = [(notified, _id) for _id in ID]

        self._cursor.executemany('UPDATE alarm SET notified = ? WHERE ID = ?;', t)

        semaphore.release()


if __name__ == '__main__':
    # create local.db script
    db = DBHandler().open_connection()
    db.create_alarm_table()

    db = DBHandler().open_connection()
    result = db.count_alarms()
    db.close_connection()
