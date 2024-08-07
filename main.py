import sys

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
chips = ["29C256", "28C256", "28C64", "28C16", "27C512"]
chip_conf = {"29C256": "32K", "28C256": "32K", "28C64": "8K", "28C16": "2K", "27C512": "64K,UV"}
recent = []


class Settings:
    def __init__(self):
        self.settings: dict = {}
        self.memSize: int = 0
        self.progConnected: bool = False
        self.readConfig()
        self.chipAttributes: list = []

    def readConfig(self):
        with open("conf.json") as conf:
            self.settings = json.loads(conf.read())
        ui.selectChip.setCurrentText(self.settings["chip"])
        ui.com.setCurrentText(self.settings["uart"])
        ui.actionAutoerase.setChecked(self.settings["erase"])
        ui.actionAutoconnect.setChecked(self.settings["connect"])
        ui.autoerase.setChecked(self.settings["erase"])
        ui.autoverify.setChecked(self.settings["verify"])
        self.drawDummyHex()
        self.getSize()
        self.setAttributes()
        if ui.com.currentText() == self.settings["uart"] and self.settings["connect"]:
            openport()

    def setAttributes(self):
        self.chipAttributes = chip_conf[self.settings["chip"]].split(",")

    def eraseEN(self):
        return 0 if self.settings["erase"] != 2 else 1

    def verifyEN(self):
        return 0 if self.settings["verify"] != 2 else 1

    def getSize(self):
        self.memSize = int(chip_conf[self.settings["chip"]].split("K")[0]) * 1024

    def saveConfig(self):
        self.settings["chip"] = ui.selectChip.currentText()
        with open("conf.json", "w") as conf:
            conf.write(json.dumps(self.settings))

    def setChip(self, chip):
        if chip in chips:
            self.settings["chip"] = chip
            self.getSize()
            self.setAttributes()
        else:
            return 1

    def setEraseMode(self, checked):
        self.settings["erase"] = checked
        ui.actionAutoerase.setChecked(checked)
        ui.autoerase.setChecked(checked)

    def setVerifyMode(self, checked):
        self.settings["verify"] = checked
        ui.autoverify.setChecked(checked)

    def setConnectionMode(self, checked):
        self.settings["connect"] = checked

    def saveSettings(self):
        self.setChip(ui.selectChip.currentText())
        with open("conf.json", "w") as conf:
            conf.write(json.dumps(self.settings))

    def drawDummyHex(self):
        dummy = ' ' * 10 + ' '.join([f'{""}0{hex(i)[2:]}' for i in range(16)]) + '\n'
        for j in range(int(self.memSize / 16) - 1):
            dummy += ('{:0>6}'.format(hex((j + 1) * 16)[2:]) + '    ' + "ff " * 16 + "    " + "ÿ" * 16 + "\n")
        ui.filecontent.setText(dummy)


class File:
    def __init__(self):
        self.fileName: str = ""
        self.content: list = []
        self.fileLength: int = 0
        self.blockLength: int = 0
        self.tempFileContent: str = ""

    def setFile(self, name):
        self.fileName = name
        with open(self.fileName, "rb") as file:
            self.content = ['{:02X}'.format(b).lower() for b in file.read()]
            self.fileLength = len(self.content)
        self.blockLength = self.fileLength // 64
        if self.fileLength % 64:
            self.blockLength += 1
            self.content += ["ff" for i in range(64-self.fileLength % 64)]
        ui.setWindowTitle(f"Flash&EEPROM programmer: {self.fileName}")
        ui.filecontent.setText(drawhex(self.fileName))

    def resetFile(self):
        self.fileName = ""
        self.content.clear()
        self.fileLength = 0
        self.blockLength = 0




file = File()
config = Settings()
# file = File("C:/Users/kroko/Desktop/Projects/Z80/test/test2.hex")


def loadBlock(data):
    print(data)
    request = f"load,{"".join(data)}"
    ser.write(bytes(request, 'utf-8'))
    return ser.readline()


def writeOneBlock(block, data):
    print(f"Writing block {block}...")
    loadBlock(data)

    request = f"write,{block}"
    ser.write(bytes(request, 'utf-8'))
    if config.verifyEN():
        ser.readline()
        read = str(readBlock(block)).replace("b'", "").replace("\\r\\n'", "").lower()
        readArray = read.split("_")
        if data != readArray:
            QMessageBox.critical(ui, "Error", f"Verification error at block {block}.\nWriting terminated.")
            return 1
    else:
        ser.readline()
    return 0


def writeFromFile():
    if file.fileName == "":
        QMessageBox.warning(ui, "Warning", "No opened files")
        return 0

    setActButtonState(erase=False, write=False, read=False)
    if config.eraseEN() and "UV" not in config.chipAttributes:
        erase()

    ui.progressBar.setMaximum(file.blockLength)
    ui.progressBar.setValue(0)
    for block in range(file.blockLength):
        ui.progressBar.setValue(block)
        if writeOneBlock(block, file.content[block*64:(block+1)*64]):
            break
    else:
        print("Done")
        ui.progressBar.setValue(ui.progressBar.maximum())

    setActButtonState(erase=True, write=True, read=True)

    # try:
    #     with open(file, 'rb') as file:
    #         s = file.read()
    #     if settings["erase"] == 2 and "UV" not in chip_conf[ui.selectChip.currentText()]:
    #         erase()
    #     for i in range(len(s)//16):
    #         sect_s = s[i * 16: (i + 1) * 16]  # a = slice(i *16 : (i + 1)*16)
    #         new_s = ""
    #         for j in sect_s:
    #             if len(hex(j)[2:]) == 1 and hex(j)[0].isalpha:
    #                 new_s += f'0{hex(j)[2:]} '
    #             elif len(hex(j)[2:]) == 1:
    #                 new_s += f'{hex(j)[2:]} '
    #             else:
    #                 new_s += f'{hex(j)[2:]} '
    #         new_s += '    '
    #         hex_list = new_s.split()
    #         hex_lst += hex_list
    #     ui.progressBar.setMaximum(int(len(hex_lst)))
    #     ui.progressBar.setValue(int(len(hex_lst)/100))
    #     for i in range(int(len(hex_lst)/64)+1):
    #         j: int = 0
    #         for j in range(64):
    #             if j+64*i >= len(hex_lst):
    #                 print("Done Writing")
    #                 ui.progressBar.setValue(ui.progressBar.maximum())
    #                 return
    #             BUFFER[j] = hex_lst[j+64*i]
    #         writeOneBlock(i, BUFFER)
    #         ui.progressBar.setValue(j+64*i)
    # except ValueError:
    #     return 0
    # except Exception as ex:
    #     QMessageBox.warning(ui, "Warning", "No opened files")
    #     print(f"WriteError: File is not available {ex}")


def updateports():
    portlist = []
    ports = QSerialPortInfo().availablePorts()
    for port in ports:
        portlist.append(port.portName())
    ui.com.clear()
    ui.com.addItems(portlist)


def openport():
    if config.progConnected:
        return 1
    try:
        ser.baudrate = 115200
        ser.port = ui.com.currentText()
        ser.open()
        ui.state.setText(f"Connected on {ser.name}")
        ui.read.setStyleSheet("color : black")
        ui.write.setStyleSheet("color : black")
        ui.read.setEnabled(True)
        ui.write.setEnabled(True)
        config.progConnected = True
        updateChip()
    except Exception as ex:
        print(ex)
        ui.state.setText("Error")


def openfile(fname=False):
    if not fname:
        home_dir = str(Path.home())
        name = QFileDialog.getOpenFileName(ui, 'Open file', home_dir)
        if name[0] == "":
            return 1
        file.setFile(name[0])
    else:
        file.setFile(fname)

    if file.fileName not in recent[-5:]:
        recent.append(file.fileName)
        with open("recent.json", "w") as conf:
            conf.write(json.dumps(recent))
        fillRecent()


def readToFile():
    setActButtonState(erase=False, write=False, read=False)
    file.resetFile()
    ui.setWindowTitle(f"Flash&EEPROM programmer")
    code = ""
    LEN = int(config.memSize/64)
    ui.progressBar.setMaximum(LEN)
    for i in range(0, LEN):
        ui.progressBar.setValue(i+1)
        line = str(readBlock(i)).replace("b'", "").replace("_", "").replace("\\r\\n'", "")
        if line == "1":
            setProgState(0)
            QMessageBox.critical(ui, "Error", "Communication error.\nReading terminated.")
            return 1
        code = code + line

    file.tempFileContent = code
    fp = tempfile.TemporaryFile()
    fp.write(bytes.fromhex(code))
    fp.seek(0)
    ui.filecontent.setText(drawhex(fp, type=0))
    setActButtonState(erase=True, write=True, read=True)
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
        return 1


def saveFile():
    if file.tempFileContent == "":
        QMessageBox.warning(ui, "Warning", f"Nothing to save.")
        return 1
    if file.fileName == "":
        home_dir = str(Path.home())
        name = QFileDialog.getOpenFileName(ui, 'Open file', home_dir)
        if name[0] == "":
            return 1
        file.setFile(name[0])
        openfile(name[0])
    with open(file.fileName, "wb") as f:
        f.write(bytes.fromhex(file.tempFileContent))
    QMessageBox.information(ui, "Saved", f"File saved.")


def updateChip():
    config.setChip(ui.selectChip.currentText())

    if file.fileName == "":
        config.drawDummyHex()

    isUV = not "UV" in config.chipAttributes
    if config.progConnected:
        setActButtonState(erase=isUV)
    ui.autoerase.setEnabled(isUV)
    ui.autoerase.setStyleSheet(f"color : {"black" if isUV else "gray"}")
    ui.actionAutoerase.setEnabled(isUV)


def fillRecent():
    global recent
    ui.menuRecent.clear()
    with open("recent.json") as conf:
        recent = json.loads(conf.read())
    for rec in recent[-5:]:
        act = QAction(rec, ui)
        act.triggered.connect(partial(openfile, rec))
        ui.menuRecent.addAction(act)


def erase():
    ser.write(bytes("erase", 'utf-8'))
    return ser.readline()


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
    ui.actionAutoerase.triggered.connect(config.setEraseMode)
    ui.actionAutoconnect.triggered.connect(config.setConnectionMode)
    ui.autoerase.stateChanged.connect(config.setEraseMode)
    ui.autoverify.stateChanged.connect(config.setVerifyMode)
    ui.actionSave_settings.triggered.connect(config.saveSettings)
    ui.selectChip.currentIndexChanged.connect(updateChip)
    setActButtonState(erase=False, write=False, read=False)
    ui.setWindowTitle(f"Flash&EEPROM programmer")


def setProgState(code):
    # 0 - Error
    match code:
        case 0:
            ui.state.setText(f"Not connected")

    setActButtonState(erase=code, write=code, read=code)
    # ui.read.setStyleSheet(f"color : {"gray" if code else "black"}")
    # ui.write.setStyleSheet(f"color : {"gray" if code else "black"}")
    # ui.erase.setStyleSheet(f"color : {"gray" if code else "black"}")
    # ui.erase.setEnabled(code)
    # ui.read.setEnabled(code)
    # ui.write.setEnabled(code)
    config.progConnected = code


def setActButtonState(**kwargs):
    if kwargs.get("read") is not None:
        ui.read.setStyleSheet(f"color : {"black" if kwargs.get("read") else "gray"}")
        ui.read.setEnabled(kwargs.get("read"))
    if kwargs.get("write") is not None:
        ui.write.setStyleSheet(f"color : {"black" if kwargs.get("write") else "gray"}")
        ui.write.setEnabled(kwargs.get("write"))
    if kwargs.get("erase") is not None:
        ui.erase.setStyleSheet(f"color : {"black" if kwargs.get("erase") else "gray"}")
        ui.erase.setEnabled(kwargs.get("erase"))




if __name__ == "__main__":
    ser = serial.Serial()
    updateports()
    fillRecent()
    configureUI()
    config.readConfig()

    ui.show()
    sys.exit(app.exec())
