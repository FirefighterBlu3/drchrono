from autobahn.twisted.wamp import Application
from twisted.internet.defer import inlineCallbacks

SERVER='drc.blue-labs.org'

app = Application('drchrono')

@app.signal('onjoined')
@inlineCallbacks
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


# start client
if __name__ == '__main__':
    app.run(url=u'ws://{}:7998/ws'.format(SERVER))
