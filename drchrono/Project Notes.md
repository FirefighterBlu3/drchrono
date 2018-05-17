Technologies

* Nginx with letsencrypt SSL certificates
* Python 3.6
  * datetime objects with correct TZ localization
  * UTF-8 content properly handled
  * variable annotation and decorators
* Django 1.11.1
  * Session values
  * Models with validators, FK
  * Forms .Form and .ModelForm for unbound (form data validation) and bound data (web page generation)
    * form data cleaners and widgets
  * ORM; use of Q obj QuerySets w/ annotation, field concatenation, filtering and ordering
* JavaScript, ES6 arrow functions
  * jQuery
    * AJAX
    * JSONP
    * promises & deferreds
    * element attribute scrambling to defeat Chrome autofill, combined with homoglyph/homographs
  * Bootstrap
* CSS3
  * Flex-box
  * GPU utilization triggers
* WAMP
  * CrossbarIO Web Application Messaging Protocol ~v18.5
  * python-autobahn client drives real-time updates for the Doctor's appointment page (in process)
* drchrono API
  * social_django oauth2 authentication
  * doctor, office, patient, appointment loading
  * patient and appointment patching
  * paged json loads
  * webhooks
* drchrono Project function
  * all hackathon specified function implemented except for demographics patch to the API (partially complete)
  * Dr login
  * Dr Appointments vs. Kiosk mode
  * Appointment view
    * displays pertinent list of per-day appointments
    * displays
      * a hoverable-resize patient photo
      * patient's preferred language
      * reason for visit
    * shows status of appointment with check-in time and wait time
      * wait time per patient
      * wait time for today
      * wait time for overall
    * box to indicate patient to be seen now (stops wait timer)
  * Patient check-in (existing patient only)
    * single appointment per day
    * choice if multiple appointments
    * walk-ins
      * next available (with minimum time) appointment slot
    * autocomplete on patient name
    * requires date-of-birth for identity matching



Notes

* This application is not really intended for high performance. It exists as a small unit with few resources and a marginally optimized Sqlite DB



Goals and TODO

* no oauth2 refresh_token() method yet
* allow doctor to set local timezone
* put a HOME button on kiosk path that takes user back to patient check-in
* put HOME button on dr path that takes user back to ...
* employ webhooks with the API so cache updates can happen in the background instead of a view load (view created, cache updates happen, needs wamp for appointment redraw)
  * trigger a reload at midnight by our server (probably use Celery)
* build a WAMP router and component so web page data can be updated real-time without page reloads (initial build created)
* need aesthetic continuity in check-in page
  * unselect other appointment time boxes before selecting current one
* make doctor appt page date selectable and selectable width (1day, 1wk..)
* patient check-in ought to toast a message that the person has been [un]successfully checked in
* new patients are not created, only existing patients are allowed
* new patients should have a [confirm?] button pop up next to their name/dob if they type in a name/dob that isn't in our database, we don't want to store typoed names
* demographics DoB doesn't have placeholder text because it's a widget[date] that doesn't support the placeholder attribute (read-only, still ought to have it simulated if there's no value)
* choosing a walk-in time could be iterative instead of making one big block
* choosing a walk-in time could round up



Bugs

* hardwired office appointment start time, no profile used
* hardwired min-office visit block is 30 minutes
* not all input is sanitized
* not all GET/POST request methods are properly checked
* a new page load for patient check-in does not consider if the patient has already checked in and will restart the wait-time and appointment status
* errors that redirect to the check-in page ought to fade away so the next patient doesn't see them
* clicking 'back' in the browser to the check-in page may result in an 'invalid date' indication due to HTML5 date widget not recovering all its state
* avg wait time for today (breaks/negative value) if you leave the timer running all day or if you check in on a different day
* appointment creation doesn't gracefully handle overlap or duplication