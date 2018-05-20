from autobahn.twisted.wamp import Application
from twisted.internet.defer import inlineCallbacks

SERVER='drc.blue-labs.org'

# note, this prefix specification is actually pointless at the moment
root='org.blue_labs.drchrono'
app = Application(root)

@app.signal('onjoined')
def called_on_joined():
    """ Loop sending the state of this machine using WAMP every x seconds.
        This function is executed when the client (myself) joins the router, which
        means it's connected and authenticated, ready to send WAMP messages.
        
        Things we'll do here:
            1. pull the patient and appointment data on startup
            2. emit a publish() message when a modification to the base
               data occurs. this is so the appointments page updates
               in real time.
    """
    print("Connected")


@app.subscribe(root+'.appointment')
@app.subscribe(root+'.appointment.create')
@app.subscribe(root+'.appointment.modify')
@app.subscribe(root+'.appointment.delete')
@app.subscribe(root+'.patient')
@app.subscribe(root+'.patient.create')
@app.subscribe(root+'.patient.modify')
@app.subscribe(root+'.patient.delete')
def foo(args):
    print('received a msg: {}'.format(args))



# start client
if __name__ == '__main__':
    print('startup')
    app.run(url='wss://{}:7998/ws'.format(SERVER), realm='drchrono')
