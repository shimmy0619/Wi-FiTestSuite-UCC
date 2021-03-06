###################################################################
#
# Copyright (c) 2014 Wi-Fi Alliance
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE
# USE OR PERFORMANCE OF THIS SOFTWARE.
#
###################################################################

from socket import *
from time import gmtime, strftime
import thread, time, Queue, os
import sys, time
from select import select
import logging
import re
import ctypes
import HTML
from xml.dom.minidom import Document
from XMLLogger import XMLLogger

VERSION = "4.2.0"


conntable = {}
retValueTable = {}
DisplayNameTable = {}
streamSendResultArray = []
streamRecvResultArray = []
streamInfoArray = []
runningPhase = '1'
testRunning = 0
threadCount = 0
resultPrinted = 0
ifcondBit = 1
iDNB = 0
iINV = 0
RTPCount = 1
#default command file path
uccPath = '..\\..\\cmds'
DUTFeatureInfoFile = "./log/DUTFeatureInfo.html"


STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12

FOREGROUND_BLUE = 0x01 # text color contains blue.
FOREGROUND_GREEN = 0x02 # text color contains green.
FOREGROUND_RED = 0x04 # text color contains red.
FOREGROUND_INTENSITY = 0x08 # text color is intensified.

#Define extra colours
FOREGROUND_WHITE = FOREGROUND_RED | FOREGROUND_BLUE | FOREGROUND_GREEN
FOREGROUND_YELLOW = FOREGROUND_RED | FOREGROUND_GREEN
FOREGROUND_CYAN = FOREGROUND_BLUE | FOREGROUND_GREEN
FOREGROUND_MAGENTA = FOREGROUND_RED | FOREGROUND_BLUE


BACKGROUND_BLUE = 0x10 # background color contains blue.
BACKGROUND_GREEN = 0x20 # background color contains green.
BACKGROUND_RED = 0x40 # background color contains red.
BACKGROUND_INTENSITY = 0x80 # background color is intensified.


std_out_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

cSLog = ""
class classifiedLogs:
    """Global Handler for classified Logs"""
    def __init__(self, name, fileName, msg=""):
        self.name = name
        self.fileD = open(fileName, 'a')
        self.msg = msg
        self.fileD.write("%s\n" % msg)
        #time.strftime("%H-%M-%S_%b-%d-%y", time.localtime())

    def log(self, msg):
        """Print out time and message into file"""
        self.fileD.write("%s | %s \n" %(time.strftime("%b:%d:%Y-%H:%M:%S",
                                                      time.localtime()), msg))
    def __str__(self):
        return "%s:%s" %(self.fileName, self.msg)
    def __del__(self):
        self.fileD.close()


class streamInfo:
    """Returns string in formatted stream info"""
    def __init__(self, streamID, IPAddress, pairID, direction,
                 trafficClass, frameRate, phase, RTPID):
        self.streamID = streamID
        self.IPAddress = IPAddress
        self.pairID = pairID
        self.direction = direction
        self.trafficClass = trafficClass
        self.frameRate = frameRate
        self.phase = phase
        self.status = -1
        self.RTPID = RTPID

    def __str__(self):
        return "%-10s Stream ID = %s , IP Address = %s \n\r%-10s pairID = %s direction = %s \n\r%-10s frameRate =%s \n\r%-10s status =%s  %s" % (' ', self.streamID, self.IPAddress, ' ', self.pairID, self.direction, ' ', self.frameRate, ' ', self.status, self.phase)


class streamResult:
    """Returns string in formatted stream result"""
    def __init__(self, streamID, IPAddress, rxFrames, txFrames, rxBytes,
                 txBytes, phase):
        self.streamID = streamID
        self.IPAddress = IPAddress
        self.rxFrames = rxFrames
        self.txFrames = txFrames
        self.rxBytes = rxBytes
        self.txBytes = txBytes
        self.phase = phase
        #print 'self = %s streamID =%s' % (self,streamID)
    def __str__(self):
        return "%-10s RX   %10s  Bytes   |  TX  %10s   | Stream ID = %s" % (' ', self.rxBytes, self.txBytes, self.streamID)

# socket desc list to be used by select
waitsocks, readsocks, writesocks = [], [], []

#Multicast test
multicast = 0


def set_color(color, handle=std_out_handle):
    """(color) -> BOOL

    Example: set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
    """
    bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)
    return bool

def setUCCPath(path):
    """Set absolute path of cmds or script location"""
    global uccPath
    uccPath = path
    return

def scanner(fileobject, linehandler):
    """Scan file objects"""
    for line in fileobject.readlines():
        if not line: break
        linehandler(line)

def sock_tcp_conn(ipaddr, ipport):
    """function for client socket connection set to blocking mode"""
    global readsocks, waitsocks, deftimeout
    buf = 2048
    addr = (ipaddr, ipport)

    mysock = socket(AF_INET, SOCK_STREAM)
    try:
        mysock.connect(addr)
    except:
        exc_info = sys.exc_info()
        logging.error('Connection Error, IP = %s PORT = %s REASON = %s',
                      ipaddr, ipport, exc_info[1])
        wfa_sys_exit("IP-%s:%s REASON = %s" % (ipaddr, ipport, exc_info[1]))

    readsocks.append(mysock)
    # Add the descriptor to select wait
    waitsocks.append(mysock)
    return mysock

def process_ipadd(line):
    """function to parse IP address and port number. Create socket connection if not already."""
    global conntable
    i = 0
    addrlist = []
    addrlist = line.split(':')
    naddr = len(addrlist)
    while i < naddr:
        ip = addrlist[i].split(',', 1)
        ipa = ip[0].split('=')[1]    # ip adress
        ipp = ip[1].split('=')[1]    # ip port
        logging.info('Connecting to - IP Addr = %s Port = %s', ipa, ipp)

        sockhdlr = sock_tcp_conn(ipa, int(ipp))
        conntable["%s:%s" %(ipa, ipp)] = sockhdlr
        i = i+1
def close_conn():
    global conntable

def printStreamResults():
    """Determines if WMM or WPA2 before printing results"""
    global resultPrinted
    ProgName = os.getenv("PROG_NAME")
    if resultPrinted == 1:
        return

    XLogger.setTestResult("COMPLETED")
    if ProgName == "P2P":
        return
    if "WPA2Test" in retValueTable:
        logging.debug("WPA2 Results")
        printStreamResults_WPA2()
    else:
        printStreamResults_WMM()

def printStreamResults_WPA2():
    """Prints stream results of WPA2"""
    global resultPrinted
    maxRTP = 1
    set_color(FOREGROUND_WHITE)
    if not streamSendResultArray:
        resultPrinted = 0
    else:
        resultPrinted = 1
    logging.info("\n\r %-7s --------------------STREAM RESULTS-----------------------" % "")
    for s in streamSendResultArray:
        sDisplayAddress = s.IPAddress
        if s.IPAddress in DisplayNameTable:
            sDisplayAddress = DisplayNameTable[s.IPAddress]
        for r in streamInfoArray:
            if r.streamID == s.streamID and r.IPAddress == s.IPAddress and r.phase == s.phase:
                recv_id = r.pairID
                trafficClass = r.trafficClass
                phase = r.phase
                break
        for p in streamRecvResultArray:
            pDisplayAddress = p.IPAddress
            if p.IPAddress in DisplayNameTable:
                pDisplayAddress = DisplayNameTable[p.IPAddress]
            if p.streamID == recv_id and p.phase == s.phase:
                logging.info("\n\r %-7s -----  %s --> %s -----" %
                             ("", sDisplayAddress, pDisplayAddress))
                logging.info("\n%s" % s)
                if maxRTP < int(r.RTPID):
                    maxRTP = int(r.RTPID)
                logging.info("\n%s" % p)
                break
    set_color(FOREGROUND_WHITE)

def printStreamResults_WMM():
    """Prints stream results of WMM"""
    global resultPrinted
    summaryList = {}
    summaryStreamDisplay = {}
    maxRTP = 1
    i = 1
    if not streamSendResultArray:
        resultPrinted = 0
    else:
        resultPrinted = 1
    logging.info("\n\r %-7s --------------------STREAM RESULTS-----------------------" % "")
    for s in streamSendResultArray:
        sDisplayAddress = s.IPAddress
        if s.IPAddress in DisplayNameTable:
            sDisplayAddress = DisplayNameTable[s.IPAddress]
        for r in streamInfoArray:
            if r.streamID == s.streamID and r.IPAddress == s.IPAddress and r.phase == s.phase:
                recv_id = r.pairID
                trafficClass = r.trafficClass
                phase = r.phase
                break
        for p in streamRecvResultArray:
            pDisplayAddress = p.IPAddress
            if p.IPAddress in DisplayNameTable:
                pDisplayAddress = DisplayNameTable[p.IPAddress]
            if p.streamID == recv_id and p.phase == s.phase:
                logging.info("\n\r %-7s ----- RTP_%s-%s ( %s --> %s ) PHASE  = %s -----" %("", r.RTPID, trafficClass, sDisplayAddress, pDisplayAddress, phase))
                logging.info("\n%s" % s)
                summaryList.setdefault("%s:%s"%(int(r.RTPID), int(phase)), p.rxBytes)
                summaryStreamDisplay.setdefault("%s:%s" % (int(r.RTPID), int(phase)), "RTP%-1s_%-10s [%s-->%s]" % (r.RTPID, trafficClass, sDisplayAddress, pDisplayAddress))
                if maxRTP < int(r.RTPID):
                    maxRTP = int(r.RTPID)
                logging.info("\n%s" % p)
                break
    set_color(FOREGROUND_WHITE)
    logging.info("--------------------------SUMMARY----------------------------------")
    logging.info(" %46s %10s | %10s" % ("|", "Phase1 (Bytes)", "Phase2 (Bytes)"))
    logging.info("-------------------------------------------------------------------")
    while i <= maxRTP:
        str1 = ""
        str2 = ""
        stremDisplay = ""
        if "%s:%s"%(i, "1") in summaryList:
            str1 = summaryList["%s:%s" % (i, "1")]
            stremDisplay = summaryStreamDisplay["%s:%s"%(i, "1")]
        if "%s:%s"%(i, "2") in summaryList:
            str2 = summaryList["%s:%s" % (i, "2")]
            stremDisplay = summaryStreamDisplay["%s:%s"%(i, "2")]

        logging.info("\n%6s %-43s %5s %10s | %10s" % (" ", stremDisplay, "|", str1, str2))
        i = i + 1
    set_color(FOREGROUND_INTENSITY)

def responseWaitThreadFunc(_threadID, command, addr, receiverStream):
    global waitsocks, readsocks, writesocks, runningPhase, testRunning, streamInfoArray

    logging.debug("responseWaitThreadFunc started %s" % testRunning)
    while testRunning > 0:
        readables, writeables, exceptions = select(readsocks, writesocks, [], 0.1)
        for sockobj in readables:
            if sockobj in waitsocks:
                resp = sockobj.recv(2048)
                resp_arr = resp.split(',')
                for socks in conntable:
                    if sockobj == conntable[socks]:
                        responseIPAddress = socks
                displayaddr = responseIPAddress
                if responseIPAddress in DisplayNameTable:
                    displayaddr = DisplayNameTable[responseIPAddress]
                logging.info("%-15s <--1 %s" % (displayaddr, resp))
                # Check for send stream completion
                if len(resp_arr) > 2:
                    if resp_arr[3] == '':
                        logging.error("NULL streamID returned from %s" % responseIPAddress)
                        continue
                    if resp_arr[2] == 'streamID':
                        logging.debug("STREAM COMPLETED = %s" % (resp_arr[3]))

                        # spliting the values of multiple streams
                        idx = resp_arr[3].strip()
                        idx = idx.split(' ')
                        sCounter = 0 # For multiple stream value returns
                        if resp_arr[7].split(' ')[sCounter] == '':
                            sCounter = 1

                        for i in idx:
                            txFrames = resp_arr[5].split(' ')[sCounter]
                            logging.debug(" TXFRAMES = %s" % txFrames)
                            i = ("%s;%s"%(i, responseIPAddress))
                            if txFrames != '0':
                                logging.info("%s (%-15s) <--  SEND Stream - %s Completed " % (displayaddr, responseIPAddress, i))

                                # Setting status complete
                                for p in streamInfoArray:
                                    if p.IPAddress == responseIPAddress and p.streamID == i and p.phase == runningPhase:
                                        p.status = 1
                                streamSendResultArray.append(streamResult(i, responseIPAddress, resp_arr[7].split(' ')[sCounter], resp_arr[5].split(' ')[sCounter], resp_arr[11].split(' ')[sCounter], resp_arr[9].split(' ')[sCounter], runningPhase))

                            else:
                                streamRecvResultArray.append(streamResult(i, responseIPAddress, resp_arr[7].split(' ')[sCounter], resp_arr[5].split(' ')[sCounter], resp_arr[11].split(' ')[sCounter], resp_arr[9].split(' ')[sCounter], runningPhase))
                                logging.info("%s (%-15s) <----  RECV Stream - %s Completed " % (displayaddr, responseIPAddress, i))

                            sCounter += 1

            else:
                logging.debug('Unwanted data on socket')
    logging.debug("\n THREAD STOPPED ")
    return
def process_cmd(line):
    """
    Process CAPI commands and send through socket if necessary

    Parameters
    ----------
    line : str
        CAPI command followed by parameters with "," as delimiter

    Returns
    -------
    none

    Examples
    --------
	process_cmd(ca_get_version)
    process_cmd(sniffer_control_filter_capture,infile,_521-step1,
        outfile,521-step1_A,srcmac,00:11:22:33:44:55,
        destmac,55:44:33:22:11:00)
    """
    global conntable, threadCount, waitsocks_par, runningPhase, testRunning, streamInfoArray, resultPrinted
    global retValueTable, RTPCount, multicast, ifcondBit, iDNB, iINV, ifCondBit, socktimeout
    line = line.rstrip()
    str = line.split('#')
    recv_id = {}

    try:
        if str[0] == '':
            return
        command = str[0].split('!')

        if command[0].lower() == "else":
            if int(ifCondBit):
                ifCondBit = 0
            else:
                ifCondBit = 1
            return
        if command[0].lower() == "endif":
            ifCondBit = 1
            return
        if command[0].lower() == "if":
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            if command[3] in retValueTable:
                command[3] = retValueTable[command[3]]
            if(command[2]).lower() == "=":
                if (command[1]).lower() == (command[3]).lower():
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            elif (command[2]).lower() == ">":
                if long(command[1]) > long(command[3]):
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            elif (command[2]).lower() == "<":
                if long(command[1]) < long(command[3]):
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            elif (command[2]).lower() == ">=":
                if long(command[1]) >= long(command[3]):
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            elif (command[2]).lower() == "<=":
                if long(command[1]) <= long(command[3]):
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            elif (command[2]).lower() == "<>":
                if (command[1]).lower() != (command[3]).lower():
                    ifcondBit = 1
                else:
                    ifcondBit = 0
            return

        if int(ifcondBit) == 0:
            return
        if command[0].lower() == "_dnb_":
            iDNB = 1
            return
        if command[0].lower() == "_inv":
            iINV = 1
            return
        if command[0].lower() == "inv_":
            iINV = 0
            return
        if command[0].lower() == "mexpr":
            if command[1] not in retValueTable:
                return
            if command[3] in retValueTable:
                command[3] = retValueTable[command[3]]
            if command[2] == "%":
                retValueTable[command[1]] = (int(retValueTable[command[1]]) * int(command[3])) / 100

            return
        if command[0].lower() == "extract_p2p_ssid":
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            p2p_ssid = command[1].split(' ')
            if len(p2p_ssid) > 1:
                retValueTable.setdefault("$P2P_SSID", "%s" % p2p_ssid[1])
            else:
                logging.error("Invalid P2P Group ID")
            return
        if command[0].lower() == "calculate_ext_listen_values":
            if command[1] not in retValueTable or command[2] not in retValueTable:
                wfa_sys_exit("%s or %s not available" % (command[1], command[2]))
                command[1] = retValueTable[command[1]]
                command[2] = retValueTable[command[2]]
                retValueTable.setdefault("$PROBE_REQ_INTERVAL", "%s" % (int(command[2]) / 2))
                retValueTable.setdefault("$PROBE_REQ_COUNT", "%s" % (int(command[1]) / (int(command[2]) / 2)))
                return
        if command[0].lower() == "get_rnd_ip_address":
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            if command[2] in retValueTable:
                command[2] = retValueTable[command[2]]
            ip1 = command[1].split(".")
            ip2 = command[2].split(".")
            if (int(ip2[3]) + 1) != int(ip1[3]):
                rnd_ip = ("%s.%s.%s.%s" % (ip2[0], ip2[1], ip2[2], int(ip2[3]) + 1))
            else:
                rnd_ip = ("%s.%s.%s.%s" % (ip2[0], ip2[1], ip2[2], int(ip2[3]) + 2))
            retValueTable.setdefault(command[3], "%s" % rnd_ip)
            return

        if command[0].lower() == 'ucc_form_device_discovery_frame':
            iCn = 0
            for c in command:
                if iCn > 1 and c in command:
                    wfa_sys_exit("Invalid UCC command")
                    #command[1] Frame command[2] GOUT Device Address command[3] group ID command[4] Injector source Address command[5] Testbed Client address

            f = command[1].split('*')
            iCn = 0

            #Hex SSID
            SSID = retValueTable[command[3]].split(" ")[1]
            SSIDLength = len(SSID)
            SSIDLen1 = hex(int(SSIDLength) + 22).split("0x")[1]
            SSIDLen2 = "%s 00" % hex(int(SSIDLength + 6)).split("0x")[1]
            if int(len(SSIDLen2)) < 5:
                SSIDLen2 = "0%s" % SSIDLen2
            hexSSID = ""
            for s in SSID:
                h = hex(ord(s)).split("0x")[1]
                hexSSID = hexSSID + h
            logging.debug("hexSSID = %s hexLength %s" % (hexSSID, SSIDLength))
            FrameData = "%s%s%s%s%s%s%s%s%s%s%s%s" % (f[0],
                                                      retValueTable[command[2]],
                                                      retValueTable[command[4]],
                                                      retValueTable[command[2]],
                                                      f[3],
                                                      SSIDLen1,
                                                      f[4],
                                                      retValueTable[command[5]],
                                                      f[5],
                                                      SSIDLen2,
                                                      retValueTable[command[2]],
                                                      hexSSID)
            logging.debug(FrameData)
            retValueTable.setdefault("$INJECT_FRAME_DATA", FrameData)

        if command[0].lower() == 'addstaversioninfo':

            vInfo = command[1].split(",")
            i = 0

            if len(vInfo) < 5:
                logging.info("Incorrect version format")
                return

            if vInfo[0] not in retValueTable:
                logging.debug("Unknown Component[1] %s", vInfo[0])
                return

            if retValueTable[vInfo[0]] not in conntable:
                if retValueTable[retValueTable[vInfo[0]]] not in conntable:
                    logging.debug("Unknown Component[3] %s", vInfo[0])
                    return

            #print vInfo
            print len(retValueTable)
            for c in vInfo:
                if c in retValueTable:
                    vInfo[i] = retValueTable[c]
                if vInfo[i] in DisplayNameTable:
                    vInfo[i] = DisplayNameTable[vInfo[i]]
                i = i + 1
            XLogger.AddTestbedDevice(vInfo[1], vInfo[2], vInfo[3], vInfo[4])
            logging.debug(vInfo)
            return

        if command[0].lower() == 'adduccscriptversion':
            XLogger.AddWTSComponent("UCC", VERSION, command[1])

        if command[0].lower() == 'addwtscompversioninfo' or command[0].lower() == 'adddutversioninfo':

            vInfo = command[1].split(",")
            i = 0

            if len(vInfo) < 5:
                logging.info("Incorrect version format...")
                return

            if vInfo[0] in retValueTable:
                vInfo[0] = retValueTable[vInfo[0]]

            #print vInfo
            print len(retValueTable)
            for c in vInfo:
                if c in retValueTable:
                    vInfo[i] = retValueTable[c]
                if vInfo[i] in DisplayNameTable:
                    vInfo[i] = DisplayNameTable[vInfo[i]]
                i = i + 1

            if command[0].lower() == 'adddutversioninfo':
                XLogger.AddDUTInfo(vInfo[1], vInfo[2], vInfo[3], vInfo[4])
                logging.debug("DUT INFO [%s][%s][%s][%s]" % (vInfo[1], vInfo[2], vInfo[3], vInfo[4]))
            else:
                logging.debug("WTS Comp[%s][%s][%s][%s]" % (vInfo[1], vInfo[2], vInfo[3], vInfo[4]))
                XLogger.AddWTSComponent(vInfo[0], vInfo[1], "%s:%s:%s" % (vInfo[2], vInfo[3], vInfo[4]))

            logging.debug(vInfo)
            return

        if re.search("STA", command[0]):
            if command[0] in retValueTable:
                command[0] = retValueTable[command[0]]
            else:
                return

        if command[0].lower() == 'exit':
            set_color(FOREGROUND_CYAN | FOREGROUND_INTENSITY)
            wfa_sys_exit("Exiting - %s" % command[1])

        if command[0].lower() == 'pause':
            set_color(FOREGROUND_YELLOW | FOREGROUND_INTENSITY)
            logging.info("Exeuction Paused - %s \n Press any key to continue..." % command[1])
            sys.stdin.read(1)
            set_color(FOREGROUND_INTENSITY)
            return

        if command[0].lower() == 'sleep':
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            time.sleep(float(command[1]))
            return
        if command[0].lower() == 'userinput':
            set_color(FOREGROUND_YELLOW | FOREGROUND_INTENSITY)
            logging.info("[USER INPUT REQUIRED]")
            udata = raw_input(command[1])
            if command[2] in retValueTable:
                retValueTable[command[2]] = udata
            else:
                retValueTable.setdefault(command[2], udata)

            set_color(FOREGROUND_INTENSITY)
            return
        if command[0].lower() == 'userinput_ifnowts':

            if retValueTable["$WTS_ControlAgent_Support"] == "0":
                set_color(FOREGROUND_YELLOW | FOREGROUND_INTENSITY)
                logging.info("[USER INPUT REQUIRED]")
                udata = raw_input(command[1])
                if command[2] in retValueTable:
                    retValueTable[command[2]] = udata
                else:
                    retValueTable.setdefault(command[2], udata)

                set_color(FOREGROUND_INTENSITY)
            return

        if command[0].lower() == 'ifnowts':

            if retValueTable["$WTS_ControlAgent_Support"] == "0":
                set_color(FOREGROUND_YELLOW | FOREGROUND_INTENSITY)
                if len(command) > 3 and command[2] in retValueTable:
                    s = "- %s" % retValueTable[command[2]]
                else:
                    s = ""
                logging.info("%s %s\n        Press any key to continue after done" % (command[1], s))

                sys.stdin.read(1)
                set_color(FOREGROUND_INTENSITY)

            return

        if command[0] == 'wfa_control_agent' or command[0] == 'wfa_control_agent_dut':
            if retValueTable["$WTS_ControlAgent_Support"] == "0":
                return

        if command[0].lower() == 'getuccsystemtime':
            timeStr = time.strftime("%H-%M-%S-%m-%d-%Y", time.localtime())
            logging.debug("\n Reading UCC System time %s" % timeStr)
            t = timeStr.split("-")
            retValueTable.setdefault("$month", t[3])
            retValueTable.setdefault("$date", t[4])
            retValueTable.setdefault("$year", t[5])
            retValueTable.setdefault("$hours", t[0])
            retValueTable.setdefault("$minutes", t[1])
            retValueTable.setdefault("$seconds", t[2])
            logging.debug("""\n UCC System Time -
                          Month:%s:
                          Date:%s:
                          Year:%s:
                          Hours:%s:
                          Minutes:%s:
                          Seconds:%s:""" %
                          (retValueTable["$month"],
                           retValueTable["$date"],
                           retValueTable["$year"],
                           retValueTable["$hours"],
                           retValueTable["$minutes"],
                           retValueTable["$seconds"]))
            return

        if command[0].lower() == 'r_info':
            rdata = "-"
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            if len(command) > 1:
                rdata = command[2]
            resultPrinted = 1
            set_test_result(command[1], rdata, "-")
            XLogger.setTestResult(command[1], rdata)
            wfa_sys_exit_0()
            return

        if command[0].lower() == 'info':
            set_color(FOREGROUND_CYAN | FOREGROUND_INTENSITY)
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            logging.info("\n %7s ~~~~~ %s ~~~~~ \n" %("", command[1]))
            set_color(FOREGROUND_INTENSITY)
            return

        if re.search('esultIBSS', command[0]):
            time.sleep(5)
            printStreamResults()
            process_passFailIBSS(command[1])
            return

        elif re.search('define', command[0]):
            logging.debug("..Define %s = %s"%(command[1], command[2]))
            if command[1] in retValueTable:
                if command[2] in retValueTable:
                    command[2] = retValueTable[command[2]]
                retValueTable[command[1]] = command[2]
            else:
                if command[2] in retValueTable:
                    command[2] = retValueTable[command[2]]
                retValueTable.setdefault(command[1], command[2])

            return

        elif command[0].lower() == 'echo':
            if command[1] in  retValueTable:
                logging.info("%s=%s" % (command[1], retValueTable[command[1]]))
            else:
                logging.info("Unknown variable %s" %command[1])
            return
        elif command[0].lower() == 'echo_ifnowts' and retValueTable["$WTS_ControlAgent_Support"] == "0":
            if command[1] in  retValueTable:
                logging.info("-%s=%s-" % (command[1], retValueTable[command[1]]))
            else:
                logging.info("%s" % command[1])
            return

        elif command[0].lower() == 'storethroughput':
            cmd = command[2].split(",")
            logging.debug("Storing the Throughput(Mbps) value of stream %s[%s %s] in %s  duration=%s p=%s", cmd[0], cmd[3], "%", command[1], retValueTable[cmd[2]], cmd[1])
            P1 = -1
            for p in streamRecvResultArray:
                if p.streamID == retValueTable[cmd[0]] and int(p.phase) == int(cmd[1]):
                    P1 = p.rxBytes
                    P1 = int(int(P1) / 100) * int(cmd[3])
                    P1 = ((float(P1) * 8))/(1000000 * int(retValueTable[cmd[2]]))
                    break
            logging.info("Storing %s = %s [Mbps]", command[1], P1)
            if command[1] in retValueTable:
                retValueTable[command[1]] = P1
            else:
                retValueTable.setdefault(command[1], P1)
            return

        elif command[0].lower() == 'resultwmm':
            time.sleep(5)
            printStreamResults()
            process_passFailWMM(command[1])
            return
        elif command[0].lower() == 'resultwmm_1':
            time.sleep(5)
            printStreamResults()
            process_passFailWMM_1(command[1])
            return
        elif re.search('CheckThroughput', command[0]):
            time.sleep(5)
            printStreamResults()
            process_CheckThroughput(command[1], 0)
            return
        elif re.search('CheckMCSThroughput', command[0]):
            time.sleep(5)
            printStreamResults()
            process_CheckMCSThroughput(command[1])
            return
        elif re.search('CheckDT4Result', command[0]):
            time.sleep(5)
            printStreamResults()
            process_CheckDT4(command[1])
            return
        elif re.search('TransactionThroughput', command[0]):
            time.sleep(5)
            printStreamResults()
            process_CheckThroughput(command[1], 1)
            return
        elif re.search('esultCheck', command[0]):
            time.sleep(5)
            process_ResultCheck(command[1])
            return

        logging.debug("COMMAND - to %s" % command[0])
        if command[0] == 'wfa_test_commands':
            if command[1] in retValueTable:
                command[1] = retValueTable[command[1]]
            process_cmdfile("%s%s"%(uccPath, command[1]))
            return
        if command[0] == 'Phase':
            RTPCount = 1
            time.sleep(3)
            logging.debug("Starting Phase - %s ..." % command[1])
            runningPhase = command[1]
            threadCount = 0
            testRunning = 0
            time.sleep(2)
            return
        if len(command) < 3:
            logging.error('Incorrect format of line - %s', line)
            return

        ret_data_def = command[2]
        ret_data_def_type = ret_data_def.split(',')
        logging.debug("Command Return Type = %s" % (ret_data_def_type[0].lower()))
        if ret_data_def_type[0] == 'STREAMID' or ret_data_def_type[0] == 'INTERFACEID' or ret_data_def_type[0] == 'PING':
            ret_data_idx = ret_data_def_type[1]
        elif ret_data_def_type[0] == 'RECV_ID':
            recv_value = ret_data_def_type[1].split(' ')
            i = 0
            for r in recv_value:
                recv_id[i] = r
                i += 1
            logging.debug('RECV ID %s', recv_id)

        elif ret_data_def_type[0] == 'FILENAME':
            upload_file_desc = open(ret_data_def_type[1], 'a')
            logging.info('File desc=  %s', upload_file_desc)
            logging.info('Uploading to file -  %s', ret_data_def_type[1])

        if command[0] in retValueTable:
            toaddr = retValueTable[command[0]]
        else:
            return

        displayName = toaddr
        if toaddr in DisplayNameTable:
            displayName = DisplayNameTable[toaddr]

        capi_run = command[1].strip()
        capi_elem = command[1].split(',')
        logging.debug("%s (%-15s) --> %s " % (displayName, toaddr, capi_elem))

        if capi_elem[0] == 'traffic_agent_receive_stop':
            idx = capi_elem.index('streamID')
            # Wait for Send to finish, in case of receive_stop
            sid = capi_elem[2].split(' ')
            capi_elem[idx+1] = ''
            for i in sid:
                val = retValueTable[i]
                if re.search(";", retValueTable[i]):
                    val = retValueTable[i].split(";")[0]

                for p in streamInfoArray:
                    if p.pairID == retValueTable[i] and p.phase == runningPhase:
                        while p.status != 1:
                            #Minor sleep to avoid 100% CPU Usage by rapid while
                            time.sleep(0.1)

                        if multicast == 1:
                            capi_elem[idx+1] = val
                            break
                        else:
                            capi_elem[idx+1] += val
                            capi_elem[idx+1] += ' '
                            break

                    elif multicast == 1:
                        capi_elem[idx+1] = val

            capi_run = ','.join(capi_elem)
            capi_cmd = capi_run + ' \r\n'
            logging.info("%s (%-10s) --> %s" % (displayName, toaddr, capi_cmd))
            asock = conntable.get(toaddr)
            asock.send(capi_cmd)
            time.sleep(15)
            return

        elif capi_elem[0] == 'traffic_agent_send':
            idx = capi_elem.index('streamID')
            sid = capi_elem[2].split(' ')
            capi_elem[idx+1] = ''
            rCounter = 0
            for i in sid:
                #Making Send-receive Pair
                for s in streamInfoArray:
                    if s.IPAddress == toaddr and s.streamID == retValueTable[i] and s.phase == runningPhase:
                        s.pairID = retValueTable[recv_id[rCounter]]
                if re.search(";", retValueTable[i]):
                    val = retValueTable[i].split(";")[0]
                else:
                    val = retValueTable[i]
                capi_elem[idx+1] += val
                capi_elem[idx+1] += ' '
                rCounter += 1

            capi_run = ','.join(capi_elem)
            logging.info("%s (%-15s) --> %s " %(displayName, toaddr, capi_run))

            # Pass the receiver ID for send stream

            # Start the response wait thread (only once)
            if threadCount == 0:
                testRunning = 1
                thread.start_new(responseWaitThreadFunc, (threadCount, capi_run, toaddr, recv_id))
                threadCount = threadCount + 1
				#Temporary Addition for VHT
            capi_cmd = capi_run + ' \r\n'
            asock = conntable.get(toaddr)
            asock.send(capi_cmd)
            return

        else:
            if capi_elem[0] == 'sniffer_control_stop':
                time.sleep(2)
                testRunning = 0
                time.sleep(2)

            #Replacing the placeholder(s) in command.
            for id in retValueTable:
                elementCounter = 0
                for capiElem in capi_elem:

                    if capiElem == id:
                        if re.search(";", retValueTable[id]):
                            val = retValueTable[id].split(";")[0]
                        else:
                            val = retValueTable[id]
                        capi_elem[elementCounter] = val
                        logging.debug("Replacing the placeholder %s %s" % (id, capi_elem[elementCounter]))
                    elementCounter += 1

        if capi_elem[0] == 'sta_up_load':
            seq_no = 1
            code_no = 1
            while code_no != '0':
                capi_elem[3] = "%s" % seq_no
                seq_no += 1
                status = send_capi_command(toaddr, capi_elem)
                ss = status.rstrip('\r\n')
                logging.debug("%s (%s) <--- %s" % (displayName, toaddr, ss))
                stitems = ss.split(',')
                if  stitems[1] == "COMPLETE"  and len(stitems) > 3:
                    upload_file_desc.write(stitems[4])
                    code_no = stitems[3]

            upload_file_desc.close()
            return
        else:
            if capi_elem[0] == 'sta_is_connected':
                isConnectRetry = 0
                while isConnectRetry < 10:
                    isConnectRetry = isConnectRetry + 1
                    time.sleep(4)
                    status = send_capi_command(toaddr, capi_elem)
                    ss = status.rstrip('\r\n')
                    logging.info("%s (%-15s) <-- %s" % (displayName, toaddr, ss))
                    stitems = ss.split(',')
                    if  stitems[1] == "COMPLETE"  and len(stitems) > 3:
                        retValueTable.setdefault("$IS_CONNECTED", stitems[3])
                        if "PingInternalChk" in retValueTable:
                            if retValueTable["PingInternalChk"] == "0":
                                logging.debug("Skipping IS_CONNECTE check")
                                return
                            elif stitems[3] == '1':
                                return
                            else:
                                continue
                        else:
                            if stitems[3] == '1':
                                return
                            else:
                                continue
                wfa_sys_exit("\n NO ASSOCIATION -- Aborting the test")
            else:
                status = send_capi_command(toaddr, capi_elem)

        ss = status.rstrip('\r\n')
        logging.info("%s (%-15s) <-- %s" % (displayName, toaddr, ss))
        #Exit in case of ERROR
        if re.search('ERROR', ss) or re.search('INVALID', ss) and iDNB == 0 and iINV == 0:
            set_test_result("ERROR", "-", "Command returned Error")
            wfa_sys_exit(" Command returned Error. Aborting the test")

        stitems = ss.split(',')
        if  stitems[1] == "COMPLETE"  and len(stitems) > 3:
            if stitems[2] == 'streamID':

                if capi_elem[4] == 'send':
                    streamInfoArray.append(streamInfo("%s;%s" %(stitems[3], toaddr), toaddr, -1, 'send', capi_elem[16], capi_elem[18], runningPhase, RTPCount))
                    RTPCount = RTPCount+1
                else:
                    streamInfoArray.append(streamInfo("%s;%s" %(stitems[3], toaddr), toaddr, -1, 'receive', -1, -1, runningPhase, -1))
                if capi_elem[2] == 'Multicast':
                    logging.debug("----MULTICAST----")
                    multicast = 1
                if ret_data_idx in retValueTable:
                    retValueTable[ret_data_idx] = ("%s;%s" %(stitems[3], toaddr))
                else:
                    retValueTable.setdefault(ret_data_idx, "%s;%s" %(stitems[3], toaddr))
            elif stitems[2] == 'interfaceType':
                retValueTable.setdefault(ret_data_idx, stitems[5])
            elif stitems[2].lower() == 'interfaceid':
                if ret_data_idx in retValueTable:
                    retValueTable[ret_data_idx] = stitems[3].split('_')[0]
                else:
                    retValueTable.setdefault(ret_data_idx, stitems[3].split('_')[0])
            elif capi_elem[0] == 'traffic_stop_ping':
                retValueTable["%s;%s"%(capi_elem[2], toaddr)] = stitems[5]
                logging.debug("%s = %s" %  (capi_elem[2], retValueTable["%s;%s"%(capi_elem[2], toaddr)]))
                if "PingInternalChk" in retValueTable:
                    if retValueTable["PingInternalChk"] == "0":
                        logging.debug("Ping Internal Check")
                    elif stitems[5] == '0':
                        wfa_sys_exit("\n NO IP Connection -- Aborting the test")
                else:
                    if stitems[5] == '0':
                        wfa_sys_exit("\n NO IP Connection -- Aborting the test")
            if ret_data_def_type[0].lower() == "id":
                i = 0

                for s in stitems:
                    if(int(i)%2 == 0) and len(stitems) > i+1:
                        logging.debug("--------> Adding %s = %s"%(ret_data_def_type[i/2], stitems[i+1]))
                        stitems[i+1] = stitems[i+1].rstrip(' ')
                        stitems[i+1] = stitems[i+1].rstrip('\n')
                        stitems[i+1] = stitems[i+1].rstrip('\r')
                        if ret_data_def_type[i/2] in retValueTable:
                            retValueTable[ret_data_def_type[i/2]] = stitems[i+1]
                        else:
                            retValueTable.setdefault(ret_data_def_type[i/2], stitems[i+1])

                    i = int(i) + 1

        elif stitems[1] != "COMPLETE" and iINV == 0 and iDNB == 0:
            logging.info('Command %s not completed' % capi_run)

        if capi_elem[0] == 'sta_associate':
            time.sleep(10)
    except:
        exc_info = sys.exc_info()
        logging.error(exc_info[1])
        wfa_sys_exit("")

def send_capi_command(toaddr, capi_elem):
    """
    Send CAPI commands through socket based on IP address and
    port number

    Parameters
    ----------
    toaddr : str
        IP address and port number
    capi_elem : tuple of str
        CAPI command followed by parameters with "," as delimiter

    Returns
    -------
    status : str
        Contains string specifying command is running, complete
        or returning values

    Examples
    --------
    send_capi_command(192.168.0.1:9000, ca_get_version)
    send_capi_command(192.168.0.1:9000, sniffer_control_filter_capture,
        infile,_521-step1,outfile,521-step1_A,
        srcmac,00:11:22:33:44:55,destmac,55:44:33:22:11:00)
    """
    global iDNB, iINV
    capi_run = ','.join(capi_elem)
    capi_cmd = capi_run + ' \r\n'
    asock = conntable.get(toaddr)
    asock.send(capi_cmd)
    displayaddr = toaddr
    if toaddr in DisplayNameTable:
        displayaddr = DisplayNameTable[toaddr]
    logging.info("%s (%-15s) ---> %s" % (displayaddr, toaddr, capi_cmd.rstrip('\r\n')))
    status = asock.recv(2048)
    logging.debug("%s (%s) <--- %s" % (displayaddr, toaddr, status.rstrip('\r\n')))

    # Status,Running
    # Quick fix for case where AzWTG sends response RUNNING and COMPLETED in one read
    if len(status) > 25:
        status = status.split('\n')
        status = status[1]
    else:
        if iDNB == 0:
            status = asock.recv(2048)
        else:
            iDNB = 0

    if displayaddr == cSLog.name:
        cSLog.log("%s ---> %s" % (displayaddr, capi_cmd.rstrip('\r\n')))
        cSLog.log("%s <--- %s\n" % (displayaddr, status.rstrip('\r\n')))

    if re.search("FAIL", status) and re.search("SNIFFER", displayaddr) and iINV == 0:
        logging.info("%s <--- %s\n" % (displayaddr, status.rstrip('\r\n')))
        wfa_sys_exit("Command returned FAIL")
    return status

def process_cmdfile(line):
    """
    Process the file line by line based on file name and path specified

    Parameters
    ----------
    line : str
        File name and path

    Returns
    -------
    none

    Example
    --------
    process_cmdfile(C:\\WTS_UCC_Windows\\cmds\\11n\\STA_5.2.1.txt)
    """
    i = 0
    line = line.rstrip()
    filelist = []
    filelist = line.split(',')
    nfile = len(filelist)
    while i < nfile:
        logging.debug('Command file ---' + filelist[i])
        file = open(filelist[i])
        scanner(file, process_cmd)
        file.close()
        i = i+1

def set_test_result(result, data, rdata):
    XLogger.setTestResult(result, data, rdata)
    if re.search("PASS", result):
        set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
        logging.info("\n     TEST RESULT ---> %15s" % result)
    elif re.search("FAIL", result):
        set_color(FOREGROUND_RED |FOREGROUND_INTENSITY)
        logging.info("\n     TEST RESULT ---> %15s | %s |" % (result, data))

def process_passFailWMM_1(line):
    """Determines pass or fail for WMM based on results and what is expected"""
    global runningPhase
    try:
        cmd = line.split(',')
        P1 = -1
        P2 = -1

        for p in streamRecvResultArray:
            if p.streamID == retValueTable[cmd[0]] and int(p.phase) == int(runningPhase):
                P1 = p.rxBytes
            elif p.streamID == retValueTable[cmd[1]] and int(p.phase) == int(runningPhase):
                P2 = p.rxBytes
        if cmd[2] in retValueTable:
            cmd[2] = retValueTable[cmd[2]]

        if (int(P2) <= 0) or (int(P1) <= 0):
            actual = -1
        else:
            actual = (float(P2) / float(P1)) * 100

        if actual <= long(cmd[2]):
            set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
            result = cmd[3]
        else:
            set_color(FOREGROUND_RED | FOREGROUND_INTENSITY)
            result = cmd[4]

        logging.info("\n       ----------------RESULT---------------------------\n")
        logging.info("Expected  <= %s %s" % (cmd[2], "%"))
        logging.info("Actual -  %6.6s %s" % (actual, "%"))
        logging.info("TEST RESULT ---> %s" % result)
        logging.info("\n       ------------------------------------------------")
        set_color(FOREGROUND_INTENSITY)
        set_test_result(result, "%6.6s %s" % (actual, "%"), "<= %s %s" % (cmd[2], "%"))
    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_passFailWMM(line):
    """Determines pass or fail for WMM based on two phases result and what is expected"""
    try:
        cmd = line.split(',')
        P1 = -1
        P2 = -1

        for p in streamRecvResultArray:
            if p.streamID == retValueTable[cmd[0]] and int(p.phase) == 1:
                P1 = p.rxBytes
            elif p.streamID == retValueTable[cmd[1]] and int(p.phase) == 2:
                P2 = p.rxBytes

        if cmd[2] in retValueTable:
            cmd[2] = retValueTable[cmd[2]]

        if (int(P2) <= 0) or (int(P1) <= 0):
            actual = -1
        else:
            actual = (float(P2) / float(P1)) * 100

        if actual > long(cmd[2]):
            set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
            result = cmd[3]
        else:
            set_color(FOREGROUND_RED | FOREGROUND_INTENSITY)
            result = cmd[4]

        logging.info("\n       ----------------RESULT---------------------------\n")
        logging.info("%s Phase 1 = %s Bytes | %s Phase 2 = %s Bytes " %(cmd[5], P1, cmd[5], P2))
        logging.info("Expected  > %s %s" % (cmd[2], "%"))
        logging.info("Actual -  %6.6s %s" % (actual, "%"))
        logging.info("TEST RESULT ---> %s" % result)
        logging.info("\n       ------------------------------------------------")
        set_color(FOREGROUND_INTENSITY)
        set_test_result(result, "%6.6s %s" % (actual, "%"), "> %s %s" % (cmd[2], "%"))
    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_passFailIBSS(line):
    """Determines pass or fail for IBSS based on results and what is expected"""
    try:
        cmd = line.split(',')
        P1 = -1
        logging.debug("Processing PASS/FAIL...")
        for p in streamRecvResultArray:
            if p.streamID == retValueTable[cmd[0]]:
                P1 = p.rxBytes
                break
        logging.info(" Received = %s Bytes Duration = %s Seconds Expected = %s Mbps " % (P1, cmd[2], cmd[1]))
        logging.debug(" B = %s B1 = %s" % (((long(P1) / 10000)), ((float(cmd[1]) * 125000))))
        if int(P1) <= 0:
            actual = -1
        else:
            actual = ((float(P1) * 8)) / (1000000 * int(cmd[2]))

        logging.info("Expected = %s Mbps  Received =%s Mbps" % (cmd[1], actual))
        if float(actual) >= float(cmd[1]):
            result = cmd[3]
        else:
            result = cmd[4]
        set_test_result(result, "-", "-")

    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_CheckThroughput(line, Trans):
    """Determines throughput and prints the results and expected to logs"""
    try:
        cmd = line.split(',')

        if cmd[2] in retValueTable:
            cmd[2] = retValueTable[cmd[2]]
        if cmd[3] in retValueTable:
            cmd[3] = retValueTable[cmd[3]]

        P1 = -1
        logging.debug("Processing Throughput Check...")
        if Trans:
            for p in streamSendResultArray:
                if p.streamID == retValueTable[cmd[0]] and int(p.phase) == int(cmd[1]):
                    P1 = p.rxBytes
                    break
        else:
            for p in streamRecvResultArray:
                if p.streamID == retValueTable[cmd[0]] and int(p.phase) == int(cmd[1]):
                    P1 = p.rxBytes
                    break

        if int(P1) <= 0:
            actual = -1
        else:
            actual = ((float(P1) * 8))/(1000000 * int(cmd[2]))

        condition = ">="
        if float(actual) >= float(cmd[3]):
            result = cmd[4]
            if "fail" in result.lower():
                condition = "<="
        else:
            result = cmd[5]
            if "pass" in result.lower():
                condition = "<="

        logging.debug(" Received = %s Bytes Duration = %s Seconds Expected = %s Mbps " % (P1, cmd[2], cmd[3]))
        logging.info("\n Expected %s %s Mbps Actual = %s Mbps" % (condition, cmd[3], actual))
        set_test_result(result, "%s Mbps" %(actual), "%s Mbps" %(cmd[3]))

    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_CheckMCSThroughput(line):
    """Determines MCS throughput and prints the results and expected to logs"""
    try:
        cmd = line.split(',')
        logging.debug("process_CheckMCSThroughput")
        logging.debug("-%s-%s-%s-%s-%s" % (cmd[0], cmd[1], cmd[2], cmd[3], cmd[4]))

        TX = -1
        RX1 = -1
        RX2 = -1
        logging.debug("Processing Throughput Check...")
        for p in streamSendResultArray:
            if p.streamID == retValueTable[cmd[1]] and int(p.phase) == int(cmd[0]):
                TX = long(p.txBytes)
                break
        for p in streamRecvResultArray:
            if p.streamID == retValueTable[cmd[2]] and int(p.phase) == int(cmd[0]):
                RX1 = long(p.rxBytes)
            if p.streamID == retValueTable[cmd[3]] and int(p.phase) == int(cmd[0]):
                RX2 = long(p.rxBytes)

        logging.debug("-%s-%s-%s-%s" % (TX, RX1, RX2, cmd[4]))
        TX = (long(TX)* (float(cmd[4])/100))
        actual = -1
        if int(TX) <= 0:
            actual = -1
        else:
            if RX1 > TX and RX2 > TX:
                actual = 1

        if float(actual) > 0:
            result = cmd[5]
        else:
            result = cmd[6]

        logging.info("\n MCS Expected %s bytes, actual %s bytes and %s bytes" % (TX, RX1, RX2))
        set_test_result(result, "%s Bytes %s Bytes" %(RX1, RX2), "%s Bytes" % (TX))

    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_CheckDT4(line):
    """Determines amount of DT4 packets and prints the results and expected to logs"""
    try:
        cmd = line.split(',')
        logging.debug("process_Check DT4 Results")
        logging.debug("-%s-%s-%s-%s-%s-%s" % (cmd[0], cmd[1], retValueTable[cmd[1]], cmd[2], cmd[3], cmd[4]))
        RX = -1
        for p in streamSendResultArray:
            if p.streamID == retValueTable[cmd[1]] and int(p.phase) == int(cmd[0]):
                RX = long(p.rxFrames)

        logging.debug("-%s-%s" % (RX, cmd[2]))

        actual = -1
        if long(RX) > long(cmd[2]):
            actual = 1

        if float(actual) > 0:
            result = cmd[3]
        else:
            result = cmd[4]

        logging.info("\n DT4 Expected > %s packets, actual %s packets" % (cmd[2], RX))
        set_test_result(result, "%s Packets" %(RX), "%s Packets" % (cmd[2]))

    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def process_ResultCheck(line):
    """Determines pass or fail at the end of the test run"""
    try:
        cmd = line.split(',')
        logging.debug("%s-%s-%s-%s-%s-%s" % (retValueTable[cmd[0]], int(retValueTable["%s" % retValueTable[cmd[0]]]), cmd[0], cmd[1], cmd[2], cmd[3]))
        if int(retValueTable["%s" % retValueTable[cmd[0]]]) >= int(cmd[1]):
            result = cmd[2]
        else:
            result = cmd[3]

        XLogger.setTestResult(result)
        logging.info("\nTEST RESULT ---> %15s" % result)

    except:
        exc_info = sys.exc_info()
        logging.error('Invalid Pass/Fail Formula - %s' % exc_info[1])

def wfa_sys_exit(msg):
    """Exiting because an error has occurred"""
    time.sleep(2)
    set_color(FOREGROUND_RED | FOREGROUND_INTENSITY)
    if re.search("not applicable", msg) or re.search("not supported", msg):
        XLogger.setTestResult("TEST N/A")
    else:
        XLogger.setTestResult("ABORTED123", msg)

    XLogger.writeXML()
    sys.exit(msg)

def wfa_sys_exit_0():
    """Exiting because a failure has occurred"""
    time.sleep(2)
    set_color(FOREGROUND_CYAN | FOREGROUND_INTENSITY)
    logging.disable("ERROR")
    XLogger.writeXML()
    sys.exit(0)

class XMLLogHandler(logging.FileHandler):

    def emit(self, record):
        try:
            XLogger.log(self.format(record))
            self.flush()
        except:
            self.handleError(record)

XLogger = ""

def init_logging(_filename, level):
    global cSLog, XLogger
    p = _filename.split('\\')
    resultCollectionFile = open("TestResults", "a")
    for s in p:
        tFileName = s

    directory = "./log/%s_%s" %(tFileName.rstrip(".txt"), time.strftime("%b-%d-%Y__%H-%M-%S", time.localtime()))
    os.mkdir(directory)

    os.system("echo %s > p" % directory)

    fname = "%s/log_%s.log" %(directory, tFileName.rstrip(".txt"))
    fname_sniffer = "%s/sniffer_log_%s.log" % (directory, tFileName.rstrip(".txt"))
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename=fname,
                        filemode='w')
    cSLog = classifiedLogs("SNIFFER", fname_sniffer, "SNIFFER CHECKS LOG - Testcase: %s \n\n" % tFileName.rstrip(".txt"))
    #  a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    if level == '2':
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    if level != '0':
        logging.getLogger('').addHandler(console)
    set_color(FOREGROUND_INTENSITY)

    # Add XML Log Handler
    XLogger = XMLLogger("%s/%s_%s.xml" %
                        (directory,
                         tFileName.rstrip(".txt"),
                         time.strftime("%Y-%m-%dT%H_%M_%SZ",
                                       time.localtime())),
                        "%s" % (tFileName.rstrip(".txt")))
    hXML = XMLLogHandler('t')
    XMLformatter = logging.Formatter('%(message)s')
    hXML.setFormatter(XMLformatter)
    logging.getLogger('').addHandler(hXML)


    logging.info("###########################################################\n")
    logging.info("UCC Version - %s" % VERSION)
    logging.info('Logging started in file - %s' % (fname))


def firstword(line):
    global maxThroughput, payloadValue, uccPath
    str = line.split('#')
    command = str[0].split('!')

    if command[0] == 'wfa_control_agent' or command[0] == 'wfa_control_agent_dut':
        if retValueTable["$WTS_ControlAgent_Support"] != "0":
            process_ipadd(command[1])
            retValueTable.setdefault(command[0], "%s:%s" % ((command[1].split(',')[0]).split('=')[1], (command[1].split(',')[1]).split('=')[1]))
    elif  command[0] == 'wfa_console_ctrl' or command[0] == 'wfa_adept_control_agent' or re.search('control_agent_testbed_sta', command[0]) or re.search('control_agent', command[0]) or re.search('TestbedAPConfigServer', command[0]) or re.search('wfa_sniffer', command[0]) or re.search('ethernet', command[0]):
        process_ipadd(command[1])
        retValueTable.setdefault(command[0], "%s:%s" % ((command[1].split(',')[0]).split('=')[1], (command[1].split(',')[1]).split('=')[1]))
    elif command[0].lower() == 'exit':
        wfa_sys_exit("Exiting - %s" % command[1])
    elif command[0].lower() == 'info':
        if command[1] in retValueTable:
            command[1] = retValueTable[command[1]]
        logging.info("\n %7s ~~~~~ %s ~~~~~ \n" %("", command[1]))
    elif command[0] == 'wfa_test_commands':
        logging.debug('Processing wfa_test_commands')
        process_cmdfile("%s%s" % (uccPath, command[1]))
    elif command[0] == 'wfa_test_commands_init':
        logging.debug('Processing init wfa_test_commands')
        logging.debug("UCC Path = %s" % uccPath)
        s1 = command[1]
        scanner(open(uccPath + s1), firstword)
    if "$TestNA" in retValueTable:
        logging.error("%s" % retValueTable["%s" % "$TestNA"])
        wfa_sys_exit("%s" % retValueTable["%s" % "$TestNA"])
    elif command[0] == 'dut_wireless_ip' or command[0] == 'dut_default_gateway' or command[0] == 'wfa_console_tg' or re.search('wireless_ip', command[0]) or re.search('wmmps_console', command[0]) or re.search('tg_wireless', command[0]):
        retValueTable.setdefault(command[0], command[1])
    elif re.search('define', command[0]):
        if command[2] in retValueTable:
            command[2] = retValueTable[command[2]]
        if command[1] in retValueTable:
            retValueTable[command[1]] = command[2]
        else:
            retValueTable.setdefault(command[1], command[2])
    elif re.search('DisplayName', command[0]):
        if command[1] in retValueTable:
            DisplayNameTable.setdefault(retValueTable[command[1]], command[2])
        else:
            DisplayNameTable.setdefault(command[1], command[2])
    elif re.search('throughput', command[0]):
        maxThroughput = command[1]
        logging.info("Maximum Throughput %s Mbps" % maxThroughput)
        retValueTable.setdefault(command[0], command[1])
    elif re.search('payload', command[0]):
        payloadValue = command[1]
        logging.info("Payload =  %s Bytes", (command[1]))
        retValueTable.setdefault(command[0], command[1])
    elif re.search('stream', command[0]):
        logging.debug("STREAM = %s, Payload = %s Bytes, Percentage = %s %s of Maximum Throughput" %(command[0], payloadValue, command[1], "%"))
        frameRate = int(maxThroughput) * int(command[1])*1250/int(payloadValue)
        logging.info("%s %s Frames / second"  % (command[0], frameRate))
        retValueTable.setdefault(command[0], "%s" % frameRate)
    if len(command) == 2:
        logging.debug("Command = %s" % (command[1]))
