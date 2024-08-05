from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtSerialPort import QSerialPortInfo
from PyQt6.QtGui import QPixmap, QAction
from pathlib import Path
from hexview import drawhex
from functools import partial
import serial
import tempfile
from sys import exit
import json

app = QtWidgets.QApplication([])
ui = uic.loadUi("29prog.ui")
# C:/Users/kroko/Desktop/Z80/test/test2.hex
work_file = ""
hex_vars = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F"]
chips = ["29C256", "28C256", "28C64", "28C16", "27C512"]
chip_conf = {"29C256": "32K", "28C256": "32K", "28C64": "8K", "28C16": "2K", "27C512": "64K,UV"}
recent = []
memorySize = 0
dummySize = 2047
readedData = ""
isProgConnected = False
# settings = {"chip": chips[0], "uart": 115200, "erase": False}
settings = {}

BUFFER = []
for i in range(64):
    BUFFER.append("ff")


def loadBlock(data):
    req = ""
    for d in data:
        req += str(d)
    request = f"load,{req}"
    ser.write(bytes(request, 'utf-8'))
    return ser.readline()


def writeOneBlock(block, data):
    print(f"Writing block {block}...")
    loadBlock(data)

    request = f"write,{block}"
    ser.write(bytes(request, 'utf-8'))
    if settings["verify"] != 2:
        return ser.readline()
    else:
        ser.readline()
        read = str(readBlock(block)).replace("b'", "").replace("\\r\\n'", "").lower()
        readArray = read.split("_")
        if data != readArray:
            QMessageBox.critical(ui, "Error", f"Verification error at block {block}.\nWriting terminated.")
            raise ValueError


def writeFromFile():
    file = work_file
    hex_lst = []
    try:
        with open(file, 'rb') as file:
            s = file.read()
        if settings["erase"] == 2 and "UV" not in chip_conf[ui.selectChip.currentText()]:
            erase()
        for i in range(len(s)//16):
            sect_s = s[i * 16: (i + 1) * 16]  # a = slice(i *16 : (i + 1)*16)
            new_s = ""
            for j in sect_s:
                if len(hex(j)[2:]) == 1 and hex(j)[0].isalpha:
                    new_s += f'0{hex(j)[2:]} '
                elif len(hex(j)[2:]) == 1:
                    new_s += f'{hex(j)[2:]} '
                else:
                    new_s += f'{hex(j)[2:]} '
            new_s += '    '
            hex_list = new_s.split()
            hex_lst += hex_list
        ui.progressBar.setMaximum(int(len(hex_lst)))
        ui.progressBar.setValue(int(len(hex_lst)/100))
        for i in range(int(len(hex_lst)/64)+1):
            j: int = 0
            for j in range(64):
                if j+64*i >= len(hex_lst):
                    print("Done Writing")
                    ui.progressBar.setValue(ui.progressBar.maximum())
                    return
                BUFFER[j] = hex_lst[j+64*i]
            writeOneBlock(i, BUFFER)
            ui.progressBar.setValue(j+64*i)
    except ValueError:
        return 0
    except Exception as ex:
        QMessageBox.warning(ui, "Warning", "No opened files")
        print(f"WriteError: File is not available {ex}")


def updateports():
    portlist = []
    ports = QSerialPortInfo().availablePorts()
    for port in ports:
        portlist.append(port.portName())
    ui.com.clear()
    ui.com.addItems(portlist)


def openport():
    global isProgConnected
    try:
        ser.baudrate = 115200
        ser.port = ui.com.currentText()
        ser.open()
        ui.state.setText(f"Connected on {ser.name}")
        ui.read.setStyleSheet("color : black")
        ui.write.setStyleSheet("color : black")
        ui.read.setEnabled(True)
        ui.write.setEnabled(True)
        isProgConnected = True
        updateChip()
    except Exception as ex:
        print(ex)
        ui.state.setText("Error")


def openfile(fname=False):
    global work_file
    if not fname:
        home_dir = str(Path.home())
        name = QFileDialog.getOpenFileName(ui, 'Open file', home_dir)
        work_file = name[0]
    else:
        work_file = fname
    if work_file == "":
        return

    if work_file not in recent[-5:]:
        recent.append(work_file)
        with open("recent.json", "w") as conf:
            conf.write(json.dumps(recent))
        fillRecent()
    ui.setWindowTitle(f"Flash&EEPROM programmer: {work_file}")
    ui.filecontent.setText(drawhex(work_file))


def readToFile():
    global readedData
    global work_file
    work_file = ""
    ui.setWindowTitle(f"Flash&EEPROM programmer")
    code = ""
    LEN = int(memorySize/64)
    ui.progressBar.setMaximum(LEN)
    for i in range(0, LEN):
        ui.progressBar.setValue(i+1)
        line = str(readBlock(i)).replace("b'", "").replace("_", "").replace("\\r\\n'", "")
        code = code + line

    readedData = code
    fp = tempfile.TemporaryFile()
    fp.write(bytes.fromhex(code))
    fp.seek(0)
    ui.filecontent.setText(drawhex(fp, type=0))

    print("Done reading.")


def readBlock(block):
    # bit1 = byte >> 8
    # bit2 = byte ^ bit1 << 8
    request = f"read,{block}"
    try:
        ser.write(bytes(request, 'utf-8'))
        return ser.readline()
    except Exception as ex:
        print(ex)


def saveFile():
    global work_file
    if work_file == "":
        home_dir = str(Path.home())
        name = QFileDialog.getOpenFileName(ui, 'Open file', home_dir)
        work_file = name[0]
    with open(work_file, "wb") as file:
        file.write(bytes.fromhex(readedData))


def updateChip():
    global memorySize
    if work_file == "":
        drawDummyHex()
    memorySize = int(chip_conf[ui.selectChip.currentText()].split("K")[0]) * 1024
    if not isProgConnected:
        return 0
    if "UV" in chip_conf[ui.selectChip.currentText()]:
        ui.erase.setEnabled(False)
        ui.erase.setStyleSheet("color : gray")
        ui.autoerase.setEnabled(False)
        ui.autoerase.setStyleSheet("color : gray")
        ui.actionAutoerase.setEnabled(False)
    else:
        ui.erase.setEnabled(True)
        ui.erase.setStyleSheet("color : black")
        ui.autoerase.setEnabled(True)
        ui.autoerase.setStyleSheet("color : black")
        ui.actionAutoerase.setEnabled(True)


def fillRecent():
    global recent
    ui.menuRecent.clear()
    with open("recent.json") as conf:
        recent = json.loads(conf.read())
    for rec in recent[-5:]:
        act = QAction(rec, ui)
        act.triggered.connect(partial(openfile, rec))
        ui.menuRecent.addAction(act)


def saveSettings():
    settings["chip"] = ui.selectChip.currentText()
    with open("conf.json", "w") as conf:
        conf.write(json.dumps(settings))


def loadSettings():
    global settings
    global memorySize
    with open("conf.json") as conf:
        settings = json.loads(conf.read())
    ui.selectChip.setCurrentText(settings["chip"])
    ui.com.setCurrentText(settings["uart"])
    ui.actionAutoerase.setChecked(settings["erase"])
    ui.actionAutoconnect.setChecked(settings["connect"])
    ui.autoerase.setChecked(settings["erase"])
    ui.autoverify.setChecked(settings["verify"])
    drawDummyHex()
    memorySize = int(chip_conf[settings["chip"]].split("K")[0])*1024
    if ui.com.currentText() == settings["uart"] and settings["connect"]:
        openport()


def drawDummyHex():
    dummy = ' ' * 10 + ' '.join([f'{""}0{hex(i)[2:]}' for i in range(16)]) + '\n'
    for j in range(int(memorySize/16)-1):
        dummy += ('{:0>6}'.format(hex((j + 1) * 16)[2:]) + '    ' + "ff "*16 + "    " + "ÿ"*16 + "\n")
    ui.filecontent.setText(dummy)


def erase():
    ser.write(bytes("erase", 'utf-8'))
    return ser.readline()


def setEraseMode(checked):
    settings["erase"] = checked
    ui.actionAutoerase.setChecked(settings["erase"])
    ui.autoerase.setChecked(settings["erase"])


def setVerifyMode(checked):
    settings["verify"] = checked
    ui.autoverify.setChecked(settings["verify"])


def setConnectionMode(checked):
    settings["connect"] = checked


def configureUI():
    pixmap = QPixmap("28 zif.png")
    pixmap = pixmap.scaled(181, 351)
    ui.flashimg.setPixmap(pixmap)
    ui.selectChip.addItems(chips)
    ui.read.clicked.connect(readToFile)
    ui.update.clicked.connect(updateports)
    ui.write.clicked.connect(writeFromFile)
    ui.conn.clicked.connect(openport)
    ui.open.clicked.connect(openfile)
    ui.erase.clicked.connect(erase)
    ui.actionExit.triggered.connect(exit)
    ui.actionOpen.triggered.connect(openfile)
    ui.actionSave.triggered.connect(saveFile)
    ui.actionAutoerase.triggered.connect(setEraseMode)
    ui.actionAutoconnect.triggered.connect(setConnectionMode)
    ui.autoerase.stateChanged.connect(setEraseMode)
    ui.autoverify.stateChanged.connect(setVerifyMode)
    ui.actionSave_settings.triggered.connect(saveSettings)
    ui.selectChip.currentIndexChanged.connect(updateChip)
    ui.erase.setStyleSheet("color : gray")
    ui.write.setStyleSheet("color : gray")
    ui.read.setStyleSheet("color : gray")
    ui.setWindowTitle(f"Flash&EEPROM programmer")


if __name__ == "__main__":
    ser = serial.Serial()
    configureUI()
    updateports()
    fillRecent()
    loadSettings()
    ui.show()
    app.exec()
