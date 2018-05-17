'use strict';

var wsuri = 'wss://'+document.location.hostname+'/ws';
var wamp_uri_prefix = 'org.blue_labs.drchrono';
var realm = 'drchrono';

// that's all. please leave the rest of this to me.
var __version__  = 'version 1.0';
var __author__   = 'David Ford <david@blue-labs.org>'
var __email__    = 'firefighterblu3@gmail.com'
var __date__     = '2018-May-17 04:00E'
var __license__  = 'Apache 2.0'

var connection, session, principal, ticket,
    wamp_subscriptions = {};


$(document).ready(function() {
    // the WAMP connection to the Router
    connection = new autobahn.Connection({
        url: wsuri,
        realm: realm,
    });

    // fired when connection is established and session attached
    connection.onopen = function (ss, details) {
        ss.subscribe(wamp_uri_prefix+'.appointments.create', function(args) {
            console.log('create',args);
        });

        ss.subscribe(wamp_uri_prefix+'.appointments.modify', function(args) {
            console.log('modify',args);
        });

        ss.subscribe(wamp_uri_prefix+'.appointments.delete', function(args) {
            console.log('delete',args);
        });

    }

    // fired when connection was lost (or could not be established)
    connection.onclose = function (reason, details) {
    }

    connection.open();

});
