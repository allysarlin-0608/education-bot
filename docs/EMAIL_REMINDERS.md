# Email reminders — ready to switch on later

In-app reminders work now: a learner turns them on in Settings → Reminders,
picks a time, and Today shows a short note after that time on a day she
hasn't studied. Email reminders reuse the same choice (`learner_prefs`:
`reminder_on`, `reminder_time`; `reminder_email` is the switch for email).

## How it will work

1. Once an hour, a small scheduled job asks the database for the people
   whose reminder time has just passed, who turned email on, and who
   haven't studied today. Only their email address and first name leave
   the database.
2. It sends each of them one short email ("A few minutes for GNOSIS
   today? Your next lesson: …") with a link to Today and a one-click
   "turn off email reminders" link.
3. Never more than one email a day; none on a day she has already studied.

## What you will do (about 15 minutes, once)

1. **Choose an email service.** Recommended: Resend (free for 3,000 emails
   a month). Sign up with the address that should send the emails.
2. **Verify your sending domain** in Resend (it shows two DNS records to
   add where your domain is registered). Resend says when it's verified.
3. **Create an API key** in Resend and paste it into the place I'll name
   then (a secret of the scheduled job, never in the code).
4. Tell me it's done: I switch email on and show you a test email first.

## A decision needed before then

The scheduled job has to read reminder times and email addresses of
everyone who chose email. That needs either Supabase's service key (it
can read everything; it would live only as a secret of the job) or a
narrow database function that returns only "who is due now" and can be
called only with a separate secret. **Recommendation: the narrow
function.** It's a security-related change, so I'll show you the SQL and
wait for your yes.
