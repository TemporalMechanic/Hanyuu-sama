import config
if config.twilio:
    try:
        from twilio.rest import TwilioRestClient as Twilio
    except ImportError:
        print "Consider installing twilio's python REST API"
    client = Twilio(config.account, config.token)
    