from hcis.mail.catalog import MailCatalog, SyncResult, sync_mail
from hcis.mail.crm import mail_to_crm_event
from hcis.mail.ics import CalendarCandidate, parse_ics
from hcis.mail.schema import MailEnvelope, MailMessage

__all__ = [
    "CalendarCandidate",
    "MailCatalog",
    "MailEnvelope",
    "MailMessage",
    "SyncResult",
    "parse_ics",
    "mail_to_crm_event",
    "sync_mail",
]
