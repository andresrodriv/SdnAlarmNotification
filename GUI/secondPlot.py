import logging
from PyQt5 import QtCore, QtGui, QtWidgets,uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout
import sys
from models.database_handler import DBHandler
from models.config_manager import ConfigManager
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import os
import random
dirname = os.path.dirname(__file__)
import numpy as np
import sqlite3
import datetime
from models import database_handler

logging.basicConfig(filename="../../log.log", level=logging.ERROR)
class Plot2(FigureCanvas):
    def __init__(self, parent=None, width=7, height=5, dpi=100,updateCheck=False):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        #self.fig.tight_layout()
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)
        self.updateCheck=updateCheck
        #self.barGraph(self.axes)
        self.axes.set_xlabel('IP addresses of the hosts')
        self.axes.set_ylabel('Number of Alarms')
        self.axes.set_title('Alarms by IP')

    def barGraph(self,axes):
        print("here")
        try:
            db = database_handler.DBHandler().open_connection()
            result = [tuple[1] for tuple in db.select_all()]
            labels = set(result)
            #print(labels)

            result = [tuple[3] for tuple in db.select_all()]
            alarms_description = set(result)
            #print(alarms_description)

            rects = []
            for alarms in alarms_description:
                means = []
                for ip in labels:
                    result = db.select_count_by_device_ip(alarms,ip)
                    means.append(result[0][0])
                rects.append(means)
            #print(rects)

            x = np.arange(len(labels))  # the label locations
            width = 1.5/len(alarms_description)  # the width of the bars
            fig, ax = plt.subplots()

            for i in range(0, len(rects)):
                bar = ax.bar(x + (i - (len(rects) - 1) / 2) * width / 2, rects[i], width / 2,
                             label=list(alarms_description)[i])
                self.autolabel(bar,ax)

            # Fabio aiutami qua
            axes.set_xticks(x)
            axes.set_xticklabels(labels)
            axes.legend(bbox_to_anchor= (0,-0.5),loc='lower left')
            axes.text(0, -0.1, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), verticalalignment='center',
                   transform=axes.transAxes)
            ###############################################
            ax.set_ylabel('Number of Alarms')
            ax.set_title('Alarms by IP')
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.legend()
            fig.tight_layout()
            plt.show()
            ##############################################
            db.close_connection()
        except Exception as e:
            logging.log(logging.ERROR, "something wrong opening the Data Base" + str(e))

    def reStartPlot2(self):
        self.axes.set_xlabel('IP addresses of the hosts')
        self.axes.set_ylabel('Number of Alarms')
        self.axes.set_title('Alarms by IP')
        self.barGraph(self.axes)


    def autolabel(self, rects, axes):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects:
            height = rect.get_height()
            axes.annotate('{}'.format(height),
            xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
