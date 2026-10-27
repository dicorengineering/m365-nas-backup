"""Read MAPI property tags numerically, independent of hexadecimal padding."""

import re

PROPERTY_TAG = re.compile(r"^String\s+0x([0-9a-f]{1,4})$", re.IGNORECASE)


def metadata_subject(metadata):
    for prop in metadata.get("singleValueExtendedProperties") or []:
        match = PROPERTY_TAG.fullmatch(str(prop.get("id", "")).strip())
        if match and int(match[1], 16) == 0x0037:
            value = prop.get("value")
            if isinstance(value, str):
                return value
    return ""


def item_subject(item):
    # Old snapshots retain the original Graph metadata even when the old parser
    # failed to populate the convenience subject field. Never rewrite a snapshot.
    return item.get("subject") or metadata_subject(item.get("metadata", {}))
