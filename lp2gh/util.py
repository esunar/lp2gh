import time
import re

GH_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def to_timestamp(dt):
    return dt.strftime(GH_DATE_FORMAT)

def remove_mentions(str):
    regex = r"([\s]+|^)(@)([^\s]+)"
    subst = "\\g<1>**\\g<3>**"
    return re.sub(regex, subst, str, 0, re.MULTILINE)