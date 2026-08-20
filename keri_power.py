""" Utility to power control Kerisys controller at HSA

This communicates with a Raspberry Pi located in the HSA computer room.  Relays on the Pi
are used to intercept the V(12v) from the power supply to each Kerisys panel, so that both AC
power and battery power are cut off for a forced reboot.

There is some inversion of terminology due to how we use the Pi relays.

Power is connected to the C/NC terminals, so power is on when the relay is not energized
Power is disconnected when the relay is energized.  This is so any hardware failure on th Pi, or
termination of the process monitoring the control port will leave the Keri panels powered up.

What this means is that what the code sees as on (relay engaged) turns off the power.

The user interface shows the uses reality (power status to the Keri), not the relay power status.

So off in on, and on is off, so to speak.


"""
# pylint: disable=C0103,C0209,W0621,W0602,C0301,R0914,I1101
# pyline: disable=W0614,W0401,W0703,W0603,W0614,W1308

import sys
import json
import socket
from tkinter import *

VERSION = 1.0
SLEEPTIME = 3

#
# This must be changed to the address of the Raspberry Pi on the CAN (clubhouse area network)
# for this to work on machines within the HSA complex.
#
HOSTADDR = "hsaclub.ddns.net"
PORT = 10004

tkroot = Tk()
var = IntVar()
tkroot.geometry("800x300")
tkroot.resizable(False, False)
tkroot.title("Pi Kerisys Power Controller")

currentRow = 0
sequence_num = 0

tkroot.columnconfigure(0, weight=1)
tkroot.rowconfigure(0, weight=1)

def getNextRow(init=False):
    """Get next row number to use, reset count if init set to Trye"""
    global currentRow
    if init:
        currentRow = 0
    t = currentRow
    currentRow += 1
    return t

def sequence(init=False):
    """ Use to generate ascending sequence numbers for button menu """
    global sequence_num
    sequence_num = 1
    while True:
        if init:
            sequence_num = 1
        yield sequence_num
        sequence_num += 1

def clrwin():
    """Clear the text display window"""
    textArea.configure(state="normal")
    textArea.delete("1.0", END)
    textArea.configure(state="disable", bg="lightgray")
    textArea.configure(state="disabled")

def oneLine(value):
    """Add one line to results display window without clearing current content"""
    textArea.configure(state="normal")
    textArea.insert(INSERT, value)
    textArea.update()
    textArea.configure(state="disable")

def sendToControl(jsonstuff):
    """ Connect to socket on client Pi and send control message """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print('beta\n');
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(1)
            s.connect((HOSTADDR,PORT))
            jsonmsg = json.dumps(jsonstuff)
            s.send(jsonmsg.encode('UTF-8'))
            data = s.recv(1024)
            if not data:
                oneLine("No message received from controller at clubhouse")
                textArea.configure(bg='pink')
            else:
                jsonret=json.loads(data)
                if jsonret["system"] != "keri":
                    oneLine('Bad return from client: {data}')
                    textArea.configure(state="disable", bg="orange", wrap="word")
                else:
                    match jsonret["type"]:
                        case "status":
                            color1 = "red" if jsonret["led1on"] else "green"
                            color2 = "red" if jsonret["led2on"] else "green"
                            canvas.itemconfig(rect1, fill=f'{color1}')
                            canvas.itemconfig(rect2, fill=f'{color2}')
                        case "error":
                            err = jsonret["error"]
                            oneLine(f'Client error: {err}')
                textArea.configure(bg="lightgreen")
    except TimeoutError as e:
        oneLine('Exception connecting to Raspberry Keri power controller\n')
        textArea.configure(bg='pink')
    except Exception as e:
        oneLine(f'Exception {str(e)}')
        textArea.configure(bg='red')

def keri_action(action, relay, message):
    """ Construct message to be send to client Pi """
    jsonm = {}
    jsonm['target'] = 'keri'
    jsonm['action'] = action
    jsonm['relay'] = relay
    jsonm['message'] = message
    if action == "on":
        oneLine(f'Turning Keri {relay} off\n')
    if action == "off":
        oneLine(f'Turning Keri {relay} on\n')
    sendToControl(jsonm)

def keri_on1():
    """ Turn relay #1 on which actually powers Keri #1 off """
    clrwin()
    keri_action('on', 1, 'Disabling Keri panel #1')

def keri_on2():
    """ Turn relay #2 on which actually powers Keri #2 off """
    clrwin()
    keri_action('on', 2, 'Disabling Keri panel #2')

def keri_off1():
    """ Turn relay #1 off which actually powers Keri #1 on """
    clrwin()
    keri_action('off', 1, 'Enabling Keri panel #1')

def keri_off2():
    """ Turn relay #2 off which actually powers Keri #2 on """
    clrwin()
    keri_action('off', 2, 'Enabling Keri panel #2')

def keri_status(show_msg = True):
    """ Fetch status from client and display it """
    clrwin()
    if(show_msg):
        oneLine('Updating status of Keri panels\n')
    keri_action('status', 0, "Getting status of Kerisys panels")

#
# Layout the UI
#
left = Frame(tkroot)
left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

Label(left, text="Version {}".format(VERSION)).pack(anchor='center')

buttons = [
    ("Power off Keri #1", keri_on1),
    ("Power off Keri #2", keri_on2),
    ("Power on Keri #1", keri_off1),
    ("Power on Keri #2", keri_off2),
    ("Update Kerisys Status", keri_status),
    ("Exit", sys.exit)
]

for (prompt, fctn) in buttons:
    Button(left, width=18, text=prompt, command=fctn).pack(anchor='center')

right = Frame(tkroot)
right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

canvas = Canvas(right, height=50, width=800, borderwidth=0, highlightthickness=0, bg='white')
canvas.pack(fill=BOTH, expand=True, padx=10, pady=5)
rect1 = canvas.create_rectangle(0,    0, 290, 50, width=0, fill='gray')
rect2 = canvas.create_rectangle(310,  0, 600, 50, width=0, fill='gray')
canvas.create_text(150,25,text="Keri #1 (.220)", font=('ariel',12,'bold'), fill='yellow')
canvas.create_text(450,25,text="Keri #2 (.221)", font=('ariel',12,'bold'), fill='yellow')

welcomeMsg = ( "Kerisys Panel Power Conrol\n\n"
               "Use this to power cycle panels to recover from a system hang"
               " or unexplained failure for a reader to work" )

keriUses = ("Keri #1: Basement Door, Pistol, Stairs, Arms Room\n"
            "Keri #2: Rifle Gate, Skeet Gate, Furnace, Front Door")

textArea = Text(right, height=2, font=("Courier", 14))
textArea.pack(fill=BOTH, expand=True, padx=10, pady=5)
textArea.insert(INSERT, keriUses)
textArea.configure(state="disable", bg="white", wrap="word")

textArea = Text(right, font=("Courier", 14))
textArea.pack(fill=BOTH, expand=True, padx=10, pady=0)
textArea.insert(INSERT, welcomeMsg)
textArea.configure(state="disable", bg='lightgray', wrap="word")

keri_status(False)
oneLine(welcomeMsg)

tkroot.mainloop()
