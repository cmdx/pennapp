# Server that reads csv file for initialization data and emits it
# waits for "send info" message then begins to stream csv file with patient data

import socketio
import eventlet
import json

eventlet.monkey_patch()
from flask import Flask, render_template

sio = socketio.Server(cors_allowed_origins='*')
app = Flask(__name__)

sending = False

moFields = ["FacilityID", "PatientID", "Modality", "Location", "Date", "Time", "Value"]
patientFields = ["name", "roomid", "roomnumber", "patientid"]
initFields = ["hospname", "roomId", "room", "patientId", "patientname"]
dataFile = "himss.moberg.demo.csv"
initFile = "moInitVals.csv"

roomIds = []
rooms = [
    {'roomId': 0, 'roomNo': '#1101', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 1, 'roomNo': '#1102', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 2, 'roomNo': '#1103', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 3, 'roomNo': '#1104', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 4, 'roomNo': '#1105', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 5, 'roomNo': '#1106', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 6, 'roomNo': '#1107', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 7, 'roomNo': '#1108', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 8, 'roomNo': '#1109', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 9, 'roomNo': '#1110', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 10, 'roomNo': '#1111', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 11, 'roomNo': '#1112', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 12, 'roomNo': '#1113', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 13, 'roomNo': '#1114', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 14, 'roomNo': '#1115', 'patient': {'patientId': '', 'patientName': ''}},
    {'roomId': 15, 'roomNo': '#1116', 'patient': {'patientId': '', 'patientName': ''}},
]
ranges = [
    {'vitalName': 'HR', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'RR', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'ABPSyst', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'ABPDias', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'ABPMean', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'EtCO2', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'ICP', 'vals': {'min': 7, 'max': 20}},
    {'vitalName': 'CPP', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'PbtO2', 'vals': {'min': 20, 'max': 50}},
    {'vitalName': 'CVP', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'Tperf', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'SpO2', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'perfDeltaT', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'Perfusion', 'vals': {'min': -999, 'max': 999}},
    {'vitalName': 'Burden', 'vals': {'min': -999, 'max': 3}}
]

modNorms = {
    'ABP': {'Syst': {'lo': 90, 'hi': 140}, 'Dias': {'lo': 60, 'hi': 90}, 'Mean': {'lo': 70, 'hi': 110}},
    'NBP': {'Syst': {'lo': 90, 'hi': 140}, 'Dias': {'lo': 60, 'hi': 90}, 'Mean': {'lo': 70, 'hi': 105}},
    'CPP': {'na': {'lo': 40, 'hi': 70}},
    'CVP': {'Mean': {'lo': 5, 'hi': 12}},
    'HR': {'na': {'lo': 40, 'hi': 150}},
    'ICP': {'Mean': {'lo': 7, 'hi': 20}},
    'ICT': {'na': {'lo': 36, 'hi': 38}},
    'PbtO2': {'Mean': {'lo': 20, 'hi': 50}},
    'RR': {'na': {'lo': 12, 'hi': 30}},
    'SpO2': {'na': {'lo': 94, 'hi': 100}},
    'Tcore': {'na': {'lo': 35, 'hi': 39}},
    'EtCO2': {'na': {'lo': 30, 'hi': 45}},
}

burdenDict = {}

def normalizeMod(modality, location, value):
    try:
        value = float(value)
        valStd = (value - modNorms[modality][location]['lo']) / \
                 (modNorms[modality][location]['hi'] - modNorms[modality][location]['lo'])
        valScale = valStd * 2 - 1
        return valScale
    except Exception as e:
        print(e)
        return -99

hospitalName = {'facilityId': 'DemoHospital', 'title': 'HIMSS 2020'}
shift = {'name': 'Not Set'}

customs = {'c1': 0, 'c2': 0, 'c3': 0,  # burden
           'c4': 0, 'c5': 0, 'c6': 0,  # map
           'c7': 0, 'c8': 0, 'c9': 0, # icp
           'c10': 0, 'c11': 0, 'c12': 0, #pbt
           'c13': 0, 'c14': 0,  # dt/tm & msgcount
           }

roundDigit = {
    # Modalities that need precision > 0
    # Format: modality, decimal digits
    'Tperf': 1,
    'perfDeltaT': 2,
    'Perfusion': 1,
    'Burden': 2,
}

def roundValue(modality):
    try:
        retDigits = roundDigit[modality]
        return retDigits
    except:
        return 0

# will emit updated ranges from form
@sio.on('set-ranges')
def rangeUpdate(sid, inputRange):
    print('sent range update')
    sio.emit('change-range', inputRange)

# all initialization data sent once server has connected to client
@sio.on('connect')
def connect(sid, environ):
    print('connect ', sid)
    readInit()  # function that will read from initialization file
    print("emitting rooms")
    sio.emit('init-ranges', ranges)
    sio.emit('update-title', hospitalName)
    sio.emit('update-shift', shift)

class Room(object):
    name: ""
    roomid: 0
    roomNumber: ""
    patientId: ""

# creates new room object that will later be sent to add into existing rooms array
def createRoom(nameIn, roomIdIn, roomNumIn, patId):
    room = Room()
    room.name = nameIn
    room.roomid = int(roomIdIn)
    room.roomNumber = roomNumIn
    room.patientId = patId
    return room

def getShift(hour):
    if hour in range(7, 16):
        return 'First'
    else:
        if hour in range(15, 24):
            return 'Second'
        else:
            return 'Night'

# reads from the initialization file and creates all the rooms that have data by ending individual lines
def readInit():
    with open(initFile) as ip:
        print('reading input')
        line = ip.readline()
        while line:
            res1 = line.strip()
            fin = res1.split(',')
            output = {}
            for i in range(0, len(fin)):
                output[patientFields[i]] = fin[i].rstrip()
            # send to function to construct room
            roomData = createRoom(output["name"], output["roomid"], output["roomnumber"], output["patientid"])
            # send to function that will add rooms to room array
            addRoom(roomData)
            # initialize burden dictionary entry
            if output['patientid']:
                burdenDict[output['patientid']] = {}
                burdenDict[output['patientid']]['ICP'] = 0
                burdenDict[output['patientid']]['PbtO2'] = 0
                burdenDict[output['patientid']]['Burden'] = 0

            line = ip.readline()
    # emit new rooms array
    sio.emit('init-data', rooms)


# adds room to existing rooms array
def addRoom(roomDataIn):
    if roomDataIn.roomid not in roomIds:
        roomIds.append(roomDataIn.roomid)
        room = {
            'roomId': roomDataIn.roomid,
            'roomNo': roomDataIn.roomNumber,
            'patient': {
                'patientId': roomDataIn.patientId,
                'patientName': roomDataIn.name,
                'alert': {
                    'status': False,
                    'vitName': ''},
                'vitals': {'HR': 0, 'RR': 0, 'ABPSyst': 0, 'ABPDias': 0, 'ABPMean': 0, 'EtCO2': 0, 'ICP': 0,
                           'CPP': 0, 'PbtO2': 0, 'CVP': 0, 'Tperf': 0, 'SpO2': 0, 'Perfusion': 0, 'perfDeltaT': 0,
                           'Burden': 0},
                'changedVital': {'vital': '', 'value': 0}}
        }
        rooms[roomDataIn.roomid] = room

# Main process to read data and send to client
def sendLine():
    mapOk = mapLo = mapHi = 0
    icpOk = icpLo = icpHi = 0
    pbtOk = pbtLo = pbtHi = 0
    burOk = burHi = 0
    curHour = 99
    skiprecs = 300000  #6178111
    reccount = skiprecs

    with open(dataFile) as fp:
        for _ in range(skiprecs):
            next(fp)
        line = fp.readline()
        while line:
            reccount += 1
            res2 = line.strip()
            res = res2.split(',')
            output = {}
            for i in range(0, len(res)):
                output[moFields[i]] = res[i].rstrip()

            if output['Modality'] == "ABP" and output["Location"] == "Mean":
                chkval =  normalizeMod(output['Modality'], output['Location'], output['Value'])
                if chkval > 1:
                    mapHi += 1
                else:
                    if chkval < -1:
                        mapLo += 1
                    else:
                        mapOk +=1

            if output['Modality'] == "ICP" and output["Location"] == "Mean":
                chkval =  normalizeMod(output['Modality'], output['Location'], output['Value'])
                if chkval > 1:
                    icpHi += 1
                else:
                    if chkval < -1:
                        icpLo += 1
                    else:
                        icpOk +=1

            if output['Modality'] == "PbtO2" and output["Location"] == "Mean":
                chkval =  normalizeMod(output['Modality'], output['Location'], output['Value'])
                if chkval > 1:
                    pbtHi += 1
                else:
                    if chkval < -1:
                        pbtLo += 1
                    else:
                        pbtOk += 1

            if output['Modality'] == "ABP":
                output['Modality'] = output['Modality'] + output['Location']

            output['Value'] = round(float(output['Value']), roundValue(output['Modality']))

            if output['Modality'] == "ICP":
                burdenDict[output['PatientID']]['ICP'] = round(normalizeMod(output['Modality'], output['Location'], output['Value']),2)
            elif output['Modality'] == "PbtO2":
                burdenDict[output['PatientID']]['PbtO2'] = round(normalizeMod(output['Modality'], output['Location'], output['Value']), 2)

            burdenDict[output['PatientID']]['Burden'] = abs(burdenDict[output['PatientID']]['ICP']) + abs(burdenDict[output['PatientID']]['PbtO2'])

            if burdenDict[output['PatientID']]['Burden'] > 3:
                burHi += 1
            else:
                burOk +=1

            mapTot = mapLo + mapOk + mapHi
            if mapTot > 0:
                customs['c1'] = round((mapLo / mapTot * 100), 0)
                customs['c2'] = round((mapOk / mapTot * 100), 0)
                #customs['c3'] = round((mapHi / mapTot * 100), 0)
                customs['c3'] = 100 - customs['c2'] - customs['c1']

            icpTot = icpLo + icpOk + icpHi
            if icpTot > 0:
                customs['c4'] = round((icpLo / icpTot * 100), 0)
                customs['c5'] = round((icpOk / icpTot * 100), 0)
                # customs['c6'] = round((icpHi / icpTot * 100), 0)
                customs['c6'] = 100 - customs['c5'] - customs['c4']
            pbtTot = pbtLo + pbtOk + pbtHi
            if pbtTot > 0:
                customs['c7'] = round((pbtLo / pbtTot * 100), 0)
                customs['c8'] = round((pbtOk / pbtTot * 100), 0)
                # customs['c9'] = round((pbtHi / pbtTot * 100), 0)
                customs['c9'] = 100 - customs['c8'] - customs['c7']

            burTot = burOk + burHi
            if burTot > 0:
                customs['c11'] = round((burOk / burTot * 100), 0)
                # customs['c12'] = round((burHi / burTot * 100), 0)
                customs['c12'] = 100 - customs['c11']


            customs['c13'] = reccount
            customs['c14'] = output['Date'] + " - " + output['Time'][0:8]

            sio.emit('update-customs', customs)

            inHour = int(output['Time'][0:2])
            if inHour != curHour:
                curHour = inHour
                shift['name'] = getShift(curHour)
                sio.emit('update-shift', shift)


            sio.emit('send-line', json.dumps(output))
            output['Value'] = round(burdenDict[output['PatientID']]['Burden'],2)
            output['Modality'] = 'Burden'
            output['Location'] = 'na'
            sio.emit('send-line', json.dumps(output))

            line = fp.readline()
            eventlet.sleep(.01)

# waits for message from first client then begins to stream patient data
@sio.on('send-records')
def sendRecords(sid, message):
    global sending
    if not sending:
        eventlet.spawn(sendLine)
        sending = True

# Socket.io  listen/.on for 'update-vital' message
@sio.on('update-vital')
def updateVital(sid, updatedVital):
    # Socket.io  send/.emit the updatedVital to any listening clients
    sio.emit('send-line', json.dumps(updatedVital))

# @sio.on('update-vital2')
# def updateVital(sid, updatedVital):
#     # Socket.io  send/.emit the updatedVital to any listening clients
#     sio.emit('update-vital2', updatedVital)

# Socket.io  listen/.on for 'reset-vitals' message
@sio.on('reset-vitals')
def resetVitals(sid):
    # Socket.io  send/.emit the rooms Array to any listening clients
    sio.emit('init-data', rooms)

@sio.on('disconnect')
def disconnect(sid):
    print('disconnect ', sid)

if __name__ == '__main__':
    # wrap Flask application with socketio's middleware
    app = socketio.Middleware(sio, app)
    # deploy as an eventlet WSGI server
    eventlet.wsgi.server(eventlet.listen(('', 8080)), app)
