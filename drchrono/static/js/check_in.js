'use strict';

$(document).ready(function() {
    var fieldnames=[];

    function unsmash(smashed) {
        return fieldnames.find(x => x.smashed === smashed).name;
    }

    function findsmashed(name) {
        try {
            return fieldnames.find(x => x.name === name).smashed;
        } catch(error) {
            // this one isn't smashed (aka, input type=date)
            return name;
        }
    }

    function find_appointment_slot() {
        $.ajax({
            url:      '/ajax/walkin/find_time/',
            dataType: 'jsonp',
            data:     {},

            success: function(data) {
                var buttons = [];

                if (data['result'].length === 0) {
                    $('div.walk-in-appointment-selection')
                        .empty()
                        .append($('<p>Sorry, no available walk-in times, please see receptionist</p>'))
                        .closest('div')
                        .slideDown();

                } else {
                    for (var i in data['result']) {
                        var tm=data['result'][i];

                        buttons.push($('<li><button \
                         class="btn btn-info btn-lg walk-in-appointment-select" \
                         type="button" name="appointment-time" \
                         >'+tm+'</button></li>'));
                    }

                    $('div.walk-in-appointment-selection')
                        .empty()
                        .append($('<p>Select available walk-in time</p>'))
                        .append($('<ul/>'))
                        .children('ul')
                        .append(buttons)
                        .closest('div')
                        .slideDown();

                    $('div.demographics')
                        .slideDown();
                }
            },

            error: function(xhr, textStatus, err){
                console.log(xhr, textStatus, err);
            },

        });
    }

    function check_in_patient(name, dob, appointment_id) {
        var aj, csrf;

        csrf = $('input[name=csrfmiddlewaretoken]').val();
        aj = $.post({
            url:      '/ajax/checkin/complete/',
            dataType: 'json',
            data: {
                name: name,
                dob:  dob,
                appointment_id: appointment_id,
                csrfmiddlewaretoken: csrf,
            },

            success: function(data) {
                console.log('update the api',data);
                // TODO: make a smiley face somewhere
            },

            error: function(xhr, textStatus, err){
                console.log(xhr, textStatus, err);
            },

        });

        return aj;
    }

    function fetch_demographics(name, dob) {
        $.ajax({
            url:      '/ajax/checkin/demographics/',
            dataType: 'jsonp',
            data: {
                name: name,
                dob:  dob,
            },

            success: function(data) {
                for (var i in data['result']) {
                    var uname = findsmashed(i);

                    $('div.demographics')
                        .find('input[name='+uname+']')
                        .val(data['result'][i]);

                    if (i === 'date_of_birth') {
                        $('div.demographics')
                            .find('input[name=date_of_birth]')
                            .attr('data-date', data['result'][i]);
                    }
                }

                $('div.demographics')
                    .slideDown();
            },

            error: function(xhr, textStatus, err){
                console.log(xhr, textStatus, err);
            },

        });
    }

    function create_appointment(name, dob, appointment_time) {
        var aj, csrf;

        csrf = $('input[name=csrfmiddlewaretoken]').val();
        aj = $.post({
            url:      '/ajax/checkin/appointment/create/',
            dataType: 'json',
            data: {
                name: name,
                dob:  dob,
                appointment_time: appointment_time,
                csrfmiddlewaretoken: csrf,
            },

            success: function(data) {
                console.log(data);
            },

            error: function(xhr, textStatus, err){
                console.log(xhr, textStatus, err);
            },

        });

        return aj;
    }

    $('input[type=date]').on('change', function() {
        var data = moment(this.value, 'YYYY/MM/DD')
            .format( this.getAttribute('data-date-format'));

        if (data === 'Invalid date') {
            data = '';
            $(this).addClass('use-placeholder');

        } else {
            $(this).removeClass('use-placeholder');
        }

        this.setAttribute('data-date', data)
    }).trigger('change');

    $('form.check-in').on('submit', function(e) {
        for (var i in fieldnames) {
            var d = fieldnames[i];
            $('input[name='+d.smashed+']').attr('name', d.name);
        };
    });

    $('input[type=text]').each(function() {
        // store context
        var oldname, newname, _this = $(this);

        // scramble the name so chrome/webkit can't use autofill/autocomplete.
        // note, yes, there is an "autocomplete=off", but chrome distinctly
        // ignores it. chrome used to only ignore autocomplete in certain
        // circumstances but recent releases of chrome rabidly avoid every
        // known method to disable autofill and we can't ask doctors and
        // receptionists to manage advanced chrome://settings flags and
        // command line options.
        //
        // the only known way to handle this now is to scramble the 'name'
        // attribute and make sure placeholder doesn't appear to be 'name'
        // either.
        //
        // what a horrible idea for public devices...
        oldname = _this.attr('name');
        newname = (Math.random().toString(36)+
                   Math.random().toString(36))
                    .replace(/[^a-z]+/g, '');

        fieldnames.push({name: oldname, smashed: newname});
        _this.attr('name', newname);

        if (oldname === 'name') {
            // update the label too
            $(_this).prev('label').attr('for', newname);

            $(_this).autocomplete({
                source: function(request, response) {
                    var name, smashed;

                    name = $('input').find('name', unsmash($(_this).attr('name'))).val();

                    $.ajax({
                        url:      '/ajax/checkin/autocomplete/',
                        dataType: 'jsonp',
                        data: {
                            term: request.term,
                            name: name,
                        },

                        success: function(data) {
                            response(data['result']);
                        },

                        error: function(xhr, textStatus, err){
                            console.log(xhr, textStatus, err);
                        },

                    });
                },
                minLength: 1,
                select: function(event, ui) {
                    //console.log("Selected: "+ui.item.value);
                }
            });
        }
    });

    $('form.check-in').on('click', 'button[name=check]', function() {
        var name, dob;

        name = findsmashed('name');
        name = $('input[name='+name+']').val();
        dob  = $('input[name=date_of_birth]').val();

        if (dob.length != 10) {
            console.warn('No/incorrect DoB entered');

            $('#pre-check-box input[name=date_of_birth]')
                .css({border:'2px solid #bbbbbb'})
                .animate({
                    borderWidth:'5px',
                    borderColor:'red'
                }, 500)
                .animate({
                    borderWidth:'2px',
                    borderColor:'#bbbbbb'
                }, 500);

            return false;
        }

        $.ajax({
            url:      '/ajax/checkin/appointments/',
            dataType: 'jsonp',
            data: {
                name: name,
                dob:  dob,
            },
            success: function(data) {
                var buttons = [];

                for (var i in data['result']) {
                    var tm, id;

                    id = data['result'][i][0];
                    tm = data['result'][i][1];

                    if (i > 0 && i[0]==(data['result'].length-1)) {
                        buttons.push($('<li class="spacer"/>'));
                    }

                    buttons.push($('<li><button \
                     class="btn btn-info btn-lg appointment-select" \
                     type="button" name="appointment-time" \
                     appointment-id="'+id+'" \
                     >'+tm+'</button></li>'));
                }

                $('div.walk-in-appointment-selection')
                    .slideUp()
                    .empty();

                $('div.appointment-selection')
                    .empty()
                    .append($('<p>Appointment time:</p>'))
                    .append($('<ul/>'))
                    .children('ul')
                    .append(buttons)
                    .parent('div')
                    .slideDown();
            },
            error: function(xhr,textStatus,err){
                console.log(xhr,textStatus,err);
            },
        });
    });

    $('form.check-in').on('click', 'div.appointment-selection button.appointment-select', function() {
        var name, dob, appointment_id, tmpInput;

        name = findsmashed('name');
        name = $('input[name='+name+']').val();
        dob  = $('div.pre-checkin input[type=date]').attr('data-date');
        appointment_id = $(this).attr('appointment-id');

        tmpInput = $('<input type="hidden" name="appointment-selection" />')
        tmpInput.val($(this).text())
        tmpInput.attr('appointment-id', $(this).attr('appointment-id'));
        tmpInput.appendTo($("form.check-in"));

        $('button.appointment-select').removeClass('selected')
        $(this).addClass('selected');

        if ($(this).text() === 'I want a walk-in appointment') {
            find_appointment_slot();

        } else {
            check_in_patient(name, dob, appointment_id)
                .done(function() {
                    $('div.demographics')
                        .find('input')
                        .val('');

                    fetch_demographics(name, dob);
                })
                .fail(function(e) {
                    // if we get a fail now, either our DB is really
                    // screwed up, or someone's playing tricks and
                    // passing bad data. everything has already been
                    // programatically checked as the page was built

                    // note: not true, the Doc could have deleted the
                    // patient, or deleted the appointment AS the patient
                    // was checking in
                    console.error(e);
                });
        }
    });

    $('form.check-in').on('click', 'div.walk-in-appointment-selection button.walk-in-appointment-select', function() {
        // walk-in appt selected, see if we can get patient demographics,
        // then create a new appointment and check in the patient (done on
        // creation success)
        var name, dob;

        name = findsmashed('name');
        name = $('input[name='+name+']').val();
        dob  = $('div.pre-checkin input[type=date]').attr('data-date');

        console.log(name,dob);

        create_appointment(name, dob, $(this).text())
            .done(function (data) {
                console.log(data);
                // check_in_patient(name, dob, appointment_id)
                //     .done(function (){
                //             $('div.demographics')
                //                 .find('input')
                //                 .val('');

                //             fetch_demographics(name, dob);
                //     });
            });

    });

    $('form.check-in').on('click', 'button[name=demographics-complete]', function() {
        //$('form.check-in').submit();
    });

});
