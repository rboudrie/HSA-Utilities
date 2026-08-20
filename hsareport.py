""" Utility to get useful info from Kerisys access database and
    hopkinton.helloclub.com membership database
"""
# pylint: disable=C0103,C0209,W0621,W0602,C0301,R0914,I1101
# pyline: disable=W0614,W0401,W0703,W0603,W0614,W1308
import http.client
import json
import re
import smtplib
import sys
import time
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from tkinter import *
from tkinter import scrolledtext
from tkinter import ttk

import pyodbc
import unidecode
from jellyfish import soundex

VERSION = 1.6

RETRY_WAIT = 5

HELLO_CLUB_API_KEY = "hc_sjzm95fK83ZA6hMSBZnpLTrHhiDxZ1T6tjY6L"
EMAIL_SENDER = "hsamailsend@gmail.com"
EMAIL_SENDER_PW = "knife&gun"

MSSQL_CONNECTION_STRING = (
    r"APP=hsautil;"
    r"DRIVER={SQL Server};"
    r"SERVER=KERISYS\ECLIPSE;"
    r"DATABASE=DHS_MAIN;"
    r"UID=dhsuser;"
    r"PWD=eclip$e"
)

multiples = None
hellonameinfo = None
knameinfo = None
kcardinfo = None
ksoundex2name = None
hellocard2name = None
hellohsa2name = None
dataFetchedKeri = False
dataFetchedHello = False
reportName = "Welcome"
currentRow = 0

def sequence(init=False):
    """ Use to generate ascending sequence numbers for button menu """
    global sequence_num
    sequence_num = 1
    while True:
        if init:
            sequence_num = 1
        yield sequence_num
        sequence_num += 1


def getNextRow(init=False):
    """Get next row number to use, reset count if init set to Trye"""
    global currentRow
    if init:
        currentRow = 0
    t = currentRow
    currentRow += 1
    return t


def clearCache():
    """Clear cache from HelloClub and Kerisys databii"""
    global dataFetchedKeri, dataFetchedHello
    dataFetchedKeri = False
    dataFetchedHello = False
    setMessage("Database cache cleared", level=2)


def setMessage(inval, level=1):
    """Fill small message window"""
    print(f"{inval}\n");

    msgtext.configure(state="normal")
    msgtext.delete("1.0", END)
    msgtext.insert(INSERT, inval)
    color = ["white", "yellow", "tomato"][level - 1]
    msgtext.configure(bg=color, state="disable")


def send_report():
    """Email report as an attachment"""
    setMessage("")
    emailaddr = emailinput.get("1.0", END).rstrip(" \n")
    if not emailaddr:
        setMessage("Blank email address", level=2)
        return
    regex = "^[a-z0-9]+[\\._]?[a-z0-9]+[@]\\w+[.]\\w{2,3}$"
    valid = re.search(regex, emailaddr)
    if not valid:
        setMessage('Invalid email address "{}"'.format(emailaddr), level=2)
        return
    messageText = textArea.get("1.0", END).strip(" \n")
    if len(messageText) < 10:
        setMessage("Report area is blank - nothing to send", level=2)
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = emailaddr
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = "HSA report you requested"

    msg.attach(MIMEText("Your requested report: {}.txt is attached".format(reportName)))
    part = MIMEApplication(messageText, name="{}.txt".format(reportName))
    part["Content-Disposition"] = "attachment; filename={}.txt".format(reportName)
    msg.attach(part)

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(EMAIL_SENDER, EMAIL_SENDER_PW)
        server.sendmail(EMAIL_SENDER, emailaddr, msg.as_string())
        server.close()
        setMessage("Report sent to {}".format(emailaddr))
    except Exception:  # pylint: disable=W0702
        (etype, value, _) = sys.exc_info()
        setMessage(
            "Error sending email to {}, error {} value {}".format(
                emailaddr, etype, value
            ),
            level=2,
        )


def send_report_a():
    """email contents of display window"""
    emailfrom = EMAIL_SENDER
    emailpw = EMAIL_SENDER_PW
    setMessage("")
    emailaddr = emailinput.get("1.0", END).rstrip(" \n")
    if not emailaddr:
        setMessage("Blank email address", level=2)
        return
    regex = "^[a-z0-9]+[\\._]?[a-z0-9]+[@]\\w+[.]\\w{2,3}$"
    valid = re.search(regex, emailaddr)
    if not valid:
        setMessage('Invalid email address "{}"'.format(emailaddr), level=2)
        return
    content = "From: {}\nTo: {}\nSubject: {}\n{}".format(
        emailfrom, emailaddr, "HSA Report", textArea.get("1.0", END)
    )

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(emailfrom, emailpw)
        server.sendmail(emailfrom, emailaddr, content)
        server.close()
        setMessage("Report sent to {}".format(emailaddr))
    except Exception:
        setMessage("Error sending email!", level=2)


def oneLine(value):
    """Add one line to results display window without clearing current content"""
    textArea.configure(state="normal")
    textArea.insert(INSERT, value)
    textArea.update()
    textArea.configure(state="disable")


def fillBox(lines, append=False, withdate=True):
    """Put data into the display window"""
    textArea.configure(state="normal")
    textArea.configure(bg="white")
    if not append:
        textArea.delete("1.0", END)
    else:
        textArea.insert(INSERT, "\n")
    if withdate:
        dtext = date.today().strftime("%B %d ,%Y")
        textArea.insert(INSERT, "Report generated: {}\n\n".format(dtext))
    for line in lines:
        textArea.insert(INSERT, line + "\n")
    textArea.configure(state="normal")


def clrwin():
    """Clear the text display window"""
    textArea.configure(state="normal")
    textArea.delete("1.0", END)
    textArea.configure(state="disable", bg="sky blue")
    setMessage("", level=1)
    textArea.configure(state="disabled")


def popup():
    """Popup progress window (unsed)"""
    pwin = Tk()
    pwin.title("In progress window")
    label = Label(pwin, text="Wait a bit")
    label.pack()
    label.update()
    time.sleep(500)
    label["text"] = "again...."
    label.update()


def get_data_keri():
    """Get data from Kerisys MsSQL databsae.  No need for warning
    since database response is very quick
    """
    global dataFetchedKeri, knameinfo, kcardinfo, ksoundex2name, multiples
    if dataFetchedKeri:
        return
    (knameinfo, kcardinfo, ksoundex2name, multiples) = getKerisysData()
    dataFetchedKeri = True


def get_data_hello():
    """Get data from Helloclub database with wait warning for user"""
    global helloname, hellonameinfo, hellocard2name, hellohsa2name, dataFetchedHello
    if dataFetchedHello:
        return
    msg = [
        "Fetching data from app.helloclub.com, please wait."
        "\n\nOnce this data is downloaded, you can browse through "
        "the variuous reports without delay."
        "\n\nProgress:"
    ]
    fillBox(msg, withdate=False)
    textArea.configure(bg="yellow")
    root.update()
    (hellonameinfo, hellocard2name, hellohsa2name) = getHelloClubData()
    dataFetchedHello = True
    textArea.configure(bg="white")


def intInString(sval):
    """Find integer in a string"""
    return int("".join(filter(str.isdigit, sval)))


def n2b(a, default=""):
    """Change None to empty string, otherwise unchanged"""
    if a is None:
        return default
    return a


def banner(newlineb4, x):
    """Pretty header"""
    hd = "*" * (len(x) + 4)
    nline = "\n" if newlineb4 else ""
    return "{0}{1}\n* {2} *\n{1}".format(nline, hd, x)


def getKerisysData():
    """Fetch info from Kerisys access contorl MS/SQL database"""
    cardinfo = {}
    cnxn = None
    cmd = (
        "SELECT dc.First_name, dc.Last_name, cr.Cardnumber, st.IsActive, dc.custom1, "
        "dc.custom7, dc.CardHolderID "
        "FROM dbo.CardHolder as DC, dbo.Credential AS cr, dbo.CardStatus as st "
        "WHERE dc.CardHolderID = cr.cardHolderID AND cr.CardStatusID = st.CardStatusID "
        "ORDER BY Last_name, First_name"
    )
    try:
        cnxn = pyodbc.connect(MSSQL_CONNECTION_STRING)
    except Exception:
        (etype, value, _) = sys.exc_info()
        setMessage(
            "Error connecting to Kerisys Database, error {} value {}".format(
                etype, value
            ),
            level=2,
        )

        setMessage("Failure to connect to MsSQL server; check stdout", level=3)

    cursor = cnxn.cursor()
    cursor.execute(cmd)

    cnxnt = pyodbc.connect(MSSQL_CONNECTION_STRING)

    nameinfo = {}
    cardinfo = {}
    sndx2name = {}
    multiples = []
    row = cursor.fetchone()
    while row:
        fname = row[0]
        lname = row[1]
        cardnum = str(row[2])
        cardstat = row[3]
        hsanum = row[4]
        reason = row[5]
        cardholderid = row[6]
        name = fname + " " + lname

        cmd = (
            "SELECT top 1 msg.TimeStamp_server "
            "FROM dbo.Message msg "
            "WHERE msg.CardHolderID='{}'"
            "ORDER BY msg.TimeStamp_server DESC "
        ).format(cardholderid)
        cursort = cnxnt.cursor()
        cursort.execute(cmd)
        rowt = cursort.fetchone()

        sndx = soundex(fname) + soundex(lname)
        sndx2name[sndx] = name

        if cardnum not in cardinfo:
            cardinfo[cardnum] = {}
        cardinfo[cardnum]["name"] = name
        cardinfo[cardnum]["active"] = cardstat

        if name in nameinfo:
            multiples.append(name)
        else:
            nameinfo[name] = {}

        nameinfo[name]["lastused"] = rowt[0].strftime("%m/%d/%y") if rowt else "-"
        nameinfo[name]["hsa"] = hsanum
        nameinfo[name]["reason"] = reason
        if "card" in nameinfo[name]:
            nameinfo[name]["card"].append(cardnum)
        else:
            nameinfo[name]["card"] = [cardnum]
        row = cursor.fetchone()
    cnxn.close()
    cnxnt.close()
    return (nameinfo, cardinfo, sndx2name, multiples)


def getHelloClubData():
    """Establish server connection"""
    api_key = HELLO_CLUB_API_KEY
    headers_json = {"Content-type": "application/json", "X-Api-Key": api_key}
    conn = http.client.HTTPSConnection("api.helloclub.com")

    offset = 0
    more = True
    kcard2name = {}
    hsa2name = {}
    nameinfo = {}
    sofar = 0
    while more:
        endpoint = "/member?offset={}".format(offset)
        conn.request("GET", endpoint, headers=headers_json)
        res = conn.getresponse()

        js = json.loads(res.read().decode("utf-8"))

        if not "members" in js:
            oneLine("HelloClub Query did not return records, sleeping {} seconds and retrying".format(RETRY_WAIT))
            time.sleep(RETRY_WAIT)
            continue

        sofar += len(js["members"])

        if offset == 0:
            count = js["meta"]["count"]           

            total = js["meta"]["total"]
            oneLine("Reading {} total records\n".format(total))
        oneLine("{} records read.\n".format(sofar))

        for memb in js["members"]:
            firstname = memb.get("firstName", "-")
            lastname = memb.get("lastName", "-")
            firstname = unidecode.unidecode(firstname)
            lastname = unidecode.unidecode(lastname)
            age = memb.get("age", 0)
            name = firstname + " " + lastname + " " + str(age)
            kericard = memb["customFields"].get("accessCard", "none")
            dupe = 0
            if name in nameinfo:
                dupe = 1
            nameinfo[name] = {}
            nameinfo[name]["age"] = age
            nameinfo[name]["duplicate"] = dupe
            nameinfo[name]["accesscard"] = str(kericard)
            nameinfo[name]["soundex"] = soundex(firstname) + soundex(lastname)
            customfields = memb.get("customFields", None)
            if customfields:
                hsanum = customfields.get("memberId", "")
                if hsanum != "":
                    hsa2name[hsanum] = name
            if kericard != 0:
                kcard2name[kericard] = name
            nameinfo[name]["hsa"] = hsanum
            # Check for current membership
            nameinfo[name]["endDate"] = ""
            nameinfo[name]["current"] = False
            subscriptions = memb.get("subscriptions", None)
            if subscriptions:
                for subscr in subscriptions:
                    if subscr["isCurrent"]:
                        nameinfo[name]["current"] = True
                    else:
                        if subscr["endDate"] > nameinfo[name]["endDate"]:
                            nameinfo[name]["endDate"] = subscr["endDate"]

        offset += count
        more = offset < total
    return (nameinfo, kcard2name, hsa2name)


def reportKeriDuplicates(append=False):
    """Report users duplicated in Kerisys"""
    global reportName
    setMessage("")
    reportName = "Kerisys Duplicates"
    cmd = (
        "SELECT count(*) as cnt, First_Name, Last_name "
        "FROM dbo.CardHolder "
        "GROUP BY Last_name, First_name "
        "HAVING count(*) > 1"
    )
    try:
        cnxn = pyodbc.connect(MSSQL_CONNECTION_STRING)
    except Exception:
        (etype, value, _) = sys.exc_info()
        setMessage(f"Error connecting to Kerisys Database, error {etype} value {value}",level=2)
        setMessage("Failure to connect to MsSQL server; check stdout", level=3)
    txtout = []
    txtout.append(banner(append, "Users duplicated in Kerisys"))
    txtout.append(
        "\nOther reports may not be accurate for any duplicated members as the code expects "
        "all Kerisys entries to have unique member names (middle name in Kerisys not used).\n"
    )
    fmt = "{:32s} {:4d}"
    fmt2 = "{:32s} {:4s}"
    txtout.append(
        "\nThis report does not check for unique middle names or initials "
        "that are specified in the Kerisys middle name files.\n"
    )
    txtout.append(fmt2.format("User", "Num"))
    txtout.append(fmt2.format("-" * 32, "----"))
    cursor = cnxn.cursor()
    cursor.execute(cmd)

    count = 0
    row = cursor.fetchone()
    if not row:
        txtout.append("No users duplicated in Kerisys")
    while row:
        cnt = row[0]
        firstName = row[1]
        lastName = row[2]
        count += 1
        txtout.append(fmt.format(firstName + " " + lastName, cnt))
        row = cursor.fetchone()
    txtout.append("\nUsers dupliated in Kerisys: {}".format(count))
    fillBox(txtout, append=append)


def reportSoundexMatch(append=False):
    """Report soundex matches between Keri and HelloClub"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    setMessage("")
    reportName = "HSA_Soundex_Matches"
    get_data_hello()
    get_data_keri()
    txtout = []
    txtout.append(banner(append, "Soundex match candidates"))
    txtout.append("\n{:32s} {}".format("Hello Club Name", "Kerisys name(s)"))
    txtout.append("----------------------------------------------------------")
    count = 0

    for name, namedetails in hellonameinfo.items():
        if name in knameinfo:
            continue
        hsoundex = namedetails["soundex"]
        if hsoundex in ksoundex2name:
            count += 1
            txtout.append("{:32s} {}".format(name, ksoundex2name[hsoundex]))
    txtout.append("\nPossible Soundex matches: {}".format(count))
    fillBox(txtout, append=append)


def reportHelloClubOnly(append=False):
    """Report persons listed only in Helloclub and not in Keri"""
    global hellonameinfo, knameinfo, reportName, reportName
    setMessage("")
    reportName = "Persons only only in HelloClub"
    get_data_hello()
    get_data_keri()
    txtout = []
    txtout.append(banner(append, "Only in HelloClub"))
    count = 0
    fmt = "{:32s} {:>8s}"
    txtout.append(fmt.format("Member", "HSA"))
    txtout.append(fmt.format("-" * 32, "-" * 8))
    for name, namedetails in hellonameinfo.items():
        if name not in knameinfo:
            txtout.append(fmt.format(name, namedetails["hsa"]))
            count += 1
    txtout.append("\nMembers listed only in HelloClub: {}".format(count))
    fillBox(txtout, append=append)


def reportHelloClubDuplicates(append=False):
    """Report persons listed more than once in HelloClub"""
    global hellonameinfo, reportName
    setMessage("")
    reportName = "Duplicates in HellpClub"
    get_data_hello()
    txtout = []
    txtout.append(banner(append, "Duplicated in HelloClub"))
    txtout.append(
        "\nOther reports may not be accurate for any duplicated members as the code expects "
        "all HelloClub entries to have unique member names.\n"
    )
    count = 0
    fmt = "{:32s}"
    txtout.append(fmt.format("\nMember"))
    txtout.append(fmt.format("-" * 32))
    for name, namedetails in hellonameinfo.items():
        if namedetails["duplicate"]:
            count = count + 1
            txtout.append(fmt.format(name))
    txtout.append("\nMembers duplicated in HelloClub: {}".format(count))
    fillBox(txtout, append=append)


def reportExpired(append=False):
    """Expired persons in Helloclub still in Kerisys"""
    global hellonameinfo, knameinfo, kcardinfo, reportName
    setMessage("")
    reportName = "Members in Kerisys with expired memberships"
    get_data_hello()
    get_data_keri()
    txtout = []
    txtout.append(banner(append, "Expired in Kerisys"))
    count = 0
    fmt = "{:32s} {:>8s} {:8s} {:10s}"
    txtout.append(fmt.format("Member", "HSA", "Card", "Expired"))
    txtout.append(fmt.format("-" * 32, "-" * 8, "-" * 8, "-" * 10))
    for name, namedetails in hellonameinfo.items():
        if name in knameinfo:
            if not namedetails["current"]:
                cardnums = knameinfo[name]["card"]

                cardstatus = "Inactive"
                for cardnum in cardnums:
                    if kcardinfo[cardnum]["active"]:
                        cardstatus = "Active"
                txtout.append(
                    fmt.format(
                        name,
                        namedetails["hsa"],
                        cardstatus,
                        namedetails["endDate"][:10],
                    )
                )
                count += 1
    txtout.append("\nExpired members in Kerisys: {}".format(count))
    fillBox(txtout, append=append)

def reportAges(append=False):
    """ Report age demographics """
    reportName = "Age Demographics"
    get_data_hello()
    txtout = []
    txtout.append(banner(append, "Age Demographics"))
#    txtout.append("\n{:32s} {}".format("Hello Club Name", "Kerisys name(s)"))
#    txtout.append("----------------------------------------------------------")
 
    count = 0
    minage=999;
    maxage=0;
    missing_age=0
    ages = [];
    for i in range(0, 100):
        ages.insert(i, 0);

    for name, namedetails in hellonameinfo.items():
        count += 1
        age = namedetails["age"]
        if(age == ""):
            missing_age += 1 
        else:
            minage=min(age, minage)
            maxage=max(age,maxage)
            if (age >=0) and (age<=100):
                ages[age] += 1;

    for tcount,value in enumerate(ages):
        txtout.append("{},{}".format(tcount,value))
       
    txtout.append("Members: {} Ages {}-{} Missing age info:{}".format(count, minage, maxage,missing_age))
    fillBox(txtout, append=append)

def reportMismatches(append=False):
    """Report members in both Keri and Helloclub with different Keri
    card numbers assigned.
    """
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    setMessage("")
    reportName = "HSA_Keri_HelloClub_Mismatch"
    count = 0
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(
        banner(append, "Access Card Mismatches Between HelloClub and Kerisys")
    )
    txtout.append("\n{:32s} {:8s} {:s}".format("Name", "HelloCl", "Kerisys"))
    txtout.append("-------------------------------- -------- ----------------")
    for name, namedetails in hellonameinfo.items():
        if name not in knameinfo:
            continue
        kericards = knameinfo[name]["card"]
        hellocard = str(namedetails["accesscard"])
        if hellocard not in kericards:
            count = count + 1
            txtout.append(
                "{:32s} {:8s} {}".format(name, hellocard, ",".join(kericards))
            )
    txtout.append("\nMembers with mismatched access card numbers: {}".format(count))
    fillBox(txtout, append=append)


def reportOnlyHello(append=False):
    """Report members only in Helloclub"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    setMessage("")
    reportName = "HSA_Only_In_Helloclub"
    count = 0
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(banner(append, "Users only in HelloClub"))
    for name, details in hellonameinfo.items():
        if name not in knameinfo:
            count = count + 1
            txtout.append(
                "{:32s} {:>8s} {:>8s}".format(
                    name, details["hsa"], details["accesscard"]
                )
            )
    txtout.append("Members only in Helloclub: {}".format(count))
    fillBox(txtout, append=append)


def reportMismatchMemberNum(append=False):
    """Report members with HSA# different in Keri and HElloclub"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name, hsadetails
    global reportName
    setMessage("")
    reportName = "HSA_Mismatch_Membernum"
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(
        banner(
            append, "Users with mismatched HSA member numbers in Helloclub and Kerisys"
        )
    )

    txtout.append(
        "\nNon-integer characters and leading zeroes ignored in comparison, "
        "for example, 00987SR and 987 are considered matching numbersp.\n"
    )
    txtout.append("{:32s} {:>8s} {:>8s}".format("Name", "HelloCl", "Keri"))
    txtout.append("-------------------------------- -------- --------")
    count = 0
    for hname, hdetails in hellonameinfo.items():
        if hname in knameinfo:
            hhsa = hdetails.get("hsa", "")
            khsa = n2b(knameinfo[hname]["hsa"])
            if khsa == "":
                continue
            # Look only at digits only in member number for compare
            if intInString(hhsa) != intInString(khsa):
                txtout.append("{:32s} {:>8s} {:>8s}".format(hname, hhsa, khsa))
                count += 1
    txtout.append(
        "\nTotal users with mismatches HSA member numbers in Helloclub and Kerisys: {}".format(
            count
        )
    )
    fillBox(txtout, append=append)


def reportKeriOnlyReason(append=False):
    """Report members only in Kerisys with the "Reason" custome field populated"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    setMessage("")
    reportName = "HSA_Contractors_only_in_keri"
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(banner(append, "Users only in Kerisys (REASON set in Keri)"))
    count = 0
    txtout.append(
        "{:32s} {:8s} {:12s} {:8s}".format("Name", "HSA #", "Reason", "Last Use")
    )
    txtout.append("-------------------------------- -------- ------------ --------")
    for keriname, nameinfo in knameinfo.items():
        if keriname not in hellonameinfo:
            active = False
            for card in nameinfo["card"]:
                if kcardinfo[card]["active"]:
                    active = True
            msg = "" if active else " (no active cards)"
            hsanum = n2b(nameinfo["hsa"])
            n2b(hsanum, default="-")
            reason = nameinfo["reason"]
            lastused = nameinfo["lastused"]
            if reason is None:
                continue
            count += 1
            txtout.append(
                "{:32s} {:8s} {:12s} {:8s} {}".format(
                    keriname, hsanum, reason, lastused, msg
                )
            )
    txtout.append(
        "\nTotal users only in Kerisys who have issuance reason: {}".format(count)
    )
    fillBox(txtout, append=append)


def reportKeriOnlyMembers(append=False):
    """Report persons in Keri only who have HSA member numbers"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    setMessage("")
    reportName = "HSA_Members_only_in_keri"
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(banner(append, "Users only in Kerisys (with member number)"))
    count = 0
    txtout.append("{:32s} {:8s} {}".format("Name", "HSA #", "Last Use"))
    txtout.append("-------------------------------- -------- --------")
    for keriname, nameinfo in knameinfo.items():
        if keriname not in hellonameinfo:
            active = False
            for card in nameinfo["card"]:
                if kcardinfo[card]["active"]:
                    active = True
            msg = "" if active else " (no active cards)"
            hsanum = nameinfo["hsa"]
            lastused = nameinfo["lastused"]
            if hsanum is None:
                continue
            count += 1
            txtout.append(
                "{:32s} {:8s} {:8s} {}".format(keriname, hsanum, lastused, msg)
            )
    txtout.append(
        "\nTotal users only in Kerisys who have member numbers: {}".format(count)
    )
    fillBox(txtout, append=append)


def reportKeriOnlyNonmem(append=False):
    """Report names in Keri only that do not have a member number or
    reason custom field filled in
    """
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global helloname, hellonameinfo, hellocard2name, hellohsa2name
    global reportName
    reportName = "HSA_Nonmembers_in_keri"
    get_data_keri()
    get_data_hello()
    txtout = []
    txtout.append(
        banner(append, "Users only in Kerisys - no Member # or Reason for card")
    )
    count = 0
    txtout.append("{:32s} {:8s}".format("Name", "Last Use"))
    txtout.append("-------------------------------- --------")
    for keriname, nameinfo in knameinfo.items():
        if keriname not in hellonameinfo:
            active = False
            for card in nameinfo["card"]:
                if kcardinfo[card]["active"]:
                    active = True
            msg = "" if active else " (no active cards)"
            hsanum = nameinfo["hsa"]
            if hsanum is not None:
                continue
            reason = nameinfo["reason"]
            lastused = nameinfo["lastused"]
            if reason is not None:
                continue
            count += 1
            txtout.append("{:32s} {:8s} {}".format(keriname, lastused, msg))
    txtout.append("\nTotal users only in Kerisys: {}".format(count))
    fillBox(txtout, append=append)


def reportMultiCards(append=False):
    """Report members with more than one active Keri card"""
    global knameinfo, kcardinfo, ksoundex2name, multiples
    global reportName
    setMessage("")
    reportName = "HSA_multiple_card_holders"
    get_data_keri()

    txtout = []
    txtout.append(banner(append, "Users with more than one active card."))
    txtout.append("\nCards  User")
    txtout.append("-----  --------------------------------")
    count = 0
    for name, nameinfo in knameinfo.items():
        cards = nameinfo["card"]
        if len(cards) > 1:
            active_count = 0
            cstr = ""
            for card in cards:
                if kcardinfo[card]["active"]:
                    active_count += 1
                    cstr += card + ","
            cstr.rstrip(",")
            if active_count > 1:
                txtout.append("{:>5d}  {}".format(active_count, name))
                count += 1
    txtout.append(
        "\nTotal users with more than one active access card: {}".format(count)
    )
    fillBox(txtout, append=append)


def reportUniqueDays(append=False):
    """Usage statistics from Kerisys"""
    global reportName
    setMessage("")
    year = int(optMenu.cget("text"))
    reportName = "HSA_visits_year_{}".format(year)

    txtout = []
    fmt = "{:>24s} {:24s} {:4d}"
    fmth = "{:^49s} {:>4}"

    txtout.append(
        banner(
            0,
            "Number of unique days a member used the club w/card in {:d}".format(year),
        )
    )
    txtout.append(fmth.format("Cardholder", "Days"))
    txtout.append(fmth.format("-" * 49, "----"))

    chids = []
    counta = 0
    countb = 0
    cmd = (
        "select ftb.fname, ftb.lname, count(*) as days, cid from "
        "(select count(*) as cnt, ch.First_Name as fname, ch.Last_Name as lname, "
        "DATEPART(y,msg.TimeStamp_Server) as dpt, msg.CardHolderID as cid "
        "from dhs_main.dbo.Message msg, dhs_main.dbo.CardHolder ch "
        "where msg.CardHolderID = ch.CardHolderID and year(msg.TimeStamp_Server) = {:d} "
        "and msg.MessageDescription = 'Access Granted' "
        "group by DATEPART(y, msg.TimeStamp_Server), msg.CardHolderID, "
        "ch.First_Name, ch.Last_Name, ch.CardHolderID "
        ") as ftb "
        "group by  ftb.fname, ftb.lname, ftb.cid "
        "order by days desc, lname, fname ".format(year)
    )

    conn = pyodbc.connect(MSSQL_CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(cmd)

    row = cursor.fetchone()
    while row:
        counta += 1
        fname = row[0]
        lname = row[1]
        days = row[2]
        cid = row[3]
        chids.append(cid)
        txtout.append(fmt.format(fname, lname, days))
        row = cursor.fetchone()

    cmd = (
        "select ch.First_Name, ch.Last_Name, ch.CardHolderID from CardHolder ch "
        "order by Last_Name, First_Name "
    )

    cursor.execute(cmd)
    row = cursor.fetchone()
    while row:
        fname = row[0]
        lname = row[1]
        cid = row[2]
        if cid not in chids:
            countb += 1
            txtout.append(fmt.format(fname, lname, 0))
        row = cursor.fetchone()

    txtout.append(
        banner(
            1,
            "Cardholders reported: {} With Uses:{} No Uses:{}".format(
                (counta + countb), counta, countb
            ),
        )
    )
    conn.close()
    fillBox(txtout, append=append)


def reportEverything():
    """Generate all reports
    Primarily for emailing
    """
    global reportName
    setMessage("")
    get_data_keri()
    get_data_hello()
    reportSoundexMatch(append=False)
    reportMismatches(append=True)
    reportMismatchMemberNum(append=True)
    reportKeriDuplicates(append=True)
    reportKeriOnlyReason(append=True)
    reportKeriOnlyMembers(append=True)
    reportKeriOnlyNonmem(append=True)
    reportHelloClubOnly(append=True)
    reportMultiCards(append=True)
    reportExpired(append=True)
    reportAges(append=True);
    # Each individual report sets reportName so this is at end
    reportName = "HSA_full_report"


dataFetchedKeri = False
dataFetchedHello = False

root = Tk()
var = IntVar()
root.geometry("1200x700")
root.title("Kerisys / HelloClub Reporting")

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

mainframe = ttk.Frame(root, padding="3 3 12 12")
mainframe.grid(column=0, rows=8, columns=2, sticky=N + E + W + S, ipadx=10, ipady=10)
mainframe.grid_columnconfigure(1, weight=1)
mainframe.grid_rowconfigure(7, weight=1)


versionFrame = Label(mainframe, text="Version {}".format(VERSION))
versionFrame.grid(column=0, row=getNextRow(), sticky=E + W)

buttonFrame = LabelFrame(mainframe, text="Select")
buttons = [
    ("Soundex Matches", sequence(init=True), reportSoundexMatch),
    ("Mismatch Access Card", sequence(), reportMismatches),
    ("Mismatch Member Num", sequence(), reportMismatchMemberNum),
    ("Keri Duplicates", sequence(), reportKeriDuplicates),
    ("Keri Only Contractor", sequence(), reportKeriOnlyReason),
    ("Keri Only Members", sequence(), reportKeriOnlyMembers),
    ("Keri Only NonMem", sequence(), reportKeriOnlyNonmem),
    ("HelloClub Duplicates", sequence(), reportHelloClubDuplicates),
    ("HelloClub Only", sequence(), reportHelloClubOnly),
    ("Multiple Cards", sequence(), reportMultiCards),
    ("Expired", sequence(), reportExpired),
    ("Ages", sequence(), reportAges),
    ("All Reports", sequence(), reportEverything),
    ("Clear Cache", sequence(), clearCache),
    ("Clear Report", sequence(), clrwin),
]

i = 0
for (prompt, value, fctn) in buttons:
    i += 1
    rb = Radiobutton(buttonFrame, text=prompt, variable=var, command=fctn, val=value)
    rb.grid(column=0, row=i, stick=W)
buttonFrame.grid(column=0, row=getNextRow(), sticky=N)

visitFrame = LabelFrame(mainframe, text="Club Visit Reports")
visitFrame.grid(column=0, row=getNextRow(), sticky=E + W)
visitFrame.rowconfigure(0, weight=1)
visitFrame.columnconfigure(0, weight=1)

repyearBut = Button(visitFrame, text="Usage Report for year:", command=reportUniqueDays)
repyearBut.grid(column=0, row=0, sticky=E + W)

options = [str(x) for x in range(date.today().year, 2016, -1)]
chosen = StringVar()
chosen.set(options[0])

optMenu = OptionMenu(visitFrame, chosen, *options)
optMenu.grid(column=0, row=1, stick=W + E)

emailframe = LabelFrame(mainframe, text="Enter Email")
emailframe.grid(column=0, row=getNextRow(), sticky=N)

emailinput = Text(emailframe, height=1, width=20)
emailinput.grid(column=0, row=0, sticky=N)

emailbutton = Button(emailframe, text="Send Report", command=send_report)
emailbutton.grid(column=0, row=1, sticky=W + E)

msgtextFrame = LabelFrame(mainframe, text="Messages")
msgtextFrame.grid(column=0, row=getNextRow(), sticky=N)

msgtext = Text(msgtextFrame, height=7, width=20)
msgtext.grid(column=0, row=getNextRow(), sticky=N)
msgtext.configure(state="disable", wrap="word")

exitBut = Button(mainframe, text="Exit", command=sys.exit)
exitBut.grid(column=0, row=getNextRow(), sticky=W + E + N)

welcomeMsg = (
    "********************\n"
    "****** Welcome *****\n"
    "********************\n\n"
    "This application generates reports using the Kerisys access "
    "system database and the online helloclub.com database.\n\nWhen you "
    "make an initial query that requires hello club data there will "
    "be a brief delay and a yellow screen while that data is fetched "
    "from the helloclub server, after which switching between the various "
    "reports will be almost instantaneous.  You may also email reports "
    "to yourself."
)

textArea = scrolledtext.ScrolledText(mainframe, font=("Courier", 14))
textArea.grid(column=1, row=0, padx=10, pady=10, rowspan=9, stick=(N, S, E, W))
textArea.insert(INSERT, welcomeMsg)
textArea.configure(state="disable", bg="sky blue", wrap="word")

root.mainloop()
