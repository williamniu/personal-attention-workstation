from __future__ import annotations

from hcis.mail.catalog import whitelist_match
from hcis.mail.schema import MailMessage


def mail_to_crm_event(message: MailMessage) -> dict[str, object] | None:
    if not whitelist_match(message.sender, message.subject):
        return None
    return {
        "candidate_id": "william",
        "event_type": "RECRUITER_MAIL_RECEIVED",
        "event_time": message.received_at.isoformat(),
        "source": "mail",
        "external_event_id": message.internet_message_id,
        "notes": message.subject,
    }
