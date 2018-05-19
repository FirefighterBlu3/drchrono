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


function add_row(data) {
    var tr;
    console.log('adding row for',data);

    // ES6 multiline string
    tr = $(`<tr appointment-id="" patient-id="">
                <td class="patient-photo">
                    <img class="patient-photo" src=""/>
                </td>
                <td class="name"/>
                <td class="preferred-language"/>
                <td class="scheduled-time align-as-clocktime">
                    <span class="scheduled-time-epoch"/>
                    <span class="scheduled-time-display"/>
                </td>
                <td class="exam-room"/>
                <td class="reason"/>
                <td class="status"/>
                <td class="arrived-time">
                    <span class="arrived-time-epoch"/>
                    <span class="arrived-time-display"/>
                </td>
                <td class="timer">
                    <span class="wait-time-seconds"/>
                    <span class="wait-time-display"/>
                </td>
                <td class="see-patient">
                    <input type="checkbox"/>
                </td>
            </tr>`);

    tr.attr('appointment-id', data['id']);
    tr.attr('patient-id', data['patient']['id']);
    tr.find('img.patient-photo').attr('src',data['patient']['patient_photo']);
    tr.find('td.name').text(data['patient']['first_name']+' '+data['patient']['last_name']);
    tr.find('td.preferred-language').text(data['patient']['preferred_language']);
    tr.find('span.scheduled-time-epoch').text(data['scheduled_time_epoch']);
    tr.find('span.scheduled-time-display').text(data['scheduled_time_display']);
    tr.find('td.exam-room').text(data['exam_room']);
    tr.find('td.reason').text(data['reason']);
    tr.find('td.status').text(data['status']);
    tr.find('span.arrived-time-epoch').text(data['arrived_time_epoch']);
    tr.find('span.arrived-time-display').text(data['arrived_time_display']);
    if (data['seen_time'] > 0) {
        var inp = tr.find('td.see-patient input');
        inp.attr('checked', 'checked');
        inp.attr('seen-in-db', 'true');
        inp.attr('seen-time', data['seen_time']);
    }

    // need to find the row to insert before
    $('table.table-appointments>tbody').append(tr);

}


$(document).ready(function() {
    // the WAMP connection to the Router
    connection = new autobahn.Connection({
        url: wsuri,
        realm: realm,
    });

    // fired when connection is established and session attached
    connection.onopen = function (ss, details) {
        var tr, data, e, page_day, sub;

        ss.subscribe(wamp_uri_prefix+'.appointment.create', function(args) {
            console.log('create',args);
        });

        ss.subscribe(wamp_uri_prefix+'.appointment.modify', function(args) {
            data=args[0];
            tr = $('tr[appointment-id='+data['id']+']');

            // if the appointment was rescheduled for another day, delete the row
            page_day = $('table.table-appointments').attr('today-date');

            sub = data['scheduled_time'].substr(0,10);
            if (sub !== page_day) {
                console.log('removing appointment',data);
                tr.remove();
                return;
            }

            // rescheduled from another day, add a row
            if (tr.length === 0) {
                add_row(data);
                return;
            }

            // can be 0 or 1 rows
            tr.each(function (o){
                e=$(this).find('td.scheduled-time span.scheduled-time-epoch');
                e.text(data['scheduled_time_epoch']);

                e=$(this).find('td.scheduled-time span.scheduled-time-display');
                e.text(data['scheduled_time_display']);

                e=$(this).find('td.exam-room');
                e.text(data['exam_room']);
                e=$(this).find('td.reason');
                e.text(data['reason']);
                e=$(this).find('td.status');
                e.text(data['status']);
            });
        });

        ss.subscribe(wamp_uri_prefix+'.appointment.delete', function(args) {
            console.log('delete',args);
        });

        // ss.subscribe(wamp_uri_prefix+'.patient.create', function(args) {
        //     console.log('create',args);
        // });

        ss.subscribe(wamp_uri_prefix+'.patient.modify', function(args) {
            data=args[0];
            tr = $('tr[patient-id='+data['id']+']');
            if (tr.length === 0) { return; }

            // can be 0 (person doesn't have an appt) or 1+ rows
            tr.each(function (o){
                e=$(this).find('td.patient-photo').children('img');
                e.attr('src',data['patient_photo']);

                e = $(this).find('td.name');
                e.text(data['first_name']+' '+data['last_name']);

                e = $(this).find('td.preferred-language');
                e.text(data['preferred_language']);
            });
        });

        ss.subscribe(wamp_uri_prefix+'.patient.delete', function(args) {
            console.log('delete',args);
        });

    }

    // fired when connection was lost (or could not be established)
    connection.onclose = function (reason, details) {
    }

    connection.open();

});
