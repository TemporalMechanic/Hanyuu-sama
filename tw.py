import logging
import bootstrap

bootstrap.logging_setup()

try:
    from twilio.rest import TwilioRestClient
except ImportError:

class Twilio(object): #TODO: something akin to adding this to logging
    """
    Extra config needed:
    config.twilio.enabled = True
    config.twilio.devs = ["+123456789012", ...] # numbers to iter over. must be verified and valid.
    config.twilio.send = ["critical", "alert", "warning"
                            # "info"
                            # "exception"
                        ]
    config.twilio.account = "ACxx..."
    config.twilio.token = "..."
    
    """
    def __init__(self):
        if config.twilio.enabled:
            self.client = TwilioRestClient(config.twilio.account, config.twilio.token)
            self.send = config.twilio.send
        else:
            self.client = None
    
    def _sms_devs(self, message):
        if self.client is not None:
        for dev in config.twilio.devs:
            client.sms.message(to=dev, from=config.twilio.number,
                                body=message[:159]) # 160 limit for SMS. TODO: make this check elsewhere.
        else:
            logging.warning("Trying to call twilio without it enabled.")
    def sms(self, type_, body):
        if self.client is not None:
            if type_ == "alert" and "alert" in self.send:
                body.prepend("[Alert]\n")
            elif type_ == "warning" and "warning" in self.send:
                body.prepend("[Warning]\n")
            elif type_ == "critical" and "critical" in self.send:
                body.prepend("[CRITICAL]\n")
            elif type_ == "info" and "info" in self.send:
                body.prepend("[Info]\n")
            elif type_ == "exception" and "exception" in self.send:
                body.prepend("[Exception]\n")
            # ^ could be in a loop, herp.
            if len(body) > 160:
                logging.warning("SMS Alert is over the limit (160 chars), truncating.")
            logging.info("Attempting to send {0} SMS Messages to devs".format(len(config.twilio.devs)))
            self._sms_devs(body)
            return
        else:
            logging.info("SMS Not enabled.")