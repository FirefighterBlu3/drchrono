'use strict';

$(document).ready(function() {

    $('.glyphicon-refresh').on('click', function(){
        // ignore results, just trigger the view
        $.get('/doctor/appointments/refresh');
    });

    /*
     * take an integer number and return a H:M:S type notation
     */
    function secondsToNotation(s) {
        var fm = [
            // Math.floor(s / 60 / 60 / 24), // DAYS
            ~~ (s / 60 / 60) % 24, // HOURS
            ~~ (s / 60) % 60, // MINUTES
            s % 60 // SECONDS
        ];
        // map each element of 'fm' into a string, zero prefixed, then join all with ':'
        s = $.map(fm, function(v, i) { return ((v < 10) ? '0' : '') + v; }).join(':');

        // now strip off all leading zeroes and colons
        // 00:00:05 -> 5
        // 00:01:05 -> 1:05
        s = s.replace(/^[0:]+/gm, '');
        return s
    }

    /*
     * - running wait times are for patients that have checked in but not been seen
     * - static wait times are shown for:
     *     boxes the doctor has just checked
     *     the page has been reloaded and the box checked
     * - calculation of wait time is a summation of
     *     running wait times
     *     static wait times that do not have the 'seen-in-db' attribute on the box
     *
     * Note: this logic is semantically broken if the appointments page isn't loaded
     *       and running somewhere. the problem with using AJAX or WAMP to do constant
     *       accurate updates is the heavy network traffic
     */
    setInterval(function() {
        var avg, wtsa=[], wtsa_overall=[];

        // find all patients that have checked in
        $('td.arrived-time').each(function() {
            var now, seen, seen_in_db, arrived_time, ws, wt;

            now = ~~ (Date.now()/1000)

            arrived_time = $(this)
                .children('span.arrived-time-epoch')
                .text();

            seen = $(this)
                .siblings('td.see-patient')
                .children('input')
                .is(':checked')

            seen_in_db = $(this)
                .siblings('td.see-patient')
                .children('input')
                .attr('seen-in-db') === 'true'

            // do live updates for these EXCEPT if the 'seen' box is checked
            if (arrived_time.length > 0 && seen !== true) {
                ws = parseInt(now - arrived_time)
                wt = secondsToNotation(ws);

                $(this)
                    .next()
                    .children('span.wait-time-seconds')
                    .text(ws);

                $(this)
                    .next()
                    .children('span.wait-time-display')
                    .text(wt);
            }

            // sum up all the wait times for today
            if (arrived_time.length > 0) {
                ws = parseInt($(this)
                    .next()
                    .children('span.wait-time-seconds')
                    .text())

                wtsa.push(ws)
            }

            // sum up all the wait times overall, skip those with the seen-in-db attribute
            // they're already counted and stored in the overall TD
            if (arrived_time.length > 0 && seen_in_db !== true) {
                ws = parseInt($(this)
                        .next()
                        .children('span.wait-time-seconds')
                        .text())

                wtsa_overall.push(ws)
            }

        });

        // running average for today
        if (wtsa.length > 0) {
            var today_sum;

            today_sum = wtsa.reduce((a,b) => a+b, 0);
            avg = ~~(today_sum/wtsa.length);

            $('th#avg-wait-time-for-today').text(secondsToNotation(avg));
        }

        // running average overall
        var server_len, server_sum, overall_len, overall_sum;

        server_len = parseInt($('th#avg-wait-time-overall').attr('server-length'));
        server_sum = parseInt($('th#avg-wait-time-overall').attr('server-sum'));

        overall_len = wtsa_overall.length + server_len;
        overall_sum = server_sum + wtsa_overall.reduce((a,b) => a+b, 0);
        avg = ~~(overall_sum/overall_len);

        $('th#avg-wait-time-overall').text(secondsToNotation(~~avg));

    }, 1000);

    $(document).on('change', 'td.see-patient', function() {
        var id, csrf, checked, data, _this;

        // store context for during POST chain
        _this   = $(this);

        id      = $(_this).parent('tr').attr('patient-id');
        checked = $(_this).children('input').is(':checked');
        csrf    = $('input[name=csrfmiddlewaretoken]').val();
        data    = { id: id,
                    status: checked,
                    csrfmiddlewaretoken: csrf,
                  };

        $.post('/ajax/see-patient/', data, function(r) {
            $(_this)
                .parent('tr')
                .find('td.status')
                .text(r.status)
        });
    });

});
