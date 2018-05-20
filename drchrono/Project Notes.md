Purpose

This is an interview project to understand how I, the candidate, approach problem solving, how I utilize the Python language, and my software writing characteristics. If you're browsing this as an effort to produce your own drchrono hackathon task, please be mindful that my work is NOT representative of your work and should you be hired off my work, unless we are similar people, it'll probably show. That said, you can see how I did things, but use it as a suggestion as you develop your own. Don't copy and paste. Also, I'm utterly brand new to Django so I probably did a few things ... wrong. ;-]

My implementation of this project is considerably more detailed than is likely to be produced as I had certain circumstances that deviated dramatically from the norm.

Base requirements of the task are:

* account association flow where doctor can authenticate using their drchrono account
  * then set up the kiosk for their office
* after the doctor is logged in, a page should be displayed that lets patients check in
* a patient with an appointment should first confirm their identity (first/last name maybe SSN) then
  * be able to update their demographic information using the patient chart API endpoint
  * once the they have filled out that information the app can set the appointment status to "Arrived"

* the doctor should also have their own page they can leave open that displays today’s appointments
  * indicating which patients have checked in (status updated in API)
  * how long they have been waiting
  * doctor can indicate they are seeing a patient
    * which stops the “time spent waiting” clock
  * the doctor should also see the overall average wait time for all patients they have ever seen



Technologies:

* Nginx with letsencrypt SSL certificates
* Python 3.6
  * datetime objects with correct TZ localization
  * UTF-8 content properly handled
  * f strings
  * function and variable annotation, decorators
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
  * python-autobahn client drives real-time updates for the Doctor's appointment page
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



Operation flow:

* Doctor sign-in
* Doctor chooses mode (appointment view or kiosk)
  * Appointment View:
    * Render appointment page
      * click checkbox to see patients (AJAX update)

  * Kiosk:
    * <Cache is primed for Patients and Appointments>
    * Patient Check-in
      * Name and DoB entry (AJAX update)
      * Appointment time confirmation (AJAX update)
      * Demographics updates
        * Thank you (reverts to Patient Check-in)

AJAX updates may push data to the API which
- in turn the API should fire off a webhook. Said webhook view will update our models and will
- fire off a POST to our WAMP REST bridge
- to which the Doctor's appointment page has subscriptions for changing data



Notes

* This application is not really intended for high performance. It exists as a small unit with few resources and a marginally optimized Sqlite DB



Goals and TODO

* no oauth2 refresh_token() method yet
* allow doctor to set local timezone
* put a HOME button on kiosk path that takes user back to patient check-in
* put HOME button on dr path that takes user back to ...
* trigger a cache reload after midnight by our server (probably use Celery)
* need aesthetic continuity in check-in page
* make doctor appt page date selectable and selectable width (1day, 1wk..)
* patient check-in ought to toast a message that the person has been [un]successfully checked in (ajax xhr happens as demographics are ajax fetched)
* new patients are not created, only existing patients are allowed
* new patients should have a [confirm?] button pop up next to their name/dob if they type in a name/dob that isn't in our database, we don't want to store typoed names (new patients not yet supported)
* demographics DoB doesn't have placeholder text because it's a widget[date] that doesn't support the placeholder attribute (read-only, still ought to have it simulated if there's no value)
* choosing a walk-in time could be iterative instead of making one big block
* choosing a walk-in time could round up
* walk-in slots ought to be fully populated
* mock tests, currently there's zilch
* some view functions have gotten a bit fat and ought to be rewritten using a sub-function or two to clearly confine operations
* perhaps show patient photo in the demographics or check-in sections?
* finish wiring up the WAMP create/delete in appt page
* if an appointment date changes, unset the arrived_time, and seen*
* if the last row is removed from the appointment table, void the wait time for today
* hardwired office appointment start time, no profile used
* hardwired min-office visit block is 30 minutes
* a new page load for patient check-in does not consider if the patient has already checked in and will restart the wait-time and appointment status


Bugs

* not all input is sanitized
* errors that redirect to the check-in page ought to fade away so the next patient doesn't see them
* clicking 'back' in the browser to the check-in page may result in an 'invalid date' indication due to HTML5 date widget not recovering all its state
* wait times for today (breaks/negative value) if you leave the timer running all day or if you check in on a different day or appointments are moved from day to day
* walk-in appointment creation doesn't gracefully handle overlap or duplication
* on tablets, the date widget doesn't handle my CSS cleanly
* a number of API interactions don't respond cleanly if the appt/pt is deleted external to the app (webhooks don't always arrive to update me, actually, no DELETE have arrived, ever)
* saving a patient's preferred language doesn't work right because we don't have a reverse of full-form to 639-2


=======================================================
Bugs to report to drchrono:

API notes
* Patient Modification webhooks aren't being performed although requested
* Appointment creation endpoint would help a lot if it returned the new appointment ID in the response (does this apply to any endpoint that creates objects?)
* API doesn't like the ISO 639-2 alpha_3 code for "German"; "deu", or is it all?



API via $user.drchrono.com notes
* changing appointment exam room 0 to drop down selection (1-4) will create four instances of the appointment



What I would really love to do, is write documentation for a large set of single method sample implementations for each endpoint of the API that show exactly how something should be used
